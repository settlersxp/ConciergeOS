#!/usr/bin/env python3
"""
FastAPI application for ConciergeOS reservation dashboard.
"""

import sqlite3
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates

from app.schemas import GuestSearchRequest, GuestSearchResponse
from app.services import get_reservations_summary, query_guest_with_llm
from app.services.debug import debug_router

app = FastAPI(title="ConciergeOS")

templates = Jinja2Templates(directory="app/templates")
app.include_router(debug_router, prefix="/api")


@app.get("/")
async def index(request: Request):
    """Serve the main reservations dashboard page."""
    summary = get_reservations_summary()
    # model_dump() converts Pydantic schemas to plain dicts for Jinja2 rendering
    context = {
        "request": request,
        "rooms": summary.model_dump(mode="json")["rooms"],
        "errors": [e.model_dump(mode="json") for e in summary.errors],
    }
    return templates.TemplateResponse(request, "reservations.html", context)


@app.get("/api/reservations")
async def api_reservations():
    """JSON endpoint returning reservations grouped by room and errors."""
    summary = get_reservations_summary()
    return summary.model_dump(mode="json")


@app.get("/guest-search")
async def guest_search_page(request: Request):
    """Serve the guest search page."""
    return templates.TemplateResponse(request, "guest_search.html", {
        "request": request,
    })


@app.post("/api/guest-search")
async def api_guest_search(body: GuestSearchRequest) -> GuestSearchResponse:
    """Query the LLM for all information about a given guest."""
    llm_response = query_guest_with_llm(body.customer_name)
    return GuestSearchResponse(
        query=body.customer_name,
        llm_response=llm_response,
    )


# ── Performance Testing ─────────────────────────────────────────────────────

_DATABASE_PATH = Path(__file__).parent.parent / "performance_tests.db"


@app.get("/performance-testing")
async def performance_testing_page(request: Request):
    """Serve the performance testing page."""
    return templates.TemplateResponse(request, "performance_testing.html", {
        "request": request,
    })


@app.post("/api/performance-testing")
async def api_run_performance_testing(request: Request) -> dict[str, Any]:
    """Run performance tests with the provided settings."""
    body = await request.json()

    from PerformanceTesting.run_performance_tests import TestSettings, run_tests  # noqa: cwd

    settings = TestSettings(
        customer_name=body.get("customer_name", "عائشة إبراهيم"),
        vllm_url=body.get("vllm_url", "http://10.0.0.227:8000/v1"),
        models_endpoint=body.get("models_endpoint", "http://10.0.0.227:8000/v1/models"),
        database_path=_DATABASE_PATH,
        sequential_batch_size=int(body.get("sequential_batch_size", 5)),
        concurrent_batch_size=int(body.get("concurrent_batch_size", 8)),
        model_name=body.get("model_name", ""),
        vllm_version=body.get("vllm_version", ""),
        thinking_enabled=bool(body.get("thinking_enabled", False)),
        system_prompt=body.get("system_prompt", ""),
        user_prompt=body.get("user_prompt", ""),
        expected_response_format=body.get("expected_response_format", "auto"),
    )

    # Use default system prompt if not provided
    if not settings.system_prompt:
        from app.services.llm import SYSTEM_PROMPT  # noqa: cwd
        settings.system_prompt = SYSTEM_PROMPT

    result = run_tests(settings)
    return result


@app.get("/api/performance-testing/results")
async def api_get_performance_results() -> list[dict[str, Any]]:
    """Get the latest test results from the database."""
    if not _DATABASE_PATH.exists():
        return []

    conn = sqlite3.connect(str(_DATABASE_PATH))
    conn.row_factory = sqlite3.Row
    cursor = conn.execute(
        """
        SELECT id, run_id, batch_type, request_index, model_name,
               context_length, vllm_version, thinking_enabled,
               system_prompt, user_prompt, response_format, json_malformed,
               response_length, request_sent_time, response_received_time,
               response_content
        FROM test_results
        ORDER BY run_id DESC, batch_type, request_index DESC
        LIMIT 100
        """
    )
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


@app.get("/api/performance-testing/all-results")
async def api_get_all_performance_results() -> list[dict[str, Any]]:
    """Get all test results from the database (no limit)."""
    if not _DATABASE_PATH.exists():
        return []

    conn = sqlite3.connect(str(_DATABASE_PATH))
    conn.row_factory = sqlite3.Row
    cursor = conn.execute(
        """
        SELECT id, run_id, batch_type, request_index, model_name,
               context_length, vllm_version, thinking_enabled,
               system_prompt, user_prompt, response_format, json_malformed,
               response_length, request_sent_time, response_received_time,
               response_content
        FROM test_results
        ORDER BY run_id DESC, batch_type, request_index DESC
        """
    )
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows
