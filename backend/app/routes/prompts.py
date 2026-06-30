#!/usr/bin/env python3
"""
FastAPI router for prompt version CRUD operations.

Provides REST endpoints:
  GET    /api/prompts                          — List all prompt IDs (summary)
  GET    /api/prompts/placeholders             — List all available placeholders
  POST   /api/prompts/{prompt_id}/{version}/preview — Preview rendered prompt
  GET    /api/prompts/{prompt_id}/default      — Get the default version (resolved)
  GET    /api/prompts/{prompt_id}/{version}    — Get specific version
  GET    /api/prompts/{prompt_id}              — List all versions for a prompt ID
  POST   /api/prompts/{prompt_id}              — Create new version (auto-increments)
  PUT    /api/prompts/{prompt_id}/{version}    — Update existing version
  DELETE /api/prompts/{prompt_id}/{version}    — Delete a version
  POST   /api/prompts/{prompt_id}/{version}/duplicate — Duplicate (creates next version)
  PATCH  /api/prompts/{prompt_id}/{version}/set-default — Set as default
"""

import json
import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/prompts", tags=["prompts"])


# ---------------------------------------------------------------------------
# Request schemas (inline to avoid circular imports)
# ---------------------------------------------------------------------------

class CreatePromptRequest(BaseModel):
    name: str
    intention: str
    restrictions: str
    output_structure: str
    user_prompt_template: str
    metadata: dict | None = None


class UpdatePromptRequest(BaseModel):
    name: str | None = None
    intention: str | None = None
    restrictions: str | None = None
    output_structure: str | None = None
    user_prompt_template: str | None = None
    metadata: dict | None = None


class DuplicatePromptRequest(BaseModel):
    name: str | None = None


class ChatMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class AiImproveRequest(BaseModel):
    section: str  # "intention" | "restrictions" | "output_structure" | "user_prompt_template"
    current_text: str
    conversation: list[ChatMessage] = []
    model: str | None = None


class AiImproveResponse(BaseModel):
    improved_text: str
    summary: str | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _prompt_to_schema(pv: Any) -> dict[str, Any]:
    """Convert a PromptVersion ORM object to a dict suitable for JSONResponse."""
    import json
    meta = None
    if pv.meta_json is not None:
        try:
            meta = json.loads(pv.meta_json)
        except (json.JSONDecodeError, TypeError):
            meta = None
    return {
        "id": pv.id,
        "prompt_id": pv.prompt_id,
        "version": pv.version,
        "name": pv.name,
        "intention": pv.intention,
        "restrictions": pv.restrictions,
        "output_structure": pv.output_structure,
        "user_prompt_template": pv.user_prompt_template,
        "is_default": pv.is_default,
        "metadata": meta,
        "created_at": pv.created_at.isoformat() if pv.created_at else None,
        "updated_at": pv.updated_at.isoformat() if pv.updated_at else None,
    }


# ---------------------------------------------------------------------------
# Section context for AI improvement system prompt
# ---------------------------------------------------------------------------

_SECTION_CONTEXT = {
    "intention": """This section defines the AI assistant's core purpose and role. It should clearly state what the assistant is designed to do and its primary objectives.""",
    "restrictions": """This section defines boundaries, rules, and constraints the AI must follow. It should specify what the assistant should NOT do and any limitations on its behavior.""",
    "output_structure": """This section defines how the AI should format and structure its responses. It should specify the expected output format, including markdown structures, sections, and styling.""",
    "user_prompt_template": """This section is the template for the user's query. It contains placeholders like {customer_name} that will be replaced at runtime. It should clearly express the user's request.""",
}


_AI_IMPROVE_SYSTEM_PROMPT = """\
You are an expert prompt engineer specializing in AI system prompts for hotel concierge services.
Your job is to rewrite and improve individual sections of prompts.

You are currently working on the {section} section.

Context about this section:
{section_context}

## RULES

1. When the user asks for improvements, ALWAYS return the complete rewritten section text
2. Improve clarity, specificity, and actionability
3. Fix grammar, spelling, and awkward phrasing
4. Use clear, direct language with concrete instructions
5. If the section has structural issues, reorganize it for better readability
6. Use bullet points or numbered lists for multiple rules/constraints

## OUTPUT FORMAT — JSON ONLY

Return a single valid JSON object with exactly these two fields:

{{
  "improved_text": "... the complete improved section text here ...",
  "summary": "... brief one-line summary of what was changed ..."
}}

Rules for the output:
- Return ONLY the JSON object, nothing else
- Do NOT wrap it in markdown code fences (```)
- Do NOT add any text before or after the JSON
- The "improved_text" value should be the complete section text, ready to be applied
- The "summary" should be a brief explanation (1-2 sentences) of what changed
- Use escaped newlines (\\n) for line breaks inside the improved_text value
"""


