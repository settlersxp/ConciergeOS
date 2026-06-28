"""Core tool execution logic for LLM interactions.

This module provides the raw database query implementations and data 
serializers used by both the production service and the performance 
testing suite. It is designed to be lightweight and free of LLM 
orchestration or caching overhead.
"""

from __future__ import annotations

import json
from typing import Any, Union

from pydantic import BaseModel, Field, TypeAdapter

from app.db import SessionLocal
from app.models import Guest, Reservation, Room
from app.enums import ReservationStatus


# ── Data serializers ────────────────────────────────────────────────────────


def _format_guest(guest: Guest) -> dict[str, Any]:
    """Serialize a Guest model to a plain dict."""
    return {
        "guest_id": guest.guest_id,
        "first_name": guest.first_name,
        "last_name": guest.last_name,
        "date_of_birth": str(guest.date_of_birth) if guest.date_of_birth else "",
        "is_special_guest": guest.is_special_guest,
        "special_preferences": guest.special_preferences or "",
    }


def _format_reservation(reservation: Reservation) -> dict[str, Any]:
    """Serialize a Reservation model to a plain dict."""
    room_name = ""
    if reservation.room:
        room_name = reservation.room.name

    guest_name = ""
    if reservation.guest:
        guest_name = f"{reservation.guest.first_name} {reservation.guest.last_name}"

    return {
        "reservation_id": reservation.reservation_id,
        "room_id": reservation.room_id,
        "guest_id": reservation.guest_id,
        "check_in": str(reservation.check_in_date),
        "check_out": str(reservation.check_out_date),
        "status": reservation.status.value,
        "booking_source": reservation.booking_source.value,
        "created_at": str(reservation.created_at) if reservation.created_at else "",
        "room_name": room_name,
        "guest_name": guest_name,
    }


# ── Schema Definitions ───────────────────────────────────────────────────────


class GuestQuerySchema(BaseModel):
    """Schema for querying guests."""

    guest_id: int | None = Field(None, description="Filter by specific guest ID")
    first_name: str | None = Field(None, description="Filter by first name (case-insensitive partial match)")
    last_name: str | None = Field(None, description="Filter by last name (case-insensitive partial match)")
    is_special_guest: bool | None = Field(
        None, description="Filter by special guest status. true for special guests only, false for regular guests."
    )


class RoomQuerySchema(BaseModel):
    """Schema for querying rooms."""

    room_id: int | None = Field(None, description="Filter by specific room ID")
    name: str | None = Field(None, description="Filter by room name (case-insensitive partial match)")


class ReservationQuerySchema(BaseModel):
    """Schema for querying reservations."""

    reservation_id: int | None = Field(None, description="Filter by specific reservation ID")
    guest_id: int | None = Field(None, description="Filter by guest ID")
    room_id: int | None = Field(None, description="Filter by room ID")
    status: str | None = Field(
        None,
        description="Filter by reservation status",
    )
    check_in: str | None = Field(None, description="Filter by check-in date (ISO format YYYY-MM-DD)")
    check_out: str | None = Field(None, description="Filter by check-out date (ISO format YYYY-MM-DD)")


class HotelSummarySchema(BaseModel):
    """Schema for getting hotel summary."""

    pass


# ── Executor implementations ────────────────────────────────────────────────


def execute_query_guests(params: Union[GuestQuerySchema, dict[str, Any]]) -> str:
    """Query guests from the database based on filter params."""
    if isinstance(params, dict):
        params = TypeAdapter(GuestQuerySchema).validate_python(params)

    db = SessionLocal()
    try:
        query = db.query(Guest)
        if params.guest_id is not None:
            query = query.filter(Guest.guest_id == params.guest_id)
        if params.first_name:
            query = query.filter(Guest.first_name.ilike(f"%{params.first_name}%"))
        if params.last_name:
            query = query.filter(Guest.last_name.ilike(f"%{params.last_name}%"))
        if params.is_special_guest is not None:
            query = query.filter(Guest.is_special_guest == params.is_special_guest)

        guests = query.all()
        if not guests:
            return "No guests found matching the criteria."

        return json.dumps(
            {"count": len(guests), "guests": [_format_guest(g) for g in guests]},
            indent=2,
        )
    finally:
        db.close()


def execute_query_rooms(params: Union[RoomQuerySchema, dict[str, Any]]) -> str:
    """Query rooms from the database based on filter params."""
    if isinstance(params, dict):
        params = TypeAdapter(RoomQuerySchema).validate_python(params)

    db = SessionLocal()
    try:
        query = db.query(Room)
        if params.room_id is not None:
            query = query.filter(Room.room_id == params.room_id)
        if params.name:
            query = query.filter(Room.name.ilike(f"%{params.name}%"))

        rooms = query.all()
        if not rooms:
            return "No rooms found matching the criteria."

        results = [
            {
                "room_id": r.room_id,
                "name": r.name,
                "allowed_booking_channel": r.allowed_booking_channel.value,
                "checkin_time": r.checkin_time,
                "checkout_time": r.checkout_time,
            }
            for r in rooms
        ]
        return json.dumps({"count": len(results), "rooms": results}, indent=2)
    finally:
        db.close()


def execute_query_reservations(
    params: Union[ReservationQuerySchema, dict[str, Any]]
) -> str:
    """Query reservations from the database based on filter params."""
    if isinstance(params, dict):
        params = TypeAdapter(ReservationQuerySchema).validate_python(params)

    db = SessionLocal()
    try:
        query = db.query(Reservation)
        if params.reservation_id is not None:
            query = query.filter(Reservation.reservation_id == params.reservation_id)
        if params.guest_id is not None:
            query = query.filter(Reservation.guest_id == params.guest_id)
        if params.room_id is not None:
            query = query.filter(Reservation.room_id == params.room_id)
        if params.status:
            try:
                query = query.filter(Reservation.status == ReservationStatus(params.status))
            except ValueError:
                return (
                    f"Invalid status: {params.status}. "
                    f"Valid options: {', '.join(s.value for s in ReservationStatus)}"
                )
        if params.check_in:
            query = query.filter(Reservation.check_in_date == params.check_in)
        if params.check_out:
            query = query.filter(Reservation.check_out_date == params.check_out)

        reservations = query.all()
        if not reservations:
            return "No reservations found matching the criteria."

        return json.dumps(
            {
                "count": len(reservations),
                "reservations": [_format_reservation(r) for r in reservations],
            },
            indent=2,
        )
    finally:
        db.close()


def execute_get_hotel_summary(params: Union[HotelSummarySchema, dict[str, Any]]) -> str:
    """Return a summary of the entire hotel database."""
    if isinstance(params, dict):
        params = TypeAdapter(HotelSummarySchema).validate_python(params)

    db = SessionLocal()
    try:
        status_counts: dict[str, int] = {
            status.value: db.query(Reservation).filter(Reservation.status == status).count()
            for status in ReservationStatus
        }

        summary = {
            "total_guests": db.query(Guest).count(),
            "total_rooms": db.query(Room).count(),
            "total_reservations": db.query(Reservation).count(),
            "special_guests": db.query(Guest).filter(Guest.is_special_guest.is_(True)).count(),
            "reservations_by_status": status_counts,
        }
        return json.dumps(summary, indent=2)
    finally:
        db.close()
