#!/usr/bin/env python3
"""Performance testing routes."""

import json
import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import func, cast, String
from sqlalchemy.orm import Session

from app.db import SessionLocal, get_db
from app.models import Guest, PerformanceTestResult, Reservation, Room, PromptVersion
from app.schemas import (
    CheckDuplicatesResponse,
    DeleteBatchResponse,
    DuplicateGuestInfo,
    GenerateAllResponse,
    GenerateXmlResponse,
    GuestDetailSchema,
    PerformanceTestBatchSchema,
    PerformanceTestRequest,
    PerformanceTestResultSchema,
    ReservationDetailSchema,
    SetupGuestsResponse,
    SingleGuestValidation,
    TestGuestSchema,
    UpdateIdentifierRequest,
    UpdateIdentifierResponse,
    UpdateValidResponseRequest,
    UpdateValidResponseResponse,
    ValidateGuestsRequest,
    ValidateGuestsResponse,
)
from app.services.response_cache import generate_http_cache_key, _get_http_cache

router = APIRouter()

logger = logging.getLogger(__name__)

_DATABASE_PATH = Path(__file__).resolve().parent.parent.parent / "database.db"


# ── Run Performance Tests ────────────────────────────────────────────────────

@router.post("/api/performance-testing")
async def api_run_performance_testing(body: PerformanceTestRequest) -> dict[str, Any]:
    """Run performance tests with the provided settings."""

    from PerformanceTesting.run_performance_tests import TestSettings, run_tests  # noqa: cwd
    from app.services.llm import SHARED_SYSTEM_PROMPT, TOOL_DEFINITIONS  # noqa: cwd

    test_mode = body.test_mode
    guest_names: list[str] = []

    # Determine tool calling mode from data_format
    use_tool_calling = body.data_format == "tool_calling"

    # In multi-guest mode, fetch the test guests from the database
    if test_mode == "multi":
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

    # Log the incoming request for debugging
    logger.info(
        "[PERF TEST REQ] test_mode=%s | prompt_id=%s | prompt_version=%s | data_format=%s | batch_size_seq=%d | batch_size_conc=%d",
        test_mode,
        getattr(body, 'prompt_id', 'NOT_SET'),
        getattr(body, 'prompt_version', 'NOT_SET'),
        body.data_format,
        body.sequential_batch_size,
        body.concurrent_batch_size,
    )

    # Resolve prompt_id and prompt_version from the request body
    prompt_id = getattr(body, 'prompt_id', None) or ''
    prompt_version = getattr(body, 'prompt_version', None)

    # Resolve prompt template from DB if both prompt_id and prompt_version are provided
    user_prompt = body.user_prompt
    system_prompt = SHARED_SYSTEM_PROMPT

    if prompt_id and prompt_version:
        db = SessionLocal()
        try:
            pv = (
                db.query(PromptVersion)
                .filter(
                    PromptVersion.prompt_id == prompt_id,
                    PromptVersion.version == prompt_version,
                )
                .first()
            )
            if pv:
                user_prompt = pv.user_prompt_template or user_prompt
                system_prompt = "\n\n".join(
                    part for part in (pv.intention, pv.restrictions, pv.output_structure) if part
                )
                logger.info(
                    "[PROMPT RESOLVED] prompt_id=%s | version=%d | name=%s",
                    prompt_id, prompt_version, pv.name,
                )
            else:
                logger.warning(
                    "[PROMPT NOT FOUND] prompt_id=%s | version=%d - using defaults",
                    prompt_id, prompt_version,
                )
        finally:
            db.close()
    elif prompt_id and not prompt_version:
        logger.info(
            "[PROMPT INFO] prompt_id=%s | version=NOT SET (will default to 'guest-search' in query_guest_with_llm)",
            prompt_id,
        )

    settings = TestSettings(
        customer_name=body.customer_name,
        vllm_url=body.vllm_url,
        models_endpoint=body.models_endpoint,
        database_path=_DATABASE_PATH,
        sequential_batch_size=body.sequential_batch_size,
        concurrent_batch_size=body.concurrent_batch_size,
        test_mode=test_mode,
        guest_names=guest_names,
        batch_uuid=body.batch_uuid,
        friendly_name=body.friendly_name,
        model_name=body.model_name,
        vllm_version=body.vllm_version,
        thinking_enabled=body.thinking_enabled,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        expected_response_format=body.expected_response_format,
        data_format=body.data_format,
        use_tool_calling=use_tool_calling,
        tool_definitions=TOOL_DEFINITIONS if use_tool_calling else [],
        runtime_variables=body.runtime_variables,
        prompt_id=getattr(body, 'prompt_id', "") or "",
        prompt_version=getattr(body, 'prompt_version', None),
    )

    # Generate a UUID if not provided
    if not settings.batch_uuid:
        import uuid as uuid_lib
        settings.batch_uuid = str(uuid_lib.uuid4())

    result = run_tests(settings)
    return result


