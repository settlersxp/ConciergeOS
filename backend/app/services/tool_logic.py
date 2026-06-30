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


class GuestWithReservationsParam(BaseModel):
    """Schema for querying guests with their reservations."""

    first_name: str | None = Field(None, description="Filter by first name (case-insensitive partial match)")
    last_name: str | None = Field(None, description="Filter by last name (case-insensitive partial match)")
    guest_id: int | None = Field(None, description="Filter by specific guest ID")


# ── Executor implementations ────────────────────────────────────────────────


def execute_query_guests(args: dict[str, Any]) -> str:
    """Query guests from the database based on filter params."""
    params = args.get("params", args)
    
    if isinstance(params, dict):
        param_list = [params]
        is_list_input = False
    elif isinstance(params, list):
        param_list = params
        is_list_input = True
    else:
        param_list = [params]
        is_list_input = False

    results = {}

    for i, p in enumerate(param_list):
        if isinstance(p, dict):
            p = TypeAdapter(GuestQuerySchema).validate_python(p)
        
        db = SessionLocal()
        try:
            query = db.query(Guest)
            if p.guest_id is not None:
                query = query.filter(Guest.guest_id == p.guest_id)
            if p.first_name:
                query = query.filter(Guest.first_name.ilike(f"%{p.first_name}%"))
            if p.last_name:
                query = query.filter(Guest.last_name.ilike(f"%{p.last_name}%"))
            if p.is_special_guest is not None:
                query = query.filter(Guest.is_special_guest == p.is_special_guest)

            guests = query.all()
            if not guests:
                results[str(i)] = "No guests found matching the criteria."
            else:
                results[str(i)] = json.dumps(
                    {"count": len(guests), "guests": [_format_guest(g) for g in guests]},
                    indent=2,
                )
        finally:
            db.close()
    
    if not is_list_input:
        return json.dumps({"result": results["0"]}, indent=2)
    
    return json.dumps(results, indent=2)


def execute_query_rooms(args: dict[str, Any]) -> str:
    """Query rooms from the database based on filter params."""
    params = args.get("params", args)
    
    if isinstance(params, dict):
        param_list = [params]
        is_list_input = False
    elif isinstance(params, list):
        param_list = params
        is_list_input = True
    else:
        param_list = [params]
        is_list_input = False

    results = {}

    for i, p in enumerate(param_list):
        if isinstance(p, dict):
            p = TypeAdapter(RoomQuerySchema).validate_python(p)

        db = SessionLocal()
        try:
            query = db.query(Room)
            if p.room_id is not None:
                query = query.filter(Room.room_id == p.room_id)
            if p.name:
                query = query.filter(Room.name.ilike(f"%{p.name}%"))

            rooms = query.all()
            if not rooms:
                results[str(i)] = "No rooms found matching the criteria."
            else:
                room_results = [
                    {
                        "room_id": r.room_id,
                        "name": r.name,
                        "allowed_booking_channel": r.allowed_booking_channel.value,
                        "checkin_time": r.checkin_time,
                        "checkout_time": r.checkout_time,
                    }
                    for r in rooms
                ]
                results[str(i)] = json.dumps({"count": len(room_results), "rooms": room_results}, indent=2)
        finally:
            db.close()

    if not is_list_input:
        return json.dumps({"result": results["0"]}, indent=2)

    return json.dumps(results, indent=2)