# ---------------------------------------------------------------------------
# Endpoints
# NOTE: Static routes (e.g., /placeholders) MUST come before parameterized
# routes (e.g., /{prompt_id}) so FastAPI matches them correctly.
# ---------------------------------------------------------------------------

@router.post("/ai-improve")
async def ai_improve_prompt(body: AiImproveRequest):
    """Use LLM to iteratively improve a prompt section via chat conversation."""
    from app.services.llm import get_llm_config

    section_context = _SECTION_CONTEXT.get(body.section, "")
    system_prompt = _AI_IMPROVE_SYSTEM_PROMPT.format(
        section=body.section, section_context=section_context
    )

    # Build message list: system + conversation history + current request
    messages: list[Any] = [
        {"role": "system", "content": system_prompt},
    ]

    for msg in body.conversation:
        messages.append({"role": msg.role, "content": msg.content})

    # Build the user request from conversation history or use default
    user_request = "Improve this section for clarity and effectiveness."
    if body.conversation:
        # Use the last user message as the improvement request
        last_user_msg = next(
            (m.content for m in reversed(body.conversation) if m.role == "user"),
            None,
        )
        if last_user_msg:
            user_request = last_user_msg

    # Add the current improvement request
    messages.append({
        "role": "user",
        "content": (
            f"Current {body.section} section text:\n\n```\n{body.current_text}\n```\n\n"
            f"User request: {user_request}\n\n"
            f"Rewrite the above section incorporating the user's request. "
            f"Return only the improved text."
        ),
    })

    client, model_name = get_llm_config()
    model = body.model or model_name

    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.3,
            max_tokens=2000,
        )
        raw_content = response.choices[0].message.content or body.current_text

        # Try to parse JSON response from LLM
        improved_text = body.current_text
        summary = None

        # Strip markdown code fences if present
        content_stripped = raw_content.strip()
        if content_stripped.startswith("```json"):
            content_stripped = content_stripped[7:]
        if content_stripped.startswith("```"):
            content_stripped = content_stripped[3:]
        if content_stripped.endswith("```"):
            content_stripped = content_stripped[:-3]
        content_stripped = content_stripped.strip()

        try:
            parsed = json.loads(content_stripped)
            improved_text = parsed.get("improved_text", body.current_text)
            summary = parsed.get("summary")
        except (json.JSONDecodeError, TypeError):
            # LLM didn't return valid JSON — use raw content as improved_text
            logger.warning("LLM did not return valid JSON for ai-improve, using raw content")
            improved_text = raw_content

        return AiImproveResponse(improved_text=improved_text, summary=summary)
    except Exception as e:
        logger.error(f"Error in AI improve: {e}")
        raise HTTPException(status_code=500, detail=f"LLM request failed: {str(e)}")


@router.get("")
async def list_all_prompts():
    """List summary of all prompt IDs."""
    from app.services.prompts import PromptStore
    store = PromptStore()
    try:
        summaries = store.list_all_prompts()
        return summaries
    except Exception as e:
        logger.error(f"Error listing prompts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/placeholders")
async def list_available_placeholders():
    """Return all available placeholder definitions for the frontend."""
    from app.services.placeholders import get_all_placeholders
    placeholders = get_all_placeholders()
    return {"placeholders": [{"key": key, **meta} for key, meta in placeholders.items()]}


@router.get("/field-schema")
async def get_field_schema():
    """Return structured database schema info for runtime variable discovery.

    Returns a dict mapping table names to lists of column info dicts,
    so the frontend can show users what {table.field} variables are available.
    """
    from app.services.placeholders import _get_db_schema
    schema = _get_db_schema()
    return schema


