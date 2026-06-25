#!/usr/bin/env python3
"""Performance testing routes."""

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
    TestGuestSchema,
    UpdateValidResponseRequest,
    UpdateValidResponseResponse,
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