# ── Test Results ─────────────────────────────────────────────────────────────

@router.get("/api/performance-testing/results")
async def api_get_performance_results(
    db: Session = Depends(get_db),
) -> list[PerformanceTestResultSchema]:
    """Get the latest test results from the database."""
    rows = (
        db.query(PerformanceTestResult)
        .order_by(
            PerformanceTestResult.run_id.desc(),
            PerformanceTestResult.batch_type,
            PerformanceTestResult.request_index.desc(),
        )
        .limit(100)
        .all()
    )
    return [PerformanceTestResultSchema.model_validate(r) for r in rows]


@router.get("/api/performance-testing/all-results")
async def api_get_all_performance_results(
    db: Session = Depends(get_db),
) -> list[PerformanceTestResultSchema]:
    """Get all test results from the database (no limit)."""
    rows = (
        db.query(PerformanceTestResult)
        .order_by(
            PerformanceTestResult.run_id.desc(),
            PerformanceTestResult.batch_type,
            PerformanceTestResult.request_index.desc(),
        )
        .all()
    )
    return [PerformanceTestResultSchema.model_validate(r) for r in rows]


# ── Batches ──────────────────────────────────────────────────────────────────

@router.get("/api/performance-testing/batches")
async def api_get_performance_batches(
    db: Session = Depends(get_db),
) -> list[PerformanceTestBatchSchema]:
    """Get all unique test batches with their UUID and friendly name."""
    rows = (
        db.query(
            PerformanceTestResult.batch_uuid,
            func.max(PerformanceTestResult.friendly_name).label("friendly_name"),
            func.count("*").label("total_requests"),
            func.min(PerformanceTestResult.request_sent_time).label("first_run_time"),
        )
        .group_by(PerformanceTestResult.batch_uuid)
        .order_by(func.min(PerformanceTestResult.request_sent_time).desc())
        .all()
    )

    return [
        PerformanceTestBatchSchema(
            batch_uuid=row.batch_uuid,
            friendly_name=row.friendly_name,
            total_requests=row.total_requests,
            first_run_time=row.first_run_time,
        )
        for row in rows
    ]


from datetime import datetime

