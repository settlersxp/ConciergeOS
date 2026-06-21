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
        "current_page": "reservations",
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
        "current_page": "guest_search",
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
        "current_page": "performance_testing",
    })


@app.post("/api/performance-testing")
async def api_run_performance_testing(request: Request) -> dict[str, Any]:
    """Run performance tests with the provided settings."""
    body = await request.json()

    from PerformanceTesting.run_performance_tests import TestSettings, run_tests  # noqa: cwd

    test_mode = body.get("test_mode", "single")
    guest_names: list[str] = []

    # In multi-guest mode, fetch the test guests from the database
    if test_mode == "multi":
        from app.db import SessionLocal
        from app.models import Guest

        db = SessionLocal()
        try:
            test_guests = (
                db.query(Guest)
                .filter(Guest.special_preferences == "performance_test")
                .order_by(Guest.guest_id)
                .all()
            )
            guest_names = [
                f"{g.first_name} {g.last_name}"
                for g in test_guests
            ]
        finally:
            db.close()

    settings = TestSettings(
        customer_name=body.get("customer_name", "عائشة إبراهيم"),
        vllm_url=body.get("vllm_url", "http://10.0.0.227:8000/v1"),
        models_endpoint=body.get("models_endpoint", "http://10.0.0.227:8000/v1/models"),
        database_path=_DATABASE_PATH,
        sequential_batch_size=int(body.get("sequential_batch_size", 5)),
        concurrent_batch_size=int(body.get("concurrent_batch_size", 8)),
        test_mode=test_mode,
        guest_names=guest_names,
        batch_uuid=body.get("batch_uuid", ""),
        friendly_name=body.get("friendly_name", ""),
        model_name=body.get("model_name", ""),
        vllm_version=body.get("vllm_version", ""),
        thinking_enabled=bool(body.get("thinking_enabled", False)),
        system_prompt=body.get("system_prompt", ""),
        user_prompt=body.get("user_prompt", ""),
        expected_response_format=body.get("expected_response_format", "auto"),
    )

    # Generate a UUID if not provided
    if not settings.batch_uuid:
        import uuid as uuid_lib
        settings.batch_uuid = str(uuid_lib.uuid4())

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
               response_content, valid_response
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
        SELECT id, run_id, batch_uuid, friendly_name, batch_type, request_index,
               model_name, context_length, vllm_version, thinking_enabled,
               system_prompt, user_prompt, response_format, json_malformed,
               response_length, request_sent_time, response_received_time,
               response_content, valid_response
        FROM test_results
        ORDER BY run_id DESC, batch_type, request_index DESC
        """
    )
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


@app.get("/api/performance-testing/batches")
async def api_get_performance_batches() -> list[dict[str, Any]]:
    """Get all unique test batches with their UUID and friendly name."""
    if not _DATABASE_PATH.exists():
        return []

    conn = sqlite3.connect(str(_DATABASE_PATH))
    conn.row_factory = sqlite3.Row
    cursor = conn.execute(
        """
        SELECT batch_uuid, friendly_name, COUNT(*) AS total_requests,
               MIN(request_sent_time) AS first_run_time
        FROM test_results
        GROUP BY batch_uuid
        ORDER BY first_run_time DESC
        """
    )
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


@app.get("/api/performance-testing/results-by-batch")
async def api_get_results_by_batch(batch_uuid: str) -> list[dict[str, Any]]:
    """Get test results for a specific batch identified by UUID."""
    if not _DATABASE_PATH.exists():
        return []

    conn = sqlite3.connect(str(_DATABASE_PATH))
    conn.row_factory = sqlite3.Row
    cursor = conn.execute(
        """
        SELECT id, run_id, batch_uuid, friendly_name, batch_type, request_index,
               model_name, context_length, vllm_version, thinking_enabled,
               system_prompt, user_prompt, response_format, json_malformed,
               response_length, request_sent_time, response_received_time,
               response_content, valid_response
        FROM test_results
        WHERE batch_uuid = ?
        ORDER BY batch_type, request_index
        """,
        (batch_uuid,),
    )
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


@app.patch("/api/performance-testing/result/{result_id}")
async def api_update_valid_response(result_id: int, request: Request) -> dict[str, Any]:
    """Update the valid_response flag for a specific test result."""
    body = await request.json()
    valid_response = body.get("valid_response")

    if not _DATABASE_PATH.exists():
        return {"error": "Database not found"}

    conn = sqlite3.connect(str(_DATABASE_PATH))
    conn.execute(
        "UPDATE test_results SET valid_response = ? WHERE id = ?",
        (valid_response, result_id),
    )
    conn.commit()
    conn.close()

    return {"ok": True, "id": result_id, "valid_response": valid_response}


# ── Performance Test Guest Setup ─────────────────────────────────────────────

@app.post("/api/performance-testing/setup-guests")
async def api_setup_test_guests() -> dict[str, Any]:
    """Setup 13 test guests with 4 reservations each for performance testing."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))

    from Generator.setup_performance_guests import setup_performance_test_guests  # noqa: cwd

    try:
        guests = setup_performance_test_guests()
        return {
            "ok": True,
            "guests": guests,
            "total": len(guests),
        }
    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
            "guests": [],
        }


@app.post("/api/performance-testing/generate-xml")
async def api_generate_xml() -> dict[str, Any]:
    """Regenerate the guests data file (CSV) and return its path."""
    from app.services.llm import fetch_all_guests_and_reservations  # noqa: cwd

    try:
        csv_output = fetch_all_guests_and_reservations()
        return {
            "ok": True,
            "path": "data/guests_data.csv",
            "size_bytes": len(csv_output.encode("utf-8")),
        }
    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
        }


@app.get("/api/performance-testing/test-guests")
async def api_get_test_guests() -> list[dict[str, Any]]:
    """Get all performance test guests (marked with special_preferences = 'performance_test')."""
    from app.db import SessionLocal
    from app.models import Guest, Reservation
    from sqlalchemy import func

    db = SessionLocal()
    try:
        guests = (
            db.query(Guest)
            .filter(Guest.special_preferences == "performance_test")
            .order_by(Guest.guest_id)
            .all()
        )

        result = []
        for g in guests:
            count = (
                db.query(func.count(Reservation.reservation_id))
                .filter(Reservation.guest_id == g.guest_id)
                .scalar()
            )
            result.append({
                "guest_id": g.guest_id,
                "first_name": g.first_name,
                "last_name": g.last_name,
                "full_name": f"{g.first_name} {g.last_name}",
                "reservation_count": count,
            })

        return result
    finally:
        db.close()
