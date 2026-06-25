#!/usr/bin/env python3
"""Performance testing routes."""

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.db_performance import get_performance_db
from app.models import Guest, PerformanceTestResult, Reservation, Room
from app.schemas import (
    DeleteBatchResponse,
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

router = APIRouter()

_DATABASE_PATH = Path(__file__).resolve().parent.parent.parent / "performance_tests.db"


# ── Run Performance Tests ────────────────────────────────────────────────────

@router.post("/api/performance-testing")
async def api_run_performance_testing(body: PerformanceTestRequest) -> dict[str, Any]:
    """Run performance tests with the provided settings."""

    from PerformanceTesting.run_performance_tests import TestSettings, run_tests  # noqa: cwd
    from app.services.llm import SYSTEM_PROMPT, TOOL_DEFINITIONS  # noqa: cwd

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
        system_prompt=body.system_prompt or SYSTEM_PROMPT,
        user_prompt=body.user_prompt,
        expected_response_format=body.expected_response_format,
        data_format=body.data_format,
        use_tool_calling=use_tool_calling,
        tool_definitions=TOOL_DEFINITIONS if use_tool_calling else [],
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
    db: Session = Depends(get_performance_db),
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
    db: Session = Depends(get_performance_db),
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
    db: Session = Depends(get_performance_db),
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


@router.get("/api/performance-testing/results-by-batch")
async def api_get_results_by_batch(
    batch_uuid: str,
    db: Session = Depends(get_performance_db),
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
    db: Session = Depends(get_performance_db),
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
    db: Session = Depends(get_performance_db),
) -> DeleteBatchResponse:
    """Delete all test results for a specific batch identified by UUID."""
    deleted_count = (
        db.query(PerformanceTestResult)
        .filter(PerformanceTestResult.batch_uuid == batch_uuid)
        .delete(synchronize_session="fetch")
    )
    db.commit()

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
) -> tuple[bool | None, str | None]:
    """Validate a single guest-response pair using the LLM.

    Compares the full ground-truth JSON against the LLM response field-by-field.

    Returns (is_match, llm_reasoning).
    """
    from openai import OpenAI

    from app.services.llm import get_llm_config

    client, model = get_llm_config()

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

    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
        )
        answer = resp.choices[0].message.content or "{}"

        import json
        parsed = json.loads(answer)
        is_match = parsed.get("is_match")
        reasoning = parsed.get("reasoning", "")
        return is_match, reasoning
    except Exception as e:
        return None, f"Validation error: {e}"


# ── Validate Guests Endpoint ─────────────────────────────────────────────────

@router.post("/api/performance-testing/validate-guests")
async def api_validate_guests(
    body: ValidateGuestsRequest,
    db: Session = Depends(get_performance_db),
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

            is_match, reasoning = _validate_single_pair(
                ground_truth_json=ground_truth_json,
                ground_truth_name=full_name,
                response_content=matched_result.response_content if matched_result else None,
            )

            validation_results.append(
                SingleGuestValidation(
                    guest_id=guest.guest_id,
                    guest_name=full_name,
                    result_id=matched_result.id if matched_result else None,
                    is_match=is_match,
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


# ── Identifier Endpoints ──────────────────────────────────────────────────────

@router.patch("/api/performance-testing/result/{result_id}/identifier")
async def api_update_identifier(
    result_id: int,
    body: UpdateIdentifierRequest,
    db: Session = Depends(get_performance_db),
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
    db: Session = Depends(get_performance_db),
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