@router.get("/api/performance-testing/stats")
async def api_get_performance_stats(
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """Get aggregated performance stats per batch for dashboard visualization."""
    rows = (
        db.query(PerformanceTestResult)
        .order_by(PerformanceTestResult.batch_uuid, PerformanceTestResult.batch_type)
        .all()
    )
    from collections import defaultdict

    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        elapsed = 0.0
        if r.response_received_time and r.request_sent_time:
            try:
                sent = datetime.fromisoformat(r.request_sent_time)
                received = datetime.fromisoformat(r.response_received_time)
                elapsed = (received - sent).total_seconds()
            except (ValueError, TypeError):
                elapsed = 0.0
        groups[r.batch_uuid].append({
            "elapsed": elapsed,
            "valid": r.valid_response,
            "batch_type": r.batch_type,
            "model_name": r.model_name,
            "friendly_name": r.friendly_name,
        })

    stats = []
    for batch_uuid, entries in groups.items():
        sequential_entries = [e for e in entries if e["batch_type"] == "sequential"]
        concurrent_entries = [e for e in entries if e["batch_type"] == "concurrent"]

        for label, elapses in [("sequential", sequential_entries), ("concurrent", concurrent_entries)]:
            if not elapses:
                continue
            avg_speed = sum(e["elapsed"] for e in elapses) / len(elapses)
            valid_count = sum(1 for e in elapses if e["valid"] is True)
            accuracy = valid_count / len(elapses) * 100
            stats.append({
                "batch_uuid": batch_uuid,
                "friendly_name": elapses[0]["friendly_name"],
                "model_name": elapses[0]["model_name"],
                "batch_type": label,
                "avg_speed_seconds": round(avg_speed, 3),
                "accuracy_pct": round(accuracy, 1),
                "total_requests": len(elapses),
            })
    return stats


@router.get("/api/performance-testing/results-by-batch")
async def api_get_results_by_batch(
    batch_uuid: str,
    db: Session = Depends(get_db),
) -> list[PerformanceTestResultSchema]:
    """Get test results for a specific batch identified by UUID."""
    rows = (
        db.query(PerformanceTestResult)
        .filter(PerformanceTestResult.batch_uuid == batch_uuid)
        .order_by(
            PerformanceTestResult.batch_type,
            PerformanceTestResult.request_index,
        )
        .all()
    )
    return [PerformanceTestResultSchema.model_validate(r) for r in rows]


@router.patch("/api/performance-testing/result/{result_id}")
async def api_update_valid_response(
    result_id: int,
    body: UpdateValidResponseRequest,
    db: Session = Depends(get_db),
) -> UpdateValidResponseResponse:
    """Update the valid_response flag for a specific test result."""
    result = (
        db.query(PerformanceTestResult)
        .filter(PerformanceTestResult.id == result_id)
        .first()
    )

    if result is None:
        return UpdateValidResponseResponse(
            ok=False,
            error=f"No result found with id {result_id}",
        )

    result.valid_response = body.valid_response
    db.commit()

    return UpdateValidResponseResponse(
        ok=True,
        id=result_id,
        valid_response=body.valid_response,
    )


# ── Performance Test Guest Setup ─────────────────────────────────────────────

@router.post("/api/performance-testing/setup-guests")
async def api_setup_test_guests() -> SetupGuestsResponse:
    """Setup 13 test guests with 4 reservations each for performance testing."""

    from Generator.setup_performance_guests import setup_performance_test_guests  # noqa: cwd

    try:
        guests = setup_performance_test_guests()
        return SetupGuestsResponse(
            ok=True,
            guests=guests,
            total=len(guests),
        )
    except Exception as e:
        return SetupGuestsResponse(
            ok=False,
            error=str(e),
            guests=[],
        )


@router.post("/api/performance-testing/generate-xml")
async def api_generate_xml() -> GenerateXmlResponse:
    """Regenerate the guests data file (CSV) and return its path."""
    from app.services.llm import fetch_all_guests_and_reservations  # noqa: cwd

    try:
        csv_output = fetch_all_guests_and_reservations()
        return GenerateXmlResponse(
            ok=True,
            path="data/guests_data.csv",
            size_bytes=len(csv_output.encode("utf-8")),
        )
    except Exception as e:
        return GenerateXmlResponse(
            ok=False,
            error=str(e),
        )


@router.post("/api/performance-testing/generate-all")
async def api_generate_all() -> GenerateAllResponse:
    """Regenerate all 3 data file formats (CSV, JSON, XML) and return their paths."""
    from app.services.llm import (
        fetch_all_as_json,
        fetch_all_as_xml,
        fetch_all_guests_and_reservations,
    )  # noqa: cwd

    try:
        csv_output = fetch_all_guests_and_reservations()
        json_output = fetch_all_as_json()
        xml_output = fetch_all_as_xml()
        return GenerateAllResponse(
            ok=True,
            files={
                "csv": {
                    "path": "data/guests_data.csv",
                    "size_bytes": len(csv_output.encode("utf-8")),
                },
                "json": {
                    "path": "data/guests_data.json",
                    "size_bytes": len(json_output.encode("utf-8")),
                },
                "xml": {
                    "path": "data/guests_data.xml",
                    "size_bytes": len(xml_output.encode("utf-8")),
                },
            },
        )
    except Exception as e:
        return GenerateAllResponse(
            ok=False,
            error=str(e),
        )


@router.delete("/api/performance-testing/batch/{batch_uuid}")
async def api_delete_batch(
    batch_uuid: str,
    db: Session = Depends(get_db),
) -> DeleteBatchResponse:
    """Delete all test results for a specific batch identified by UUID."""
    # First, count the records to verify they exist and log the operation
    count = (
        db.query(PerformanceTestResult)
        .filter(PerformanceTestResult.batch_uuid == batch_uuid)
        .count()
    )
    logger.info(f"Deleting batch_uuid={batch_uuid}, found {count} records")

    deleted_count = (
        db.query(PerformanceTestResult)
        .filter(PerformanceTestResult.batch_uuid == batch_uuid)
        .delete(synchronize_session="fetch")
    )
    db.flush()
    db.commit()

    # Refresh session to ensure state is fully synchronized with the database
    db.expire_all()

    logger.info(f"Deleted {deleted_count} records for batch_uuid={batch_uuid}")

    # Invalidate the HTTP cache for the batches list endpoint
    # so the next GET request fetches fresh data from the database
    batches_cache_key = generate_http_cache_key("/api/performance-testing/batches")
    http_cache = _get_http_cache()
    http_cache.delete(batches_cache_key)
    logger.info(f"Invalidated HTTP cache for batches list (key={batches_cache_key[:12]}...)")

    # Also invalidate the specific batch results cache if it exists
    results_cache_key = generate_http_cache_key(f"/api/performance-testing/results-by-batch?batch_uuid={batch_uuid}")
    http_cache.delete(results_cache_key)

    return DeleteBatchResponse(
        ok=True,
        deleted_count=deleted_count,
        batch_uuid=batch_uuid,
    )


@router.get("/api/performance-testing/test-guests")
async def api_get_test_guests() -> list[TestGuestSchema]:
    """Get all performance test guests (marked with special_preferences = 'performance_test')."""
    db = SessionLocal()
    try:
        guests = (
            db.query(Guest)
            .filter(Guest.special_preferences == "performance_test")
            .order_by(Guest.guest_id)
            .all()
        )

        result: list[TestGuestSchema] = []
        for g in guests:
            count = (
                db.query(func.count(Reservation.reservation_id))
                .filter(Reservation.guest_id == g.guest_id)
                .scalar()
            )
            result.append(
                TestGuestSchema(
                    guest_id=g.guest_id,
                    first_name=g.first_name,
                    last_name=g.last_name,
                    full_name=f"{g.first_name} {g.last_name}",
                    reservation_count=count,
                )
            )

        return result
    finally:
        db.close()


@router.get("/api/performance-testing/check-duplicates")
async def api_check_duplicate_test_guests(
    db: Session = Depends(get_db),
) -> CheckDuplicatesResponse:
    """Check for duplicate test guests among those marked with special_preferences = 'performance_test'.

    Returns a report showing which name combinations have multiple entries,
    which can cause validation issues during performance testing.
    """
    try:
        from sqlalchemy import text

        # Get total count of test guests
        total_count = (
            db.query(func.count(Guest.guest_id))
            .filter(Guest.special_preferences == "performance_test")
            .scalar()
        )

        # Find duplicates using raw SQL for GROUP BY with HAVING
        query = text(
            """
            SELECT first_name, last_name, COUNT(*) as cnt, GROUP_CONCAT(guest_id) as guest_ids
            FROM guests
            WHERE special_preferences = 'performance_test'
            GROUP BY first_name, last_name
            HAVING cnt > 1
            ORDER BY cnt DESC
            """
        )
        results = db.execute(query).fetchall()

        duplicates = []
        for row in results:
            duplicates.append(
                DuplicateGuestInfo(
                    first_name=row[0],
                    last_name=row[1],
                    count=row[2],
                    guest_ids=[int(x) for x in str(row[3]).split(",")],
                )
            )

        return CheckDuplicatesResponse(
            ok=True,
            has_duplicates=len(duplicates) > 0,
            duplicates=duplicates,
            total_test_guests=total_count,
        )
    except Exception as e:
        return CheckDuplicatesResponse(
            ok=False,
            error=str(e),
            total_test_guests=0,
        )


@router.get("/api/performance-testing/guest/{guest_id}")
async def api_get_guest_detail(guest_id: int) -> GuestDetailSchema:
    """Get detailed information for a single guest including all reservations."""
    db = SessionLocal()
    try:
        guest = (
            db.query(Guest)
            .filter(Guest.guest_id == guest_id)
            .first()
        )

        if guest is None:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail=f"Guest {guest_id} not found")

        reservations = (
            db.query(Reservation)
            .join(Room, Reservation.room_id == Room.room_id)
            .filter(Reservation.guest_id == guest_id)
            .order_by(Reservation.reservation_id)
            .all()
        )

        reservation_details: list[ReservationDetailSchema] = []
        for r in reservations:
            created_at: str | None = None
            if r.created_at is not None:
                created_at = r.created_at.isoformat()

            reservation_details.append(
                ReservationDetailSchema(
                    reservation_id=r.reservation_id,
                    room_id=r.room_id,
                    room_name=r.room.name,
                    check_in_date=r.check_in_date,
                    check_out_date=r.check_out_date,
                    status=r.status,
                    booking_source=r.booking_source,
                    created_at=created_at,
                )
            )

        return GuestDetailSchema(
            guest_id=guest.guest_id,
            first_name=guest.first_name,
            last_name=guest.last_name,
            date_of_birth=guest.date_of_birth,
            is_special_guest=guest.is_special_guest,
            special_preferences=guest.special_preferences,
            reservations=reservation_details,
        )
    finally:
        db.close()


