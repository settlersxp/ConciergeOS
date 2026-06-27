"""Batch runners for performance testing.

This module ONLY supports multi-guest mode and always delegates to
``app.services.llm.query_guest_with_llm()`` so that prompt resolution,
placeholder substitution, tool calling, and caching are handled identically
to the Guest Search flow.

No legacy code paths exist - if something is misconfigured, the code will
fail loudly with detailed logging.
"""

from __future__ import annotations

import copy
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any
import time

from .db import PerformanceTestLogger
from .settings import BATCH_TYPE_CONCURRENT, BATCH_TYPE_SEQUENTIAL, TestSettings

logger = logging.getLogger(__name__)

# Default runtime variable key used by the frontend
_RUNTIME_VAR_KEY = "customer_name"


# ---------------------------------------------------------------------------
# Guest selection helper
# ---------------------------------------------------------------------------


def _select_guest(guest_names: list[str], index: int) -> str:
    """Return the guest name at *index*, falling back to the last guest."""
    if guest_names and index < len(guest_names):
        return guest_names[index]
    logger.warning("Index %d out of range for %d guests, using last guest", index, len(guest_names))
    return guest_names[-1] if guest_names else "UNKNOWN"


# ---------------------------------------------------------------------------
# Runtime variables helper
# ---------------------------------------------------------------------------


def _build_guest_runtime_variables(customer_name: str, settings: TestSettings) -> dict[str, str]:
    """Build runtime_variables for a specific guest, overriding the customer name key."""
    base_vars = settings.runtime_variables or {}
    # Merge base variables and override with this guest's name
    vars_copy = copy.deepcopy(base_vars)
    # Set the runtime variable key to this guest's name so the cache key differs per guest
    if _RUNTIME_VAR_KEY in vars_copy:
        vars_copy[_RUNTIME_VAR_KEY] = customer_name
    else:
        # If the key doesn't exist in base vars, add it
        vars_copy[_RUNTIME_VAR_KEY] = customer_name
    return vars_copy


# ---------------------------------------------------------------------------
# Core LLM call - always uses query_guest_with_llm
# ---------------------------------------------------------------------------


def _call_guest_llm(customer_name: str, settings: TestSettings) -> tuple[str, bool]:
    """Call app.services.llm.query_guest_with_llm for a single guest.

    This is the single shared entry point that guarantees identical behaviour
    between the Guest Search page and Performance Testing.
    """
    from app.services.llm import query_guest_with_llm

    # Build per-guest runtime variables so cache keys differ per guest
    guest_vars = _build_guest_runtime_variables(customer_name, settings)

    logger.info(
        "[LLM CALL] guest='%s' | prompt_id='%s' | version=%s | runtime_vars=%s",
        customer_name,
        settings.prompt_id,
        settings.prompt_version,
        list(guest_vars.keys())[:10],  # truncate long lists
    )

    result, was_cached = query_guest_with_llm(
        customer_name,
        prompt_id=settings.prompt_id or "guest-search",
        version=settings.prompt_version,
        runtime_variables=guest_vars or None,
    )

    logger.info(
        "[LLM CALL DONE] guest='%s' | cached=%s | response_len=%d",
        customer_name,
        was_cached,
        len(result) if result else 0,
    )

    return result, was_cached


# ---------------------------------------------------------------------------
# Database logging helper
# ---------------------------------------------------------------------------


def _log_to_perf_db(
    perf_logger: PerformanceTestLogger,
    run_id: int,
    settings: TestSettings,
    batch_type: str,
    request_index: int,
    customer_name: str,
    response: str,
    was_cached: bool,
    request_sent_time: str,
    response_received_time: str,
) -> None:
    """Log a single result to the performance test database.

    Always logs the result regardless of whether it was cached.
    """
    status_label = "CACHED" if was_cached else "LIVE"
    logger.info(
        "[DB LOG] Writing result #%d | guest='%s' | status=%s | response_len=%d | batch=%s",
        request_index, customer_name, status_label, len(response), settings.batch_uuid,
    )
    try:
        perf_logger.log(
            run_id=run_id,
            batch_uuid=settings.batch_uuid,
            friendly_name=settings.friendly_name,
            batch_type=batch_type,
            request_index=request_index,
            model_name=settings.model_name or "unknown",
            vllm_version=settings.vllm_version,
            thinking_enabled=settings.thinking_enabled,
            system_prompt=settings.system_prompt or "",
            user_prompt=f"Find all information about the customer named: {customer_name}",
            expected_response_format=settings.expected_response_format,
            response=response,
            request_sent_time=request_sent_time,
            response_received_time=response_received_time,
            identifier=customer_name,
        )
        logger.info(
            "[DB LOG] OK result #%d | guest='%s' | status=%s",
            request_index, customer_name, status_label,
        )
    except Exception as exc:
        logger.error(
            "[DB LOG] FAILED to write result #%d | guest='%s' | status=%s | error=%s",
            request_index, customer_name, status_label, exc, exc_info=True,
        )
        raise


# ---------------------------------------------------------------------------
# Multi-guest sequential runner
# ---------------------------------------------------------------------------


