"""Single-request execution for performance testing.

Handles the core execute-and-log flow that both single-guest and
multi-guest batch runners delegate to.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from .db import PerformanceTestLogger
from .llm_client import query_guest_with_llm
from .prompt_builders import resolve_system_prompt, resolve_user_prompt
from .settings import DEFAULT_MODEL, TestSettings

logger = logging.getLogger(__name__)


# ── Single request execution ────────────────────────────────────────────────


def _execute_and_log(
    batch_type: str,
    request_index: int,
    run_id: int,
    settings: TestSettings,
    perf_logger: PerformanceTestLogger,
    customer_name: str | None = None,
) -> dict[str, Any]:
    """Execute a single LLM query and log the result (thread-safe).

    Each call resolves its own prompt locally to avoid data races on the
    mutable ``TestSettings`` instance.
    """
    name = customer_name or settings.customer_name
    user_prompt = resolve_user_prompt(settings, name)
    system_content = resolve_system_prompt(settings)
    model_name = settings.model_name or DEFAULT_MODEL
    base_url = settings.resolve_vllm_url()

    request_sent_time = datetime.now(timezone.utc).isoformat()
    response_text = query_guest_with_llm(
        base_url=base_url,
        model_name=model_name,
        system_content=system_content,
        user_prompt=user_prompt,
        use_tool_calling=settings.use_tool_calling,
        tool_definitions=settings.tool_definitions or None,
    )
    response_received_time = datetime.now(timezone.utc).isoformat()

    perf_logger.log(
        run_id=run_id,
        batch_uuid=settings.batch_uuid,
        friendly_name=settings.friendly_name,
        batch_type=batch_type,
        request_index=request_index,
        model_name=model_name,
        vllm_version=settings.vllm_version,
        thinking_enabled=settings.thinking_enabled,
        system_prompt=settings.system_prompt,
        user_prompt=user_prompt,
        expected_response_format=settings.expected_response_format,
        response=response_text,
        request_sent_time=request_sent_time,
        response_received_time=response_received_time,
    )

    elapsed = (
        datetime.fromisoformat(response_received_time)
        - datetime.fromisoformat(request_sent_time)
    ).total_seconds()

    result: dict[str, Any] = {
        "batch_type": batch_type,
        "request_index": request_index,
        "elapsed": round(elapsed, 2),
    }
    if customer_name is not None:
        result["customer_name"] = customer_name
    return result


def run_single_request(
    batch_type: str,
    request_index: int,
    run_id: int,
    settings: TestSettings,
    perf_logger: PerformanceTestLogger,
) -> dict[str, Any]:
    """Execute a single LLM query and log the result (single-guest mode).

    Thin wrapper that delegates to the shared ``_execute_and_log``.
    """
    return _execute_and_log(batch_type, request_index, run_id, settings, perf_logger)


# Export for use by batch_runners
execute_and_log = _execute_and_log