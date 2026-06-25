"""Batch runners for performance testing.

Provides both sequential and concurrent batch execution, for single-guest
and multi-guest modes.  All logging delegation is handled by
``executors.execute_and_log``.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from .db import PerformanceTestLogger
from .executors import _execute_and_log
from .settings import BATCH_TYPE_CONCURRENT, BATCH_TYPE_SEQUENTIAL, TestSettings

logger = logging.getLogger(__name__)


# ── Guest selection helper ──────────────────────────────────────────────────


def _select_guest(guest_names: list[str], index: int) -> str:
    """Return the guest name at *index*, falling back to the last guest."""
    if guest_names and index < len(guest_names):
        return guest_names[index]
    return guest_names[-1] if guest_names else "unknown"


# ── Single-guest batch runners ──────────────────────────────────────────────


def run_sequential_batch(
    run_id: int,
    settings: TestSettings,
    perf_logger: PerformanceTestLogger,
) -> list[dict[str, Any]]:
    """Run sequential requests back to back (single-guest mode)."""
    results: list[dict[str, Any]] = []
    for i in range(settings.sequential_batch_size):
        result = _execute_and_log(
            BATCH_TYPE_SEQUENTIAL, i + 1, run_id, settings, perf_logger
        )
        results.append(result)
        logger.info("  [sequential] Request %d completed in %.2fs", i + 1, result["elapsed"])
    return results


def run_concurrent_batch(
    run_id: int,
    settings: TestSettings,
    perf_logger: PerformanceTestLogger,
) -> list[dict[str, Any]]:
    """Run concurrent requests simultaneously using threads (single-guest mode)."""
    results: list[dict[str, Any]] = []
    max_workers = settings.concurrent_batch_size
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(
                _execute_and_log,
                BATCH_TYPE_CONCURRENT, i + 1, run_id, settings, perf_logger,
            ): i + 1
            for i in range(settings.concurrent_batch_size)
        }
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            logger.info(
                "  [concurrent] Request %d completed in %.2fs",
                result["request_index"],
                result["elapsed"],
            )
    return results


# ── Multi-guest batch runners ───────────────────────────────────────────────


def run_sequential_batch_multi_guest(
    run_id: int,
    settings: TestSettings,
    perf_logger: PerformanceTestLogger,
    guest_names: list[str],
) -> list[dict[str, Any]]:
    """Run sequential requests, each querying a different guest.

    Uses the first ``sequential_batch_size`` guests from the provided list.
    """
    results: list[dict[str, Any]] = []
    for i in range(settings.sequential_batch_size):
        customer_name = _select_guest(guest_names, i)
        result = _execute_and_log(
            BATCH_TYPE_SEQUENTIAL, i + 1, run_id, settings, perf_logger,
            customer_name=customer_name,
        )
        results.append(result)
        logger.info(
            "  [sequential] Request %d (guest: %s) completed in %.2fs",
            i + 1, customer_name, result["elapsed"],
        )
    return results


def run_concurrent_batch_multi_guest(
    run_id: int,
    settings: TestSettings,
    perf_logger: PerformanceTestLogger,
    guest_names: list[str],
) -> list[dict[str, Any]]:
    """Run concurrent requests, each querying a different guest.

    Uses guests starting at index ``sequential_batch_size`` (i.e., the guests
    assigned to the concurrent batch).
    """
    results: list[dict[str, Any]] = []
    seq_count = settings.sequential_batch_size
    conc_count = settings.concurrent_batch_size

    with ThreadPoolExecutor(max_workers=conc_count) as executor:
        futures = {
            executor.submit(
                _execute_and_log,
                BATCH_TYPE_CONCURRENT,
                i + 1,
                run_id,
                settings,
                perf_logger,
                customer_name=_select_guest(guest_names, seq_count + i),
            ): i + 1
            for i in range(conc_count)
        }
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            logger.info(
                "  [concurrent] Request %d (guest: %s) completed in %.2fs",
                result["request_index"],
                result.get("customer_name", "?"),
                result["elapsed"],
            )
    return results