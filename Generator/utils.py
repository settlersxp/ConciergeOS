#!/usr/bin/env python3
"""
Shared constants and helpers for all Generator scripts.

Provides a single source of truth for:
  - Directory paths (BASE_DIR, PROJECT_ROOT)
  - Database connection initialization (raw sqlite3 and SQLAlchemy session)

Note: DB_PATH and DB_NAME are imported from app.db to avoid duplication.
"""

import os
import sqlite3

from sqlalchemy.orm import Session

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)

# Import DB configuration from app to avoid duplication
from app.db import DB_NAME, DB_PATH


# ---------------------------------------------------------------------------
# Database – raw sqlite3 (legacy scripts)
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


# ---------------------------------------------------------------------------
# Database – SQLAlchemy session (new code)
# ---------------------------------------------------------------------------
def get_session() -> Session:
    """
    Create and return a new SQLAlchemy Session bound to the project database.

    Callers are responsible for closing the session when done.
    """
    from app.db import SessionLocal
    return SessionLocal()