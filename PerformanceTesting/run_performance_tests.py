#!/usr/bin/env python3
"""
Performance testing for query_guest_with_llm().

This module is the orchestration layer that coordinates performance test
runs.  Detailed logic is delegated to focused sub-modules:

- :mod:`.settings` – Configuration and constants
- :mod:`.model_info` – Model metadata from vLLM
- :mod:`.tool_executors` – Database query executors for tool calling
- :mod:`.prompt_builders` – System/user prompt resolution
- :mod:`.llm_client` – LLM communication (chat + tool calling)
- :mod:`.executors` – Single-request execute-and-log flow
- :mod:`.batch_runners` – Sequential/concurrent batch execution
- :mod:`.db` – SQLite persistence (PerformanceTestLogger)
"""

from __future__ import annotations

import logging
from typing import Optional

from .batch_runners import (
    run_concurrent_batch,
    run_concurrent_batch_multi_guest,
    run_sequential_batch,
    run_sequential_batch_multi_guest,
)
from .db import PerformanceTestLogger, ensure_database, get_next_run_id
from .model_info import fetch_model_info
from .settings import TestSettings


# ── Logging ───────────────────────────────────────────────────────────────────

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Add a console handler if none exists (avoids duplicates on repeated imports)
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    )
    logger.addHandler(_handler)


# ── Public entry point ──────────────────────────────────────────────────────

def run_tests(settings: Optional[TestSettings] = None) -> dict[str, object]:
    """
    Main entry point for running performance tests.
    Can be called from CLI or from the web API.

    The database schema is ensured before tests start, and a
    :class:`~PerformanceTesting.db.PerformanceTestLogger` is injected into
    the batch runners so the testing logic remains storage-agnostic.
    """
    if settings is None:
        settings = TestSettings()

    db_path = settings.database_path

    # Ensure database schema exists (decoupled init)
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
    logger.info(
        "  Sequential: %d, Concurrent: %d",
        settings.sequential_batch_size,
        settings.concurrent_batch_size,
    )
    logger.info("  Database: %s", db_path)

    # Run batches based on test mode
    if settings.test_mode == "multi" and settings.guest_names:
        guest_names = settings.guest_names
        logger.info("  Multi-guest mode: %d guests configured", len(guest_names))
        seq_guests = guest_names[: settings.sequential_batch_size]
        conc_guests = guest_names[
            settings.sequential_batch_size:
            settings.sequential_batch_size + settings.concurrent_batch_size
        ]
        logger.info("  Sequential guests: %s", ", ".join(seq_guests))
        logger.info("  Concurrent guests: %s", ", ".join(conc_guests))

        logger.info("\n%s", separator)
        logger.info("Sequential Batch (Multi-Guest): %d requests", settings.sequential_batch_size)
        logger.info("%s", separator)
        seq_results = run_sequential_batch_multi_guest(run_id, settings, perf_logger, guest_names)

        logger.info("\n%s", separator)
        logger.info("Concurrent Batch (Multi-Guest): %d requests", settings.concurrent_batch_size)
        logger.info("%s", separator)
        conc_results = run_concurrent_batch_multi_guest(run_id, settings, perf_logger, guest_names)
    else:
        # Default single-guest mode
        logger.info("\n%s", separator)
        logger.info("Sequential Batch: %d requests", settings.sequential_batch_size)
        logger.info("%s", separator)
        seq_results = run_sequential_batch(run_id, settings, perf_logger)

        logger.info("\n%s", separator)
        logger.info("Concurrent Batch: %d requests", settings.concurrent_batch_size)
        logger.info("%s", separator)
        conc_results = run_concurrent_batch(run_id, settings, perf_logger)

    logger.info("\n%s", separator)
    logger.info("All tests completed.")
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


# ── CLI entry point ─────────────────────────────────────────────────────────

def main() -> None:
    run_tests()


if __name__ == "__main__":
    main()