# ── Validation Helpers ───────────────────────────────────────────────────────

def _validate_single_pair(
    ground_truth_json: str,
    ground_truth_name: str,
    response_content: str | None,
    use_cache: bool = True,
) -> tuple[bool | None, str | None, bool]:
    """Validate a single guest-response pair using the LLM.

    Compares the full ground-truth JSON against the LLM response field-by-field.
    Uses response caching to avoid redundant LLM calls for repeated validations.

    Args:
        ground_truth_json: JSON string of ground-truth guest data.
        ground_truth_name: Guest full name used as validation identifier.
        response_content: The LLM response to validate.
        use_cache: If True, check/use response cache for this validation.

    Returns:
        A tuple of (is_match, llm_reasoning, was_cached).
        is_match is True/False on success, None on error.
        was_cached is True if the result was served from cache.
    """
    import json

    from app.services.response_cache import (
        _get_cache,
        generate_cache_key,
    )

    system_prompt = (
        "You are a strict validation engine. Your job is to compare ground-truth guest "
        "information (provided as JSON) against an LLM-generated text response and determine "
        "whether the response correctly contains **all** of the guest's information.\n\n"
        "You must check EVERY field in the ground truth:\n"
        "1. **Guest fields**: guest_id, first_name, last_name, date_of_birth, "
        "is_special_guest, special_preferences\n"
        "2. **Each reservation**: reservation_id, room_id, room_name, check_in_date, "
        "check_out_date, status, booking_source\n\n"
        "Rules:\n"
        "- is_match = true ONLY if the LLM response contains correct information for ALL "
        "ground-truth fields and ALL reservations.\n"
        "- If the response lists the correct guest among several candidates but does not "
        "include full reservation details for that guest, is_match = false.\n"
        "- If any reservation from the ground truth is missing from the response, "
        "is_match = false.\n"
        "- If any field value differs between ground truth and response, is_match = false.\n"
        "- If the response is empty or clearly unrelated, is_match = false.\n\n"
        "Respond with a JSON object having two fields:\n"
        "- 'is_match' (boolean)\n"
        "- 'reasoning' (string) — list every field that is missing or incorrect, "
        "and which reservations are missing."
    )

    user_prompt = (
        f"Ground-truth guest name: {ground_truth_name}\n\n"
        f"Ground-truth JSON:\n{ground_truth_json}\n\n"
        f"LLM response to validate:\n{response_content or '(empty response)'}\n\n"
        "Compare the LLM response against the ground-truth JSON field by field. "
        "Return your answer as a JSON object with 'is_match' (boolean) and "
        "'reasoning' (string)."
    )

    # Generate cache key from the validation inputs (system prompt + user prompt)
    cache_input = f"{system_prompt}\n\n{user_prompt}"
    cache_key = generate_cache_key(cache_input)

    logger.info(
        f"[VALIDATE] Starting validation for guest '{ground_truth_name}' | "
        f"cache_key={cache_key[:12]}... | use_cache={use_cache}"
    )

    # Check cache first if enabled
    if use_cache:
        cached_entry = _get_cache().get(cache_key)
        if cached_entry is not None:
            logger.info(
                f"[VALIDATE] [CACHE] HIT for '{ground_truth_name}' | "
                f"response_len={len(cached_entry.response)}"
            )
            try:
                parsed = json.loads(cached_entry.response)
                is_match = parsed.get("is_match")
                reasoning = parsed.get("reasoning", "")
                return is_match, reasoning, True
            except (json.JSONDecodeError, AttributeError):
                logger.warning(
                    f"[VALIDATE] Cached response for '{ground_truth_name}' is malformed, "
                    f"falling back to LLM call"
                )

    logger.info(f"[VALIDATE] [CACHE] MISS for '{ground_truth_name}' | calling LLM")

    # Call LLM using the cached implementation
    try:
        from app.services.llm import get_llm_config

        client, model = get_llm_config()

        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
        )
        answer = resp.choices[0].message.content or "{}"

        parsed = json.loads(answer)
        is_match = parsed.get("is_match")
        reasoning = parsed.get("reasoning", "")

        # Store in cache if enabled
        if use_cache:
            _get_cache().set(cache_key, answer)
            logger.info(
                f"[VALIDATE] [CACHE] STORED for '{ground_truth_name}' | "
                f"is_match={is_match}"
            )

        return is_match, reasoning, False
    except Exception as e:
        logger.error(
            f"[VALIDATE] Error validating '{ground_truth_name}': {e}",
            exc_info=True,
        )
        return None, f"Validation error: {e}", False


