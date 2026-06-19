#!/usr/bin/env python3
"""
Performance testing for query_guest_with_llm().
Runs sequential and concurrent batches, logging results to a SQLite database.
"""

import json
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import requests

# Add project root to path so we can import app modules
_PROJECT_ROOT = Path(__file__).parent.parent

# Import shared prompts from the single source of truth
from app.services.llm import (  # noqa: E402
    SYSTEM_PROMPT as DEFAULT_SYSTEM_PROMPT,
    _fetch_all_guests_and_reservations,
    build_user_prompt,
)


@dataclass
class TestSettings:
    """All configurable settings for a performance test run."""
    customer_name: str = "عائشة إبراهيم"
    vllm_url: str = "http://10.0.0.227:8000/v1"
    models_endpoint: str = "http://10.0.0.227:8000/v1/models"
    database_path: Path = field(default_factory=lambda: Path(__file__).parent.parent / "performance_tests.db")
    sequential_batch_size: int = 5
    concurrent_batch_size: int = 8
    # Model metadata (auto-filled from vLLM API, but editable by user)
    model_name: str = ""
    vllm_version: str = ""
    thinking_enabled: bool = False
    # Prompt settings
    system_prompt: str = DEFAULT_SYSTEM_PROMPT
    user_prompt: str = ""  # If empty, auto-built from customer_name + DB data
    # Response format expectation
    expected_response_format: str = "auto"  # "json", "text", or "auto"


# ── Database setup ───────────────────────────────────────────────────────────

