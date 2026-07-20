#!/usr/bin/env python3
"""Seed data for chain pages (PromptGroup with is_chain_page=True).

Creates PromptGroups that act as configurable page templates,
each linked to a specific URL route.
"""

import sys
from pathlib import Path

# Add backend dir to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import SessionLocal
from app.models import PromptGroup, PromptGroupItem
from sqlalchemy import text


def seed_guest_intelligence_chain(db):
    """Create the Guest Intelligence chain with 2 prompts."""

    # Check if already seeded
    existing = db.query(PromptGroup).filter(
        PromptGroup.page_route == "/guest-intel"
    ).first()
    if existing:
        print(f"Already seeded: group_id={existing.group_id}")
        return existing

    # Find the default prompt IDs from the database
    search_version = db.execute(text("""
        SELECT version FROM "PromptVersions"
        WHERE prompt_id = 'guest-search' AND is_default = true
        LIMIT 1
    """)).first()

    intelligence_version = db.execute(text("""
        SELECT version FROM "PromptVersions"
        WHERE prompt_id = 'guest-intelligence' AND is_default = true
        LIMIT 1
    """)).first()

    if not search_version:
        search_version = db.execute(text("""
            SELECT version FROM "PromptVersions"
            WHERE prompt_id = 'guest-search'
            LIMIT 1
        """)).first()
        if not search_version:
            raise ValueError("No guest-search prompt found in the database")

    if not intelligence_version:
        raise ValueError("No guest-intelligence prompt found in the database")

    print(f"Using guest-search:v{search_version.version} and guest-intelligence:v{intelligence_version.version}")

    # Create the group
    group = PromptGroup(
        name="Guest Intelligence",
        description="Comprehensive guest profile and preference analysis",
        is_active=True,
        is_chain_page=True,
        page_route="/guest-intel",
    )
    db.add(group)
    db.commit()
    db.refresh(group)

    # Step 1: Search for guest
    db.add(PromptGroupItem(
        group_id=group.group_id,
        position=1,
        prompt_id="guest-search",
        prompt_version=search_version.version,
        alias="search",
        is_input_step=True,
    ))

    # Step 2: Intelligence / profile enrichment
    db.add(PromptGroupItem(
        group_id=group.group_id,
        position=2,
        prompt_id="guest-intelligence",
        prompt_version=intelligence_version.version,
        alias="intelligence",
    ))

    db.commit()

    print(f"Seeded Guest Intelligence chain:")
    print(f"  group_id: {group.group_id}")
    print(f"  is_chain_page: {group.is_chain_page}")
    print(f"  page_route: {group.page_route}")
    print(f"  items:")
    for item in group.items:
        print(f"    - position={item.position} prompt_id={item.prompt_id}:v{item.prompt_version} alias={item.alias} is_input_step={item.is_input_step}")

    return group


def seed_example_chain(db):
    """Create a simple example chain to demonstrate the concept."""

    # Check if already seeded
    existing = db.query(PromptGroup).filter(
        PromptGroup.page_route == "/hello"
    ).first()
    if existing:
        print(f"Already seeded: group_id={existing.group_id}")
        return existing

    # Find the default prompt version
    default_version = db.execute(text("""
        SELECT prompt_id, version FROM "PromptVersions"
        WHERE is_default = true
        LIMIT 1
    """)).first()
    if not default_version:
        print("No default prompt found, skipping example chain")
        return None

    print(f"Using default prompt: {default_version.prompt_id}:v{default_version.version}")

    group = PromptGroup(
        name="Hello World",
        description="A simple chain that says hello",
        is_active=True,
        is_chain_page=True,
        page_route="/hello",
    )
    db.add(group)
    db.commit()
    db.refresh(group)

    db.add(PromptGroupItem(
        group_id=group.group_id,
        position=1,
        prompt_id=default_version.prompt_id,
        prompt_version=default_version.version,
        alias="hello",
        is_input_step=True,
    ))

    db.commit()

    print(f"Seeded Hello World chain: group_id={group.group_id}, route=/hello")
    return group


def main():
    db = SessionLocal()
    try:
        seed_guest_intelligence_chain(db)
        seed_example_chain(db)
        print("\nDone! Chain pages are ready.")
        print("  Guest Intelligence: /prompt-chains/guest-intel")
        print("  Hello World: /prompt-chains/hello")
    finally:
        db.close()


if __name__ == "__main__":
    main()