# ── Validate Guests Endpoint ─────────────────────────────────────────────────

@router.post("/api/performance-testing/validate-guests")
async def api_validate_guests(
    body: ValidateGuestsRequest,
    db: Session = Depends(get_db),
) -> ValidateGuestsResponse:
    """Validate that all test guests are correctly found in a batch's test responses."""

    # Fetch test guests
    hotel_db = SessionLocal()
    try:
        query = hotel_db.query(Guest).filter(Guest.special_preferences == "performance_test")
        if body.guest_ids:
            query = query.filter(Guest.guest_id.in_(body.guest_ids))
        test_guests = query.order_by(Guest.guest_id).all()
    finally:
        pass  # We close after the try/finally below

    # Fetch batch results
    batch_results = (
        db.query(PerformanceTestResult)
        .filter(PerformanceTestResult.batch_uuid == body.batch_uuid)
        .order_by(PerformanceTestResult.request_index)
        .all()
    )

    if not test_guests:
        return ValidateGuestsResponse(ok=False, error=f"No test guests found for batch {body.batch_uuid}")

    if not batch_results:
        return ValidateGuestsResponse(ok=False, error=f"No results found for batch {body.batch_uuid}")

    # Build a lookup: identifier -> result
    results_by_identifier: dict[str, PerformanceTestResult] = {}
    for r in batch_results:
        if r.identifier:
            results_by_identifier[r.identifier] = r

    validation_results: list[SingleGuestValidation] = []
    matches = 0
    total = 0

    try:
        for guest in test_guests:
            full_name = f"{guest.first_name} {guest.last_name}"
            matched_result = results_by_identifier.get(full_name)

            # Build ground truth JSON for this guest (reservations)
            guest_reservations = (
                hotel_db.query(Reservation)
                .join(Room, Reservation.room_id == Room.room_id)
                .filter(Reservation.guest_id == guest.guest_id)
                .order_by(Reservation.reservation_id)
                .all()
            )

            ground_truth_obj = {
                "guest_id": guest.guest_id,
                "first_name": guest.first_name,
                "last_name": guest.last_name,
                "date_of_birth": str(guest.date_of_birth) if guest.date_of_birth else None,
                "is_special_guest": guest.is_special_guest,
                "special_preferences": guest.special_preferences,
                "reservations": [
                    {
                        "reservation_id": r.reservation_id,
                        "room_id": r.room_id,
                        "room_name": r.room.name,
                        "check_in_date": str(r.check_in_date),
                        "check_out_date": str(r.check_out_date),
                        "status": r.status.value,
                        "booking_source": r.booking_source.value,
                    }
                    for r in guest_reservations
                ],
            }

            ground_truth_json = json.dumps(ground_truth_obj, indent=2, default=str)

            is_match, reasoning, was_cached = _validate_single_pair(
                ground_truth_json=ground_truth_json,
                ground_truth_name=full_name,
                response_content=matched_result.response_content if matched_result else None,
                use_cache=True,
            )
            
            if was_cached:
                logger.info(f"[VALIDATE] Cached result used for guest '{full_name}'")

            validation_results.append(
                SingleGuestValidation(
                    guest_id=guest.guest_id,
                    guest_name=full_name,
                    result_id=matched_result.id if matched_result else None,
                    is_match=is_match,
                    valid_response=matched_result.valid_response if matched_result else None,
                    llm_reasoning=reasoning,
                    ground_truth=ground_truth_json,
                    llm_response_content=matched_result.response_content if matched_result else None,
                )
            )

            if is_match is not None:
                total += 1
                if is_match:
                    matches += 1

        return ValidateGuestsResponse(
            ok=True,
            results=validation_results,
            summary={
                "total_guests": len(test_guests),
                "matched": matches,
                "total_validated": total,
                "accuracy": round(matches / total, 4) if total > 0 else 0,
            },
        )
    except Exception as e:
        return ValidateGuestsResponse(ok=False, error=str(e))
    finally:
        hotel_db.close()


