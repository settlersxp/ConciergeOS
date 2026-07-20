#!/usr/bin/env python3
"""
PromptStore — database-backed CRUD for versioned prompts.

Each prompt is identified by a unique {prompt_id, version} pair and stores
4 structured fields: intention, restrictions, output_structure, user_prompt_template.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import PromptVersion

logger = logging.getLogger(__name__)


def build_system_prompt(pv: PromptVersion) -> str:
    """Build the system prompt string from a PromptVersion's structured fields."""
    parts = []
    if pv.intention:
        parts.append(pv.intention)
    if pv.restrictions:
        parts.append(pv.restrictions)
    if pv.output_structure:
        parts.append(pv.output_structure)
    return "\n\n".join(parts)


class PromptStore:
    """Database-backed prompt version store."""

    def __init__(self, db_session_factory=None):
        """Initialize with an optional custom session factory.

        If no factory is provided, uses SessionLocal (the default app session).
        """
        if db_session_factory is not None:
            self._session_factory = db_session_factory
        else:
            self._session_factory = SessionLocal

    def _session(self) -> Session:
        """Return a new database session."""
        return self._session_factory()

    # ------------------------------------------------------------------
    # CRUD operations
    # ------------------------------------------------------------------

    def create_prompt(
        self,
        prompt_id: str,
        name: str,
        intention: str,
        restrictions: str,
        output_structure: str,
        user_prompt_template: str,
        metadata_dict: dict | None = None,
    ) -> PromptVersion:
        """Create version 1 of a new prompt. Auto-sets as default."""
        with self._session() as db:
            # Check if this prompt_id already exists
            existing = db.execute(
                select(PromptVersion).where(
                    PromptVersion.prompt_id == prompt_id
                )
            ).scalars().first()

            if existing:
                raise ValueError(
                    f"Prompt '{prompt_id}' already exists. Use update_prompt or duplicate_prompt."
                )

            now = datetime.now(timezone.utc)
            prompt = PromptVersion(
                prompt_id=prompt_id,
                version=1,
                name=name,
                intention=intention,
                restrictions=restrictions,
                output_structure=output_structure,
                user_prompt_template=user_prompt_template,
                is_default=True,
                meta_json=json.dumps(metadata_dict) if metadata_dict else None,
                created_at=now,
                updated_at=now,
            )
            db.add(prompt)
            db.commit()
            db.refresh(prompt)
            return prompt

    def get_prompt(
        self,
        prompt_id: str,
        version: int | None = None,
    ) -> PromptVersion | None:
        """Get a specific version, or the default if version is None."""
        with self._session() as db:
            if version is not None:
                stmt = select(PromptVersion).where(
                    PromptVersion.prompt_id == prompt_id,
                    PromptVersion.version == version,
                )
            else:
                # Try default first, fall back to highest version
                stmt = select(PromptVersion).where(
                    PromptVersion.prompt_id == prompt_id,
                    PromptVersion.is_default == True,  # noqa: E712
                )

            result = db.execute(stmt).scalars().first()
            return result

    def list_prompts(self, prompt_id: str) -> list[PromptVersion]:
        """List all versions for a prompt ID, ordered by version number."""
        with self._session() as db:
            stmt = (
                select(PromptVersion)
                .where(PromptVersion.prompt_id == prompt_id)
                .order_by(PromptVersion.version)
            )
            result = db.execute(stmt)
            return list(result.scalars().all())

    def list_all_prompts(self) -> list[dict[str, Any]]:
        """Summary of all prompt IDs with default version and count."""
        with self._session() as db:
            stmt = select(PromptVersion)
            results = db.execute(stmt).scalars().all()

            # Group by prompt_id
            groups: dict[str, list[PromptVersion]] = {}
            for pv in results:
                groups.setdefault(pv.prompt_id, []).append(pv)

            summaries = []
            for pid, versions in sorted(groups.items()):
                default_version = next(
                    (v.version for v in versions if v.is_default),
                    versions[-1].version,  # fallback to highest
                )
                summaries.append({
                    "prompt_id": pid,
                    "default_version": default_version,
                    "version_count": len(versions),
                    "name": versions[-1].name,  # latest name
                })
            return summaries

    def update_prompt(
        self,
        prompt_id: str,
        version: int,
        name: str | None = None,
        intention: str | None = None,
        restrictions: str | None = None,
        output_structure: str | None = None,
        user_prompt_template: str | None = None,
        metadata_dict: dict | None = None,
    ) -> PromptVersion:
        """Update an existing prompt version."""
        with self._session() as db:
            prompt = db.execute(
                select(PromptVersion).where(
                    PromptVersion.prompt_id == prompt_id,
                    PromptVersion.version == version,
                )
            ).scalars().first()

            if prompt is None:
                raise ValueError(
                    f"Prompt {prompt_id}:v{version} not found."
                )

            if name is not None:
                prompt.name = name
            if intention is not None:
                prompt.intention = intention
            if restrictions is not None:
                prompt.restrictions = restrictions
            if output_structure is not None:
                prompt.output_structure = output_structure
            if user_prompt_template is not None:
                prompt.user_prompt_template = user_prompt_template
            if metadata_dict is not None:
                prompt.meta_json = json.dumps(metadata_dict)

            prompt.updated_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(prompt)
            return prompt

    def delete_prompt(self, prompt_id: str, version: int) -> bool:
        """Delete a version. If it was default, set next-lower as default."""
        with self._session() as db:
            prompt = db.execute(
                select(PromptVersion).where(
                    PromptVersion.prompt_id == prompt_id,
                    PromptVersion.version == version,
                )
            ).scalars().first()

            if prompt is None:
                raise ValueError(
                    f"Prompt {prompt_id}:v{version} not found."
                )

            was_default = prompt.is_default
            pid = prompt.prompt_id
            pv = prompt.version

            # Get remaining versions after deletion
            remaining = db.execute(
                select(PromptVersion)
                .where(PromptVersion.prompt_id == pid)
                .order_by(PromptVersion.version.desc())
            ).scalars().all()

            db.delete(prompt)
            db.commit()

            # If we deleted the default, set next-lower as default
            if was_default and remaining:
                # Find the highest version among remaining (next-lower)
                next_default = remaining[0]
                next_default.is_default = True
                next_default.updated_at = datetime.now(timezone.utc)
                db.commit()

            return True

    def duplicate_prompt(
        self,
        prompt_id: str,
        version: int,
        name: str | None = None,
    ) -> PromptVersion:
        """Duplicate a version, creating version+1 with copied content."""
        with self._session() as db:
            source = db.execute(
                select(PromptVersion).where(
                    PromptVersion.prompt_id == prompt_id,
                    PromptVersion.version == version,
                )
            ).scalars().first()

            if source is None:
                raise ValueError(
                    f"Prompt {prompt_id}:v{version} not found."
                )

            # Find next version number
            highest = db.execute(
                select(PromptVersion)
                .where(PromptVersion.prompt_id == prompt_id)
                .order_by(PromptVersion.version.desc())
                .limit(1)
            ).scalars().first()

            new_version = highest.version + 1 if highest else version + 1

            now = datetime.now(timezone.utc)
            new_prompt = PromptVersion(
                prompt_id=prompt_id,
                version=new_version,
                name=name or source.name,
                intention=source.intention,
                restrictions=source.restrictions,
                output_structure=source.output_structure,
                user_prompt_template=source.user_prompt_template,
                is_default=False,
                meta_json=source.meta_json,
                created_at=now,
                updated_at=now,
            )
            db.add(new_prompt)
            db.commit()
            db.refresh(new_prompt)
            return new_prompt

    def set_default(self, prompt_id: str, version: int) -> PromptVersion:
        """Set a specific version as the default for this prompt_id."""
        with self._session() as db:
            prompt = db.execute(
                select(PromptVersion).where(
                    PromptVersion.prompt_id == prompt_id,
                    PromptVersion.version == version,
                )
            ).scalars().first()

            if prompt is None:
                raise ValueError(
                    f"Prompt {prompt_id}:v{version} not found."
                )

            # Unset all defaults for this prompt_id
            db.execute(
                update(PromptVersion)
                .where(PromptVersion.prompt_id == prompt_id)
                .values(is_default=False, updated_at=datetime.now(timezone.utc))
            )

            prompt.is_default = True
            prompt.updated_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(prompt)
            return prompt

    def get_default_prompt(self, prompt_id: str) -> PromptVersion | None:
        """Get the default version for a prompt ID."""
        return self.get_prompt(prompt_id, version=None)

    def resolve_prompt(
        self,
        prompt_id: str,
        version: int | None = None,
    ) -> tuple[str, str]:
        """Resolve a prompt to its system prompt and user message template.

        Returns:
            Tuple of (system_prompt, user_prompt_template)
            System prompt = intention + restrictions + output_structure
        """
        prompt = self.get_prompt(prompt_id, version)
        if prompt is None:
            raise ValueError(
                f"Prompt {prompt_id}{':v' + str(version) if version else ''} not found."
            )

        system_prompt = build_system_prompt(prompt)

        # Resolve placeholders at query time
        from app.services.placeholders import resolve_placeholders
        system_prompt = resolve_placeholders(system_prompt)
        return system_prompt, prompt.user_prompt_template

    # ------------------------------------------------------------------
    # Table management & seeding
    # ------------------------------------------------------------------

    def create_all_tables(self, engine) -> None:
        """Create all tables defined in Base that don't exist yet."""
        from app.models import Base
        Base.metadata.create_all(engine)

    def seed_default_prompts(self) -> None:
        """On startup: if no prompts exist, seed from current hardcoded prompts.

        Splits SHARED_SYSTEM_PROMPT and the user prompt template from
        app/services/llm.py into the 4 structured fields.
        """
        with self._session() as db:
            count = db.execute(
                select(PromptVersion).limit(1)
            ).scalars().first()
            if count is not None:
                # Prompts already exist, nothing to seed
                return

        # Import here to avoid circular imports
        from app.services.llm import SHARED_SYSTEM_PROMPT

        # Extract a reasonable split from the existing system prompt
        # The current SHARED_SYSTEM_PROMPT contains:
        # - Base system instructions (lines 159-176): concierge role + output format
        # - Schema description (auto-generated from DB)
        # - Tool definitions description

        # The user prompt template from query_guest_with_llm (line 589)
        default_user_template = (
            "Please find all information about the guest named. "
            "The guest's name can have it's name translated into the following languages "
            "Arabic, Chinese, Devanagari, Japanese, Korean, Latin or Nordic. "
            "It is unclear if is the user's first name or last name. "
            "Retry once with every translated language if needed. "
            "Also bring the information about its reservations. : {customer_name}"
        )

        with self._session() as db:
            now = datetime.now(timezone.utc)
            prompt = PromptVersion(
                prompt_id="guest-search",
                version=1,
                name="Guest Search v1",
                intention=SHARED_SYSTEM_PROMPT,
                restrictions="",
                output_structure="",
                user_prompt_template=default_user_template,
                is_default=True,
                meta_json=json.dumps({
                    "author": "system",
                    "migrated_from": "app/services/llm.py",
                    "changelog": "Initial seed from hardcoded prompts",
                }),
                created_at=now,
                updated_at=now,
            )
            db.add(prompt)
            db.commit()
            logger.info("Seeded default prompt: guest-search:v1")