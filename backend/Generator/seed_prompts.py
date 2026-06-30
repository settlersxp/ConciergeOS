#!/usr/bin/env python3
"""
Seed the PromptVersions table with default prompts on first run.

This is part of the database population pipeline. It creates the table if it
doesn't exist and inserts initial prompt data if the table is empty.

Usage:
    python Generator/seed_prompts.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.db import engine
from app.services.prompts import PromptStore


def main():
    print("[*] Running prompt version seeding...")

    store = PromptStore()

    # Ensure the table exists
    store.create_all_tables(engine)

    # Seed default prompts only if the table is empty
    store.seed_default_prompts()

    print("[+] Prompt version seeding completed successfully.")


if __name__ == "__main__":
    main()