def execute_query_reservations(
    args: dict[str, Any]
) -> str:
    """Query reservations from the database based on filter params."""
    params = args.get("params", args)
    
    if isinstance(params, dict):
        param_list = [params]
        is_list_input = False
    elif isinstance(params, list):
        param_list = params
        is_list_input = True
    else:
        param_list = [params]
        is_list_input = False

    results = {}

    for i, p in enumerate(param_list):
        if isinstance(p, dict):
            p = TypeAdapter(ReservationQuerySchema).validate_python(p)

        db = SessionLocal()
        try:
            query = db.query(Reservation)
            if p.reservation_id is not None:
                query = query.filter(Reservation.reservation_id == p.reservation_id)
            if p.guest_id is not None:
                query = query.filter(Reservation.guest_id == p.guest_id)
            if p.room_id is not None:
                query = query.filter(Reservation.room_id == p.room_id)
            if p.status:
                try:
                    query = query.filter(Reservation.status == ReservationStatus(p.status))
                except ValueError:
                    results[str(i)] = (
                        f"Invalid status: {p.status}. "
                        f"Valid options: {', '.join(s.value for s in ReservationStatus)}"
                    )
                    continue
            if p.check_in:
                query = query.filter(Reservation.check_in_date == p.check_in)
            if p.check_out:
                query = query.filter(Reservation.check_out_date == p.check_out)

            reservations = query.all()
            if not reservations:
                results[str(i)] = "No reservations found matching the criteria."
            else:
                results[str(i)] = json.dumps(
                    {
                        "count": len(reservations),
                        "reservations": [_format_reservation(r) for r in reservations],
                    },
                    indent=2,
                )
        finally:
            db.close()

    if not is_list_input:
        return json.dumps({"result": results["0"]}, indent=2)

    return json.dumps(results, indent=2)


def execute_query_guest_with_reservations(args: dict[str, Any]) -> str:
    """Search for guests and return their reservations in a single call.

    PREFER THIS TOOL over calling query_guests + query_reservations separately.
    This tool combines both operations into a single API round-trip, reducing
    LLM turns by 1-2 per query.

    Use this whenever the user query asks about a guest's information AND their
    reservations. Only fall back to separate tools if you have a specific reason.

    Args:
        params: Filter by guest_id, or first_name + last_name.
                Accepts a single dict or a list of dicts for batch queries.

    Returns:
        JSON array of guest objects, each with a nested ``reservations`` list
        containing full reservation details (room, dates, status, etc.).
    """
    params = args.get("params", args)

    if isinstance(params, dict):
        param_list = [params]
        is_list_input = False
    elif isinstance(params, list):
        param_list = params
        is_list_input = True
    else:
        param_list = [params]
        is_list_input = False

    results: list[dict[str, Any]] = []

    for i, p in enumerate(param_list):
        if isinstance(p, dict):
            p = TypeAdapter(GuestWithReservationsParam).validate_python(p)

        db = SessionLocal()
        try:
            query = db.query(Guest)
            if p.guest_id is not None:
                query = query.filter(Guest.guest_id == p.guest_id)
            if p.first_name:
                query = query.filter(Guest.first_name.ilike(f"%{p.first_name}%"))
            if p.last_name:
                query = query.filter(Guest.last_name.ilike(f"%{p.last_name}%"))

            guests = query.all()
            if not guests:
                results.append({"guest_id": str(i), "found": False, "message": "No guests found matching the criteria."})
                continue

            guest_entries: list[dict[str, Any]] = []
            for guest in guests:
                # Fetch reservations in a single query per guest
                reservations = (
                    db.query(Reservation)
                    .filter(Reservation.guest_id == guest.guest_id)
                    .order_by(Reservation.reservation_id)
                    .all()
                )
                reservation_list = [_format_reservation(r) for r in reservations]

                guest_entry = _format_guest(guest)
                guest_entry["reservations"] = reservation_list
                guest_entries.append(guest_entry)

            results.append({
                "guest_id": str(i),
                "found": True,
                "count": len(guest_entries),
                "guests": guest_entries,
            })
        finally:
            db.close()

    if not is_list_input:
        return json.dumps({"result": results[0] if results else {}}, indent=2)

    return json.dumps(results, indent=2, ensure_ascii=False)


def execute_get_hotel_summary(args: dict[str, Any]) -> str:
    """Return a summary of the entire hotel database."""
    params = args.get("params", args)
    
    if isinstance(params, dict):
        param_list = [params]
        is_list_input = False
    elif isinstance(params, list):
        param_list = params
        is_list_input = True
    else:
        param_list = [params]
        is_list_input = False

    results = {}

    for i, p in enumerate(param_list):
        if isinstance(p, dict):
            p = TypeAdapter(HotelSummarySchema).validate_python(p)

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
            results[str(i)] = json.dumps(summary, indent=2)
        finally:
            db.close()

    if not is_list_input:
        return json.dumps({"result": results["0"]}, indent=2)

    return json.dumps(results, indent=2)