def run_sequential_batch_multi_guest(
    run_id: int,
    settings: TestSettings,
    perf_logger: PerformanceTestLogger,
    guest_names: list[str],
) -> list[dict[str, Any]]:
    """Run sequential requests, each querying a different guest.

    Always calls ``app.services.llm.query_guest_with_llm()``.
    """
    logger.info(
        "[MULTI-SEQ] run_id=%d | batch_uuid=%s | sequential_batch_size=%d | total_guests=%d | prompt_id='%s' | version=%s",
        run_id,
        settings.batch_uuid,
        settings.sequential_batch_size,
        len(guest_names),
        settings.prompt_id,
        settings.prompt_version,
    )

    if not guest_names:
        raise ValueError("[MULTI-SEQ] guest_names is empty - cannot run performance test")

    results: list[dict[str, Any]] = []
    batch_size = settings.sequential_batch_size

    for i in range(batch_size):
        customer_name = _select_guest(guest_names, i)
        logger.info("[MULTI-SEQ] Starting request %d/%d for guest: %s", i + 1, batch_size, customer_name)

        # --- Measure timing ---
        start_time = time.perf_counter()
        start_iso = datetime.now(timezone.utc).isoformat()

        # --- LLM call (shares logic with Guest Search) ---
        try:
            response, was_cached = _call_guest_llm(customer_name, settings)
        except Exception as exc:
            logger.error(
                "[MULTI-SEQ] Request %d (guest: %s) LLM call failed: %s",
                i + 1, customer_name, exc,
                exc_info=True,
            )
            response = f"Error: {exc}"
            was_cached = False

        # --- Measure timing ---
        end_iso = datetime.now(timezone.utc).isoformat()
        end_time = time.perf_counter()
        elapsed = round(end_time - start_time, 4)

        logger.info(
            "[MULTI-SEQ] Request %d (guest: %s) completed in %.2fs | cached=%s",
            i + 1, customer_name, elapsed, was_cached,
        )

        # --- Log to performance test database ---
        _log_to_perf_db(
            perf_logger=perf_logger,
            run_id=run_id,
            settings=settings,
            batch_type=BATCH_TYPE_SEQUENTIAL,
            request_index=i + 1,
            customer_name=customer_name,
            response=response,
            was_cached=was_cached,
            request_sent_time=start_iso,
            response_received_time=end_iso,
        )

        result = {
            "batch_type": BATCH_TYPE_SEQUENTIAL,
            "request_index": i + 1,
            "elapsed": elapsed,
            "customer_name": customer_name,
            "cached": was_cached,
        }
        results.append(result)

    return results


# ---------------------------------------------------------------------------
# Multi-guest concurrent runner
# ---------------------------------------------------------------------------


def run_concurrent_batch_multi_guest(
    run_id: int,
    settings: TestSettings,
    perf_logger: PerformanceTestLogger,
    guest_names: list[str],
) -> list[dict[str, Any]]:
    """Run concurrent requests, each querying a different guest.

    Always calls ``app.services.llm.query_guest_with_llm()``.
    """
    logger.info(
        "[MULTI-CONC] run_id=%d | batch_uuid=%s | concurrent_batch_size=%d | total_guests=%d | prompt_id='%s' | version=%s",
        run_id,
        settings.batch_uuid,
        settings.concurrent_batch_size,
        len(guest_names),
        settings.prompt_id,
        settings.prompt_version,
    )

    if not guest_names:
        raise ValueError("[MULTI-CONC] guest_names is empty - cannot run performance test")

    results: list[dict[str, Any]] = []
    seq_count = settings.sequential_batch_size
    conc_count = settings.concurrent_batch_size

    def _execute_single_concurrent(conc_index: int) -> dict[str, Any]:
        """Execute one concurrent request."""
        guest_idx = seq_count + conc_index
        customer_name = _select_guest(guest_names, guest_idx)
        logger.info(
            "[MULTI-CONC] Starting concurrent request %d/%d for guest: %s",
            conc_index + 1, conc_count, customer_name,
        )

        # --- Measure timing ---
        start_time = time.perf_counter()
        start_iso = datetime.now(timezone.utc).isoformat()

        # --- LLM call (shares logic with Guest Search) ---
        try:
            response, was_cached = _call_guest_llm(customer_name, settings)
        except Exception as exc:
            logger.error(
                "[MULTI-CONC] Request %d (guest: %s) LLM call failed: %s",
                conc_index + 1, customer_name, exc,
                exc_info=True,
            )
            response = f"Error: {exc}"
            was_cached = False

        # --- Measure timing ---
        end_iso = datetime.now(timezone.utc).isoformat()
        end_time = time.perf_counter()
        elapsed = round(end_time - start_time, 4)

        logger.info(
            "[MULTI-CONC] Request %d (guest: %s) completed in %.2fs | cached=%s",
            conc_index + 1, customer_name, elapsed, was_cached,
        )

        # --- Log to performance test database ---
        _log_to_perf_db(
            perf_logger=perf_logger,
            run_id=run_id,
            settings=settings,
            batch_type=BATCH_TYPE_CONCURRENT,
            request_index=conc_index + 1,
            customer_name=customer_name,
            response=response,
            was_cached=was_cached,
            request_sent_time=start_iso,
            response_received_time=end_iso,
        )

        return {
            "batch_type": BATCH_TYPE_CONCURRENT,
            "request_index": conc_index + 1,
            "elapsed": elapsed,
            "customer_name": customer_name,
            "cached": was_cached,
        }

    # --- Launch concurrent workers ---
    with ThreadPoolExecutor(max_workers=conc_count) as executor:
        futures = {
            executor.submit(_execute_single_concurrent, i + 1): i + 1
            for i in range(conc_count)
        }
        for future in as_completed(futures):
            try:
                result = future.result()
                results.append(result)
                logger.info(
                    "[MULTI-CONC] Completed request %d in %.2fs (guest: %s, cached: %s)",
                    result["request_index"], result["elapsed"], result.get("customer_name", "?"), result.get("cached", False),
                )
            except Exception as exc:
                logger.error("[MULTI-CONC] Future raised an exception: %s", exc, exc_info=True)

    return results