def init_database(db_path: Path) -> sqlite3.Connection:
    """Create the performance_tests database and return a connection."""
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS test_results (
            id                     INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id                 INTEGER,
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
            response_content       TEXT
        )
        """
    )
    conn.commit()
    return conn


_db_lock = threading.Lock()


def log_result(
    db_path: Path,
    run_id: int,
    batch_type: str,
    request_index: int,
    settings: TestSettings,
    response: str,
    request_sent_time: str,
    response_received_time: str,
) -> None:
    """Insert a single test result into the database (thread-safe)."""
    context_length = len(settings.system_prompt) + len(settings.user_prompt)

    # Detect response format
    response_format = settings.expected_response_format
    json_malformed: Optional[bool] = None

    stripped = response.strip()

    if response_format == "auto":
        # Auto-detect: if response starts with { or [, treat as JSON
        if stripped.startswith("{") or stripped.startswith("["):
            response_format = "JSON"
            try:
                json.loads(stripped)
                json_malformed = False
            except (json.JSONDecodeError, ValueError):
                json_malformed = True
        else:
            response_format = "TEXT"
    elif response_format == "json":
        response_format = "JSON"
        try:
            json.loads(stripped)
            json_malformed = False
        except (json.JSONDecodeError, ValueError):
            json_malformed = True
    else:
        response_format = "TEXT"

    response_length = len(response)

    sql = """
        INSERT INTO test_results (
            run_id, batch_type, request_index, model_name, context_length,
            vllm_version, thinking_enabled, system_prompt, user_prompt,
            response_format, json_malformed, response_length,
            request_sent_time, response_received_time, response_content
        ) VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
    """

    with _db_lock:
        conn = sqlite3.connect(str(db_path))
        conn.execute(sql, (
            run_id,
            batch_type,
            request_index,
            settings.model_name,
            context_length,
            settings.vllm_version,
            settings.thinking_enabled,
            settings.system_prompt,
            settings.user_prompt,
            response_format,
            json_malformed,
            response_length,
            request_sent_time,
            response_received_time,
            response,
        ))
        conn.commit()
        conn.close()


# ── Model info retrieval ────────────────────────────────────────────────────

def fetch_model_info(url: str) -> dict[str, Any]:
    """Fetch loaded model information from the vLLM /v1/models endpoint."""
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    data = resp.json()

    models = data.get("data", [])
    if not models:
        return {"model_name": "unknown", "vllm_version": "unknown", "thinking_enabled": False}

    model = models[0]
    model_name = model.get("id", model.get("model", "unknown"))

    # Try to extract vllm version from various possible fields
    vllm_version = model.get("vllm_version", "")
    if not vllm_version:
        vllm_version = (
            model.get("extra", {}).get("vllm_version", "unknown")
            if isinstance(model.get("extra"), dict)
            else "unknown"
        )

    # Check if thinking is enabled
    thinking_enabled = False
    capabilities = model.get("capabilities", {})
    if isinstance(capabilities, dict):
        thinking_enabled = capabilities.get("thinking", False)
    model_type = model.get("type", "")
    if "thinking" in str(model_type).lower():
        thinking_enabled = True

    return {
        "model_name": model_name,
        "vllm_version": vllm_version,
        "thinking_enabled": thinking_enabled,
    }


# ── LLM query wrapper ───────────────────────────────────────────────────────

def _build_user_prompt(customer_name: str) -> str:
    """Build the full user prompt with embedded DB data (delegates to shared function)."""
    data = _fetch_all_guests_and_reservations()
    return build_user_prompt(customer_name, data)


def _query_guest_with_llm(settings: TestSettings) -> str:
    """Query the LLM using the provided settings."""
    from openai import OpenAI

    client = OpenAI(
        base_url=settings.vllm_url,
        api_key="none",
    )

    model_name = settings.model_name or "Qwen/Qwen3.6-27B"
    user_prompt = settings.user_prompt or _build_user_prompt(settings.customer_name)

    response = client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "system", "content": settings.system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0,
        max_tokens=4096,
    )

    return response.choices[0].message.content or "The LLM returned an empty response."


# ── Single request execution ────────────────────────────────────────────────

def run_single_request(
    batch_type: str,
    request_index: int,
    run_id: int,
    settings: TestSettings,
    db_path: Path,
) -> dict[str, Any]:
    """Execute a single LLM query and log the result."""
    # Store the resolved user_prompt on settings for logging
    if not settings.user_prompt:
        settings.user_prompt = _build_user_prompt(settings.customer_name)

    request_sent_time = datetime.now(timezone.utc).isoformat()
    response = _query_guest_with_llm(settings)
    response_received_time = datetime.now(timezone.utc).isoformat()

    log_result(
        db_path=db_path,
        run_id=run_id,
        batch_type=batch_type,
        request_index=request_index,
        settings=settings,
        response=response,
        request_sent_time=request_sent_time,
        response_received_time=response_received_time,
    )

    elapsed = (
        datetime.fromisoformat(response_received_time)
        - datetime.fromisoformat(request_sent_time)
    ).total_seconds()

    return {
        "batch_type": batch_type,
        "request_index": request_index,
        "elapsed": round(elapsed, 2),
    }


# ── Batch runners ────────────────────────────────────────────────────────────

def run_sequential_batch(run_id: int, settings: TestSettings, db_path: Path) -> list[dict]:
    """Run sequential requests back to back."""
    results: list[dict] = []
    for i in range(settings.sequential_batch_size):
        result = run_single_request("sequential", i + 1, run_id, settings, db_path)
        results.append(result)
        print(f"  [sequential] Request {i + 1} completed in {result['elapsed']}s")
    return results


def run_concurrent_batch(run_id: int, settings: TestSettings, db_path: Path) -> list[dict]:
    """Run concurrent requests simultaneously using threads."""
    results: list[dict] = []
    with ThreadPoolExecutor(max_workers=settings.concurrent_batch_size) as executor:
        futures = {
            executor.submit(
                run_single_request, "concurrent", i + 1, run_id, settings, db_path
            ): i + 1
            for i in range(settings.concurrent_batch_size)
        }
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            print(f"  [concurrent] Request {result['request_index']} completed in {result['elapsed']}s")
    return results


# ── Public entry point ──────────────────────────────────────────────────────

def get_next_run_id(db_path: Path) -> int:
    """Get the next run_id from the database."""
    conn = sqlite3.connect(str(db_path))
    cursor = conn.execute("SELECT MAX(run_id) FROM test_results")
    row = cursor.fetchone()
    conn.close()
    return (row[0] or 0) + 1


def run_tests(settings: Optional[TestSettings] = None) -> dict[str, Any]:
    """
    Main entry point for running performance tests.
    Can be called from CLI or from the web API.
    """
    if settings is None:
        settings = TestSettings()

    db_path = settings.database_path

    # Initialize database
    conn = init_database(db_path)
    conn.close()

    # Fetch model info if not set by user
    if not settings.model_name:
        try:
            model_info = fetch_model_info(settings.models_endpoint)
            if not settings.model_name:
                settings.model_name = model_info.get("model_name", "unknown")
            if not settings.vllm_version:
                settings.vllm_version = model_info.get("vllm_version", "unknown")
            if not settings.thinking_enabled:
                settings.thinking_enabled = model_info.get("thinking_enabled", False)
        except Exception as e:
            print(f"Warning: Could not fetch model info: {e}")

    run_id = get_next_run_id(db_path)

    print("Performance Testing for query_guest_with_llm()")
    print(f"  Run ID: {run_id}")
    print(f"  Customer: {settings.customer_name}")
    print(f"  Model: {settings.model_name}")
    print(f"  vLLM Version: {settings.vllm_version}")
    print(f"  Thinking Enabled: {settings.thinking_enabled}")
    print(f"  Sequential: {settings.sequential_batch_size}, Concurrent: {settings.concurrent_batch_size}")
    print(f"  Database: {db_path}")

    # Run batches
    print(f"\n{'=' * 60}")
    print(f"Sequential Batch: {settings.sequential_batch_size} requests")
    print(f"{'=' * 60}")
    seq_results = run_sequential_batch(run_id, settings, db_path)

    print(f"\n{'=' * 60}")
    print(f"Concurrent Batch: {settings.concurrent_batch_size} requests")
    print(f"{'=' * 60}")
    conc_results = run_concurrent_batch(run_id, settings, db_path)

    print(f"\n{'=' * 60}")
    print("All tests completed.")
    print(f"{'=' * 60}")

    return {
        "run_id": run_id,
        "model_name": settings.model_name,
        "vllm_version": settings.vllm_version,
        "thinking_enabled": settings.thinking_enabled,
        "sequential_results": seq_results,
        "concurrent_results": conc_results,
        "total_requests": len(seq_results) + len(conc_results),
    }


# ── CLI entry point ─────────────────────────────────────────────────────────

def main() -> None:
    run_tests()


if __name__ == "__main__":
    main()