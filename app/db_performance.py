#!/usr/bin/env python3
"""
SQLAlchemy database engine and session management for the performance_tests database.

Kept separate from app/db.py (hotel.db) to cleanly isolate the two databases.
"""

from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
PERFORMANCE_DB_PATH = str(_PROJECT_ROOT / "performance_tests.db")

# ---------------------------------------------------------------------------
# Engine & Session
# ---------------------------------------------------------------------------
performance_engine = create_engine(
    f"sqlite:///{PERFORMANCE_DB_PATH}",
    connect_args={"check_same_thread": False},
)

PerformanceSessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=performance_engine
)


def get_performance_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a performance_tests database session."""
    db = PerformanceSessionLocal()
    try:
        yield db
    finally:
        db.close()