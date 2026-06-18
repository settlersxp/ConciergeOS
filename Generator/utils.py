#!/usr/bin/env python3
"""
Shared constants and helpers for all Generator scripts.

Provides a single source of truth for:
  - Directory paths (BASE_DIR, PROJECT_ROOT)
  - Database location (DB_NAME, DB_PATH)
  - Database connection initialization
"""

import os
import sqlite3

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
DB_NAME = "hotel.db"
DB_PATH = os.path.join(PROJECT_ROOT, DB_NAME)


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
def init_connection(db_path: str | None = None) -> sqlite3.Connection:
    """
    Open a SQLite connection with foreign keys enforced and WAL journal mode.

    By default connects to the project's hotel.db (DB_PATH).
    Pass a custom *db_path* to override.
    """
    path = db_path or DB_PATH
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn