#!/usr/bin/env python3
"""
Pydantic schemas for API request/response validation.
"""

from datetime import date
from typing import TYPE_CHECKING, Dict, List

from pydantic import BaseModel, Field

from app.enums import BookingSource, ReservationStatus

if TYPE_CHECKING:
    from app.models import Reservation


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
    check_in_date: date
    check_out_date: date
    status: ReservationStatus
    booking_source: BookingSource

    @classmethod
    def from_orm_reservation(
        cls,
        reservation: "Reservation",
    ) -> "ReservationResponse":
        """Create a ReservationResponse directly from an ORM Reservation object (room/guest must be loaded)."""
        return cls(
            reservation_id=reservation.reservation_id,
            room_id=reservation.room_id,
            room_name=reservation.room.name,
            guest_id=reservation.guest_id,
            first_name=reservation.guest.first_name,
            last_name=reservation.guest.last_name,
            check_in_date=reservation.check_in_date,
            check_out_date=reservation.check_out_date,
            status=reservation.status,
            booking_source=reservation.booking_source,
        )


# ---------------------------------------------------------------------------
# Error schemas
# ---------------------------------------------------------------------------

class ErrorResponse(BaseModel):
    """Detected error on a reservation."""

    reservation_id: int
    room_name: str
    room_id: int
    guest_name: str
    check_in_date: date
    check_out_date: date
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

    days: int = Field(
        default=1,
        description="Number of days to shift (positive = forward, negative = backward)"
    )


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


# ---------------------------------------------------------------------------
# Guest search schemas
# ---------------------------------------------------------------------------

class GuestSearchRequest(BaseModel):
    """Request body for searching a guest by name."""

    customer_name: str = Field(..., description="Full or partial name of the customer to search for")


class GuestSearchResponse(BaseModel):
    """Response from the guest-search endpoint."""

    query: str
    llm_response: str
