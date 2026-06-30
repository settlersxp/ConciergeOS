#!/usr/bin/env python3
"""
Performance testing for query_guest_with_llm().

This module is the orchestration layer that coordinates performance test
runs.  For multi-guest mode, all LLM calls are delegated to
``app.services.llm.query_guest_with_llm()`` so that prompt resolution,
placeholder substitution, tool calling, and caching are handled identically
to the Guest Search flow.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Optional

# Add the backend directory to sys.path so `from app.xxx` imports work
_BACKEND_DIR = str(Path(__file__).resolve().parent.parent)
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from .batch_runners import (
    run_concurrent_batch_multi_guest,
    run_sequential_batch_multi_guest,
)
from .db import PerformanceTestLogger, ensure_database, get_next_run_id
from .model_info import fetch_model_info
from .settings import TestSettings

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

# Configure logging at the root PerformanceTesting package level so ALL
# child loggers (batch_runners, db, model_info, etc.) share the same
# handler and their output becomes visible.
_pt_logger = logging.getLogger("PerformanceTesting")
_pt_logger.setLevel(logging.INFO)

# Add a console handler once (avoid duplicates across repeated imports)
if not _pt_logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    )
    _pt_logger.addHandler(_handler)

# The module-level logger for this file
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_tests(settings: Optional[TestSettings] = None) -> dict[str, object]:
    """
    Main entry point for running performance tests.

    In multi-guest mode (settings.guest_names is non-empty and settings.prompt_id
    is set), all LLM calls use ``app.services.llm.query_guest_with_llm()``.
    """
    if settings is None:
        settings = TestSettings()

    db_path = settings.database_path

    # Ensure database schema exists
    ensure_database(db_path)

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
            logger.warning("Could not fetch model info: %s", e)

    run_id = get_next_run_id(db_path)

    # Create the injected performance logger
    perf_logger = PerformanceTestLogger(db_path=db_path)

    separator = "=" * 60

    logger.info("%s", separator)
    logger.info("Performance Testing for query_guest_with_llm()")
    logger.info("  Run ID: %s", run_id)
    logger.info("  Test Mode: %s", settings.test_mode)
    logger.info("  Customer: %s", settings.customer_name)
    logger.info("  Model: %s", settings.model_name)
    logger.info("  vLLM Version: %s", settings.vllm_version)
    logger.info("  Thinking Enabled: %s", settings.thinking_enabled)
    logger.info("  Data Format: %s", settings.data_format)
    logger.info("  Sequential: %d, Concurrent: %d",
                settings.sequential_batch_size, settings.concurrent_batch_size)
    logger.info("  Database: %s", db_path)
    logger.info("  PROMPT_ID: '%s'", settings.prompt_id)
    logger.info("  PROMPT_VERSION: %s", settings.prompt_version)
    logger.info("  GUEST_NAMES: %s", settings.guest_names[:5] if len(settings.guest_names) > 5 else settings.guest_names)

    # Validate multi-guest configuration
    if not settings.guest_names:
        logger.error("[FATAL] guest_names is empty. Performance testing requires test guests.")
        logger.error("[FATAL] Run the setup endpoint first: POST /api/performance-testing/setup-guests")
        return {
            "run_id": run_id,
            "batch_uuid": settings.batch_uuid,
            "friendly_name": settings.friendly_name,
            "model_name": settings.model_name,
            "vllm_version": settings.vllm_version,
            "thinking_enabled": settings.thinking_enabled,
            "sequential_results": [],
            "concurrent_results": [],
            "total_requests": 0,
            "error": "guest_names is empty. Run setup-guests first.",
        }

    if not settings.prompt_id:
        logger.warning("[WARN] prompt_id is not set. query_guest_with_llm() will default to 'guest-search'.")

    logger.info("  Multi-guest mode: %d guests configured", len(settings.guest_names))
    seq_guests = settings.guest_names[:settings.sequential_batch_size]
    conc_guests_start = settings.sequential_batch_size
    conc_guests_end = conc_guests_start + settings.concurrent_batch_size
    conc_guests = settings.guest_names[conc_guests_start:conc_guests_end]
    logger.info("  Sequential guests: %s", ", ".join(seq_guests))
    logger.info("  Concurrent guests: %s", ", ".join(conc_guests))

    # --- Sequential batch (multi-guest) ---
    logger.info("\n%s", separator)
    logger.info("Sequential Batch (Multi-Guest): %d requests", settings.sequential_batch_size)
    logger.info("%s", separator)

    try:
        seq_results = run_sequential_batch_multi_guest(
            run_id, settings, perf_logger, settings.guest_names
        )
    except Exception as exc:
        logger.error("[FATAL] Sequential batch failed with exception: %s", exc, exc_info=True)
        seq_results = []

    # --- Concurrent batch (multi-guest) ---
    logger.info("\n%s", separator)
    logger.info("Concurrent Batch (Multi-Guest): %d requests", settings.concurrent_batch_size)
    logger.info("%s", separator)

    try:
        conc_results = run_concurrent_batch_multi_guest(
            run_id, settings, perf_logger, settings.guest_names
        )
    except Exception as exc:
        logger.error("[FATAL] Concurrent batch failed with exception: %s", exc, exc_info=True)
        conc_results = []

    logger.info("\n%s", separator)
    logger.info("All tests completed.")
    logger.info("  Sequential results: %d", len(seq_results))
    logger.info("  Concurrent results: %d", len(conc_results))
    logger.info("  Total requests: %d", len(seq_results) + len(conc_results))
    logger.info("%s", separator)

    return {
        "run_id": run_id,
        "batch_uuid": settings.batch_uuid,
        "friendly_name": settings.friendly_name,
        "model_name": settings.model_name,
        "vllm_version": settings.vllm_version,
        "thinking_enabled": settings.thinking_enabled,
        "sequential_results": seq_results,
        "concurrent_results": conc_results,
        "total_requests": len(seq_results) + len(conc_results),
    }


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    run_tests()


if __name__ == "__main__":
    main()