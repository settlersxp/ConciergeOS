#!/usr/bin/env python3
"""
Database initialization and result logging for performance tests.

Provides a standalone SQLite schema and thread-safe result logging
that can be used independently of the performance testing logic.
"""

import sqlite3
import threading
import json
from pathlib import Path
from typing import Optional


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS test_results (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id                 INTEGER,
    batch_uuid             TEXT    NOT NULL DEFAULT '',
    friendly_name          TEXT    DEFAULT '',
    batch_type             TEXT    NOT NULL,
    request_index          INTEGER NOT NULL,
    model_name             TEXT,
    context_length         INTEGER,
    vllm_version           TEXT,
    thinking_enabled       BOOLEAN,
    system_prompt          TEXT,
    user_prompt            TEXT,
    response_format        TEXT,
    json_malformed         BOOLEAN,
    response_length        INTEGER,
    request_sent_time      DATETIME,
    response_received_time DATETIME,
    response_content       TEXT,
    valid_response         BOOLEAN
)
"""

_db_lock = threading.Lock()


def init_database(db_path: Path) -> sqlite3.Connection:
    """Create the performance_tests database schema and return a connection.

    The table is created (if it does not exist) and WAL journal mode is
    enabled. The caller is responsible for closing the returned connection
    or reusing it.
    """
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(SCHEMA_SQL)
    conn.commit()
    return conn


def ensure_database(db_path: Path) -> None:
    """Create the database schema if it does not exist.

    A convenience helper for callers that manage their own connections.
    Opens a temporary connection, creates the table, and closes it.
    """
    conn = init_database(db_path)
    conn.close()


def get_next_run_id(db_path: Path) -> int:
    """Return the next auto-incremented run_id."""
    conn = sqlite3.connect(str(db_path))
    cursor = conn.execute("SELECT MAX(run_id) FROM test_results")
    row = cursor.fetchone()
    conn.close()
    return (row[0] or 0) + 1


# ── Result logging ──────────────────────────────────────────────────────────

class PerformanceTestLogger:
    """Thread-safe logger that writes performance test results to SQLite.

    Can be constructed with an existing connection (for shared-pool scenarios)
    or with a path (each call opens its own short-lived connection under a
    lock).
    """

    def __init__(self, db_path: Optional[Path] = None, connection: Optional[sqlite3.Connection] = None):
        self._db_path = db_path
        self._connection = connection
        # When a path is given we use the module-level lock for safety.
        # When a shared connection is given the caller is expected to
        # coordinate concurrent access (or rely on SQLite's own locking).

    def log(
        self,
        run_id: int,
        batch_uuid: str,
        friendly_name: str,
        batch_type: str,
        request_index: int,
        model_name: str,
        vllm_version: str,
        thinking_enabled: bool,
        system_prompt: str,
        user_prompt: str,
        expected_response_format: str,
        response: str,
        request_sent_time: str,
        response_received_time: str,
    ) -> None:
        """Insert a single performance test result (thread-safe)."""
        context_length = len(system_prompt) + len(user_prompt)
        response_format, json_malformed = _classify_response(response, expected_response_format)
        response_length = len(response)

        sql = """
            INSERT INTO test_results (
                run_id, batch_uuid, friendly_name, batch_type, request_index, model_name,
                context_length, vllm_version, thinking_enabled, system_prompt, user_prompt,
                response_format, json_malformed, response_length,
                request_sent_time, response_received_time, response_content
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
        """

        params = (
            run_id,
            batch_uuid,
            friendly_name,
            batch_type,
            request_index,
            model_name,
            context_length,
            vllm_version,
            thinking_enabled,
            system_prompt,
            user_prompt,
            response_format,
            json_malformed,
            response_length,
            request_sent_time,
            response_received_time,
            response,
        )

        if self._connection is not None:
            # Shared connection path – assume caller handles concurrency
            self._connection.execute(sql, params)
            self._connection.commit()
        else:
            # Short-lived connection path – protected by module lock
            with _db_lock:
                conn = sqlite3.connect(str(self._db_path))
                conn.execute(sql, params)
                conn.commit()
                conn.close()


def _classify_response(response: str, expected_format: str) -> tuple[str, Optional[bool]]:
    """Determine the response format and whether JSON is malformed.

    Returns:
        A tuple of (response_format_label, json_malformed_flag).
        ``response_format_label`` is ``"JSON"`` or ``"TEXT"``.
        ``json_malformed_flag`` is True/False when the format is JSON,
        otherwise None.
    """
    stripped = response.strip()

    if expected_format == "auto":
        if stripped.startswith("{") or stripped.startswith("["):
            response_format = "JSON"
            try:
                json.loads(stripped)
                json_malformed = False
            except (json.JSONDecodeError, ValueError):
                json_malformed = True
        else:
            response_format = "TEXT"
            json_malformed = None
    elif expected_format == "json":
        response_format = "JSON"
        try:
            json.loads(stripped)
            json_malformed = False
        except (json.JSONDecodeError, ValueError):
            json_malformed = True
    else:
        response_format = "TEXT"
        json_malformed = None

    return response_format, json_malformed