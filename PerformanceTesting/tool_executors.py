"""Tool executor functions and registry for LLM tool calling.

Each executor queries the hotel database and returns a JSON string result.
The ``TOOL_EXECUTORS`` dictionary maps tool names (as referenced in LLM
tool definitions) to these callable implementations.
"""

from __future__ import annotations

import json
from typing import Any, Callable

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


# ── Executor implementations ────────────────────────────────────────────────


def execute_query_guests(params: dict[str, Any]) -> str:
    """Query guests from the database by their guest IDs.
    
    Accepts a single guest ID or an array of guest IDs.
    Returns all matching guests with their details.
    
    Args:
        params: Must contain 'guest_ids' - a single integer or array of integers.
    
    Returns:
        JSON string with guest count and array of guest objects.
    """
    db = SessionLocal()
    try:
        guest_ids = params.get("guest_ids")
        if guest_ids is None:
            return "No guest IDs provided. The 'guest_ids' parameter is required."

        # Accept a single ID or an array of IDs
        if isinstance(guest_ids, int):
            guest_ids = [guest_ids]

        if not isinstance(guest_ids, list) or not guest_ids:
            return "Invalid 'guest_ids' parameter. Must be a single integer or an array of integers."

        query = db.query(Guest).filter(Guest.guest_id.in_(guest_ids))

        guests = query.all()
        if not guests:
            return f"No guests found with the provided IDs: {guest_ids}"

        return json.dumps(
            {"count": len(guests), "guests": [_format_guest(g) for g in guests]},
            indent=2,
        )
    finally:
        db.close()


def execute_query_rooms(params: dict[str, Any]) -> str:
    """Query rooms from the database based on filter params."""
    db = SessionLocal()
    try:
        query = db.query(Room)
        room_id = params.get("room_id")
        if room_id is not None:
            query = query.filter(Room.room_id == room_id)
        name = params.get("name")
        if name:
            query = query.filter(Room.name.ilike(f"%{name}%"))

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


def execute_query_reservations(params: dict[str, Any]) -> str:
    """Query reservations from the database with flexible filtering.
    
    All parameters are optional. The LLM can use any combination of filters:
    - reservation_ids: Filter by specific reservation ID(s)
    - guest_ids: Filter by guest ID(s)
    - room_ids: Filter by room ID(s)
    - statuses: Filter by reservation status(ies)
    - check_in / check_out: Filter by date(s)
    
    If no parameters are provided, returns all reservations (not recommended for large datasets).
    
    Args:
        params: Any combination of optional filter parameters.
    
    Returns:
        JSON string with reservation count and array of reservation objects.
    """
    db = SessionLocal()
    try:
        query = db.query(Reservation)

        # Filter: reservation_ids (array or single integer)
        reservation_ids = params.get("reservation_ids")
        if reservation_ids is not None:
            if isinstance(reservation_ids, int):
                reservation_ids = [reservation_ids]
            elif not isinstance(reservation_ids, list):
                reservation_ids = [reservation_ids]
            if reservation_ids:
                query = query.filter(Reservation.reservation_id.in_(reservation_ids))

        # Optional filter: guest_ids (array of integers)
        guest_ids = params.get("guest_ids")
        if guest_ids is not None:
            if isinstance(guest_ids, int):
                guest_ids = [guest_ids]
            elif not isinstance(guest_ids, list):
                guest_ids = [guest_ids]
            if guest_ids:
                query = query.filter(Reservation.guest_id.in_(guest_ids))

        # Optional filter: room_ids (array of integers)
        room_ids = params.get("room_ids")
        if room_ids is not None:
            if isinstance(room_ids, int):
                room_ids = [room_ids]
            elif not isinstance(room_ids, list):
                room_ids = [room_ids]
            if room_ids:
                query = query.filter(Reservation.room_id.in_(room_ids))

        # Optional filter: statuses (array of string enum values)
        statuses = params.get("statuses")
        if statuses is not None:
            if isinstance(statuses, str):
                # Accept single status string for backward compatibility
                statuses = [statuses]
            if isinstance(statuses, list) and statuses:
                # Validate each status value against the enum
                valid_statuses = []
                invalid_statuses = []
                for s in statuses:
                    try:
                        valid_statuses.append(ReservationStatus(s))
                    except ValueError:
                        invalid_statuses.append(s)
                
                if invalid_statuses:
                    valid_options = ", ".join(s.value for s in ReservationStatus)
                    return f"Invalid status values: {invalid_statuses}. Valid options: {valid_options}"
                
                if valid_statuses:
                    query = query.filter(Reservation.status.in_(valid_statuses))

        # Optional filter: check_in (date string)
        check_in = params.get("check_in")
        if check_in:
            query = query.filter(Reservation.check_in_date == check_in)

        # Optional filter: check_out (date string)
        check_out = params.get("check_out")
        if check_out:
            query = query.filter(Reservation.check_out_date == check_out)

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


def execute_get_hotel_summary(params: dict[str, Any]) -> str:
    """Return a summary of the entire hotel database."""
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


# ── Registry ────────────────────────────────────────────────────────────────

TOOL_EXECUTORS: dict[str, Callable[[dict[str, Any]], str]] = {
    "query_guests": execute_query_guests,
    "query_rooms": execute_query_rooms,
    "query_reservations": execute_query_reservations,
    "get_hotel_summary": execute_get_hotel_summary,
}