@router.post("/{prompt_id}/{version:int}/preview")
async def preview_prompt(prompt_id: str, version: int):
    """Resolve all placeholders and return the fully rendered prompt."""
    from app.services.prompts import PromptStore
    from app.services.placeholders import resolve_placeholders
    store = PromptStore()
    prompt = store.get_prompt(prompt_id, version)
    if prompt is None:
        raise HTTPException(status_code=404, detail="Prompt not found")
    system_prompt = "\n\n".join(p for p in [prompt.intention, prompt.restrictions, prompt.output_structure] if p)
    resolved_system = resolve_placeholders(system_prompt)
    resolved_user = prompt.user_prompt_template.replace("{customer_name}", "John Doe")
    return {"resolved_system_prompt": resolved_system, "resolved_user_template": resolved_user}


@router.get("/{prompt_id}/default")
async def get_default(prompt_id: str):
    """Get the default version for a prompt ID."""
    from app.services.prompts import PromptStore
    store = PromptStore()
    try:
        prompt = store.get_default_prompt(prompt_id)
        if prompt is None:
            raise HTTPException(status_code=404, detail=f"Default prompt '{prompt_id}' not found.")
        return _prompt_to_schema(prompt)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting default for {prompt_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{prompt_id}/{version:int}")
async def get_version(prompt_id: str, version: int):
    """Get a specific version."""
    from app.services.prompts import PromptStore
    store = PromptStore()
    try:
        prompt = store.get_prompt(prompt_id, version)
        if prompt is None:
            raise HTTPException(
                status_code=404,
                detail=f"Prompt '{prompt_id}:v{version}' not found.",
            )
        return _prompt_to_schema(prompt)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting {prompt_id}:v{version}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{prompt_id}")
async def list_versions(prompt_id: str):
    """List all versions for a prompt ID."""
    from app.services.prompts import PromptStore
    store = PromptStore()
    try:
        versions = store.list_prompts(prompt_id)
        if not versions:
            raise HTTPException(status_code=404, detail=f"Prompt '{prompt_id}' not found.")
        return [_prompt_to_schema(v) for v in versions]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing versions for {prompt_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{prompt_id}")
async def create_version(prompt_id: str, body: CreatePromptRequest):
    """Create a new version (auto-increments if prompt_id exists)."""
    from app.services.prompts import PromptStore
    store = PromptStore()
    try:
        # Check if prompt_id already exists to determine if we create v1 or next version
        existing = store.list_prompts(prompt_id)
        next_version = len(existing) + 1 if existing else 1

        prompt = store.create_prompt(
            prompt_id=prompt_id,
            name=body.name,
            intention=body.intention,
            restrictions=body.restrictions,
            output_structure=body.output_structure,
            user_prompt_template=body.user_prompt_template,
            metadata_dict=body.metadata,
        )
        return _prompt_to_schema(prompt)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating {prompt_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{prompt_id}/{version:int}")
async def update_version(prompt_id: str, version: int, body: UpdatePromptRequest):
    """Update an existing version."""
    from app.services.prompts import PromptStore
    store = PromptStore()
    try:
        prompt = store.update_prompt(
            prompt_id=prompt_id,
            version=version,
            name=body.name,
            intention=body.intention,
            restrictions=body.restrictions,
            output_structure=body.output_structure,
            user_prompt_template=body.user_prompt_template,
            metadata_dict=body.metadata,
        )
        return _prompt_to_schema(prompt)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating {prompt_id}:v{version}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{prompt_id}/{version:int}")
async def delete_version(prompt_id: str, version: int):
    """Delete a version."""
    from app.services.prompts import PromptStore
    store = PromptStore()
    try:
        store.delete_prompt(prompt_id, version)
        return {"detail": f"Prompt '{prompt_id}:v{version}' deleted."}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error deleting {prompt_id}:v{version}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{prompt_id}/{version:int}/duplicate")
async def duplicate_version(prompt_id: str, version: int, body: DuplicatePromptRequest | None = None):
    """Duplicate a version, creating the next version."""
    from app.services.prompts import PromptStore
    store = PromptStore()
    try:
        name = body.name if body else None
        prompt = store.duplicate_prompt(prompt_id, version, name=name)
        return _prompt_to_schema(prompt)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error duplicating {prompt_id}:v{version}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{prompt_id}/{version:int}/set-default")
async def set_default_version(prompt_id: str, version: int):
    """Set a specific version as the default."""
    from app.services.prompts import PromptStore
    store = PromptStore()
    try:
        prompt = store.set_default(prompt_id, version)
        return _prompt_to_schema(prompt)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error setting default for {prompt_id}:v{version}: {e}")
        raise HTTPException(status_code=500, detail=str(e))