# ── Prompt Performance Analysis Endpoints ─────────────────────────────────────


@router.get("/api/performance-testing/prompt-batches")
async def api_get_prompt_batches(
    prompt_id: str,
    version: int | None = None,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Get batch-level aggregated stats for a specific prompt.

    Groups individual test results by batch_uuid and returns aggregated
    stats per batch (avg speed, accuracy, request count) along with
    all individual request timings for scatter plot visualization.
    """
    query = (
        db.query(PerformanceTestResult)
        .filter(PerformanceTestResult.prompt_id == prompt_id,)
    )
    if version is not None:
        query = query.filter(PerformanceTestResult.prompt_version == version)

    rows = query.order_by(
        PerformanceTestResult.batch_type,
        PerformanceTestResult.batch_uuid,
        PerformanceTestResult.request_sent_time
    ).all()

    # Get prompt name
    prompt_name = f"prompt_{prompt_id}"
    pv = (
        db.query(PromptVersion)
        .filter(
            PromptVersion.prompt_id == prompt_id,
            PromptVersion.version == version,
        )
        .first()
    )
    if pv:
        prompt_name = pv.name

    # Group by (batch_uuid, batch_type, model_name)
    from collections import defaultdict
    batches_dict: dict[tuple, list[float]] = defaultdict(list)
    batch_meta: dict[tuple, dict[str, Any]] = {}

    for r in rows:
        elapsed = 0.0
        if r.response_received_time and r.request_sent_time:
            try:
                sent = datetime.fromisoformat(r.request_sent_time)
                received = datetime.fromisoformat(r.response_received_time)
                elapsed = (received - sent).total_seconds()
            except (ValueError, TypeError):
                elapsed = 0.0

        key = (r.batch_uuid, r.batch_type, r.model_name)
        batches_dict[key].append(elapsed)

        if key not in batch_meta:
            batch_meta[key] = {
                "batch_uuid": r.batch_uuid,
                "batch_type": r.batch_type,
                "model_name": r.model_name,
                "vllm_version": r.vllm_version,
                "thinking_enabled": r.thinking_enabled,
                "friendly_name": r.friendly_name,
                "valid_count": 0,
                "total_count": 0,
            }
        batch_meta[key]["total_count"] += 1
        if r.valid_response is True:
            batch_meta[key]["valid_count"] += 1

    batch_list = []
    for key, timings in batches_dict.items():
        meta = batch_meta[key]
        avg_speed = sum(timings) / len(timings)
        accuracy = (meta["valid_count"] / meta["total_count"] * 100) if meta["total_count"] > 0 else 0.0

        batch_list.append({
            "batch_uuid": meta["batch_uuid"],
            "batch_type": meta["batch_type"],
            "model_name": meta["model_name"],
            "vllm_version": meta["vllm_version"],
            "thinking_enabled": meta["thinking_enabled"],
            "friendly_name": meta["friendly_name"],
            "avg_speed_seconds": round(avg_speed, 3),
            "accuracy_pct": round(accuracy, 1),
            "total_requests": meta["total_count"],
            "min_speed_seconds": round(min(timings), 3),
            "max_speed_seconds": round(max(timings), 3),
            "individual_timings": [round(t, 3) for t in timings],
        })

    # Overall stats across all batches
    all_timings = [t for timings in batches_dict.values() for t in timings]
    overall_avg = sum(all_timings) / len(all_timings) if all_timings else 0.0
    total_valid = sum(m["valid_count"] for m in batch_meta.values())
    total_req = sum(m["total_count"] for m in batch_meta.values())
    overall_accuracy = (total_valid / total_req * 100) if total_req > 0 else 0.0

    return {
        "prompt_id": prompt_id,
        "prompt_version": version,
        "prompt_name": prompt_name,
        "batches": batch_list,
        "overall_avg_speed": round(overall_avg, 3),
        "overall_accuracy": round(overall_accuracy, 1),
        "total_batches": len(batch_list),
        "total_requests": total_req,
    }


@router.get("/api/performance-testing/prompt-stats")
async def api_get_prompt_stats(
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """Get aggregated performance stats grouped by prompt_id and prompt_version.
    
    Returns an overview of all prompts with their aggregated performance metrics
    including average speed, accuracy, and total runs/requests.
    """
    rows = (
        db.query(PerformanceTestResult)
        .filter(
            PerformanceTestResult.prompt_id.isnot(None),
            PerformanceTestResult.prompt_id != ""
        )
        .order_by(PerformanceTestResult.prompt_id, PerformanceTestResult.prompt_version, PerformanceTestResult.batch_type)
        .all()
    )
    
    # Group by (prompt_id, prompt_version, model_name, batch_type)
    from collections import defaultdict
    groups: dict[tuple, list[dict[str, Any]]] = defaultdict(list)
    
    for r in rows:
        elapsed = 0.0
        if r.response_received_time and r.request_sent_time:
            try:
                sent = datetime.fromisoformat(r.request_sent_time)
                received = datetime.fromisoformat(r.response_received_time)
                elapsed = (received - sent).total_seconds()
            except (ValueError, TypeError):
                elapsed = 0.0
        groups[(r.prompt_id, r.prompt_version, r.model_name, r.batch_type)].append({
            "elapsed": elapsed,
            "valid": r.valid_response,
        })
    
    stats = []
    for (prompt_id, prompt_version, model_name, batch_type), entries in groups.items():
        avg_speed = sum(e["elapsed"] for e in entries) / len(entries)
        valid_count = sum(1 for e in entries if e["valid"] is True)
        accuracy = valid_count / len(entries) * 100
        
        # Get prompt name from PromptVersion table
        prompt_name = f"prompt_{prompt_id}"
        if prompt_version is not None:
            pv = (
                db.query(PromptVersion)
                .filter(
                    PromptVersion.prompt_id == prompt_id,
                    PromptVersion.version == prompt_version,
                )
                .first()
            )
            if pv:
                prompt_name = pv.name
        
        stats.append({
            "prompt_id": prompt_id,
            "prompt_version": prompt_version,
            "prompt_name": prompt_name,
            "model_name": model_name,
            "batch_type": batch_type,
            "avg_speed_seconds": round(avg_speed, 3),
            "accuracy_pct": round(accuracy, 1),
            "total_runs": len(entries),
            "total_requests": len(entries),
        })
    
    return stats


@router.get("/api/performance-testing/prompt-detail")
async def api_get_prompt_detail(
    prompt_id: str,
    version: int | None = None,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Get detailed run information for a specific prompt.
    
    Returns all individual runs for a given prompt_id and version,
    including timing, validity, and batch information.
    """
    query = (
        db.query(PerformanceTestResult)
        .filter(
            PerformanceTestResult.prompt_id == prompt_id,
        )
    )
    if version is not None:
        query = query.filter(PerformanceTestResult.prompt_version == version)
    
    rows = query.order_by(
        PerformanceTestResult.batch_type,
        PerformanceTestResult.request_sent_time
    ).all()
    
    # Get prompt name
    prompt_name = f"prompt_{prompt_id}"
    pv = (
        db.query(PromptVersion)
        .filter(
            PromptVersion.prompt_id == prompt_id,
            PromptVersion.version == version,
        )
        .first()
    )
    if pv:
        prompt_name = pv.name
    
    runs = []
    for r in rows:
        elapsed = 0.0
        if r.response_received_time and r.request_sent_time:
            try:
                sent = datetime.fromisoformat(r.request_sent_time)
                received = datetime.fromisoformat(r.response_received_time)
                elapsed = (received - sent).total_seconds()
            except (ValueError, TypeError):
                elapsed = 0.0
        
        runs.append({
            "batch_uuid": r.batch_uuid,
            "friendly_name": r.friendly_name,
            "batch_type": r.batch_type,
            "model_name": r.model_name,
            "vllm_version": r.vllm_version,
            "thinking_enabled": r.thinking_enabled,
            "request_sent_time": r.request_sent_time,
            "response_received_time": r.response_received_time,
            "elapsed": round(elapsed, 3),
            "valid_response": r.valid_response,
            "response_length": r.response_length,
            "json_malformed": r.json_malformed,
            "request_index": r.request_index,
        })
    
    # Calculate aggregated stats
    if runs:
        avg_speed = sum(r["elapsed"] for r in runs) / len(runs)
        valid_count = sum(1 for r in runs if r["valid_response"] is True)
        accuracy = valid_count / len(runs) * 100
    else:
        avg_speed = 0.0
        accuracy = 0.0
    
    return {
        "prompt_id": prompt_id,
        "prompt_version": version,
        "prompt_name": prompt_name,
        "model_name": runs[0]["model_name"] if runs else None,
        "batch_type": runs[0]["batch_type"] if runs else None,
        "avg_speed_seconds": round(avg_speed, 3),
        "accuracy_pct": round(accuracy, 1),
        "total_runs": len(runs),
        "total_requests": len(runs),
        "runs": runs,
    }


# ── Identifier Endpoints ──────────────────────────────────────────────────────

@router.patch("/api/performance-testing/result/{result_id}/identifier")
async def api_update_identifier(
    result_id: int,
    body: UpdateIdentifierRequest,
    db: Session = Depends(get_db),
) -> UpdateIdentifierResponse:
    """Update the identifier for a specific test result."""
    result = (
        db.query(PerformanceTestResult)
        .filter(PerformanceTestResult.id == result_id)
        .first()
    )

    if result is None:
        return UpdateIdentifierResponse(
            ok=False,
            error=f"No result found with id {result_id}",
        )

    result.identifier = body.identifier
    db.commit()

    return UpdateIdentifierResponse(
        ok=True,
        id=result_id,
        identifier=body.identifier,
    )


@router.post("/api/performance-testing/batch/{batch_uuid}/populate-identifiers")
async def api_populate_identifiers(
    batch_uuid: str,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Populate identifiers for all results in a batch by mapping request_index to guest names."""
    hotel_db = SessionLocal()
    try:
        test_guests = (
            hotel_db.query(Guest)
            .filter(Guest.special_preferences == "performance_test")
            .order_by(Guest.guest_id)
            .all()
        )
    finally:
        hotel_db.close()

    guest_names = [f"{g.first_name} {g.last_name}" for g in test_guests]

    batch_results = (
        db.query(PerformanceTestResult)
        .filter(PerformanceTestResult.batch_uuid == batch_uuid)
        .order_by(PerformanceTestResult.request_index)
        .all()
    )

    updated = 0
    for idx, result in enumerate(batch_results):
        if not result.identifier:
            # Map request_index to guest name (round-robin if more requests than guests)
            guest_idx = result.request_index % len(guest_names) if guest_names else 0
            result.identifier = guest_names[guest_idx] if guest_names else f"guest_{result.request_index}"
            updated += 1

    db.commit()

    return {
        "ok": True,
        "batch_uuid": batch_uuid,
        "updated_count": updated,
        "total_results": len(batch_results),
    }
