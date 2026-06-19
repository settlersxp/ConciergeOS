#!/usr/bin/env python3
"""
Pydantic schemas for API request/response validation.
"""

from typing import Dict, List

from pydantic import BaseModel, Field

from app.enums import ReservationStatus


# ---------------------------------------------------------------------------
# Reservation schemas
# ---------------------------------------------------------------------------

class ReservationResponse(BaseModel):
    """Single reservation output (includes joined room/guest data)."""

    reservation_id: int
    room_id: int
    room_name: str
    guest_id: int
    first_name: str
    last_name: str
    check_in_date: str
    check_out_date: str
    status: ReservationStatus
    booking_source: str


# ---------------------------------------------------------------------------
# Error schemas
# ---------------------------------------------------------------------------

class ErrorResponse(BaseModel):
    """Detected error on a reservation."""

    reservation_id: int
    room_name: str
    room_id: int
    guest_name: str
    check_in_date: str
    check_out_date: str
    status: ReservationStatus
    error_type: str
    description: str


# ---------------------------------------------------------------------------
# Summary schema
# ---------------------------------------------------------------------------

class ReservationsSummary(BaseModel):
    """Top-level dashboard payload."""

    rooms: Dict[str, List[ReservationResponse]]
    errors: List[ErrorResponse]


# ---------------------------------------------------------------------------
# Shift reservation schemas
# ---------------------------------------------------------------------------

class ShiftRequest(BaseModel):
    """Request body for shifting reservation dates."""

    days: int = Field(default=1, description="Number of days to shift (positive = forward, negative = backward)")


class ShiftSampleEntry(BaseModel):
    check_in: str
    check_out: str


class ShiftResponse(BaseModel):
    """Response from the shift-reservations endpoint."""

    ok: bool
    shifted: int | None = None
    days: int | None = None
    message: str | None = None
    error: str | None = None
    before: List[ShiftSampleEntry] = []
    after: List[ShiftSampleEntry] = []