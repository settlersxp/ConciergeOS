#!/usr/bin/env python3
"""
Shared constants and helpers for all Generator scripts.

Provides a single source of truth for:
  - Directory paths (BASE_DIR, PROJECT_ROOT)
  - Database connection initialization (raw sqlite3 and SQLAlchemy session)

All other shared utilities (name parsing, date helpers, booking mappings,
date classification) are re-exported from ``app.services.generator_utils``
so that the main app can import from the same source of truth.

Generator scripts import via: ``from utils import ...``
The app imports via:           ``from app.services.generator_utils import ...``
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
# Re-export shared utilities from app.services.generator_utils
# so Generator scripts can use ``from utils import ...``
# ---------------------------------------------------------------------------
from app.services.generator_utils import (
    CHANNEL_TIMES_MAP,
    WING_CHANNEL_MAP,
    DEFAULT_BUCKET_RANGES,
    DEFAULT_BUCKET_WEIGHTS,
    booking_channel_to_source,
    generate_random_dob,
    get_bucket_dates,
    get_booking_channel,
    get_checkin_checkout_times,
    is_checked_in_type,
    is_checked_out_type,
    is_confirmed_type,
    split_name,
    weighted_random_bucket,
    classify_reservation_type,
)


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