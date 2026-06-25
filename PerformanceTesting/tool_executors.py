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
    """Query guests from the database based on filter params."""
    db = SessionLocal()
    try:
        query = db.query(Guest)
        guest_id = params.get("guest_id")
        if guest_id is not None:
            query = query.filter(Guest.guest_id == guest_id)
        first_name = params.get("first_name")
        if first_name:
            query = query.filter(Guest.first_name.ilike(f"%{first_name}%"))
        last_name = params.get("last_name")
        if last_name:
            query = query.filter(Guest.last_name.ilike(f"%{last_name}%"))
        is_special = params.get("is_special_guest")
        if is_special is not None:
            query = query.filter(Guest.is_special_guest == bool(is_special))

        guests = query.all()
        if not guests:
            return "No guests found matching the criteria."

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
    """Query reservations from the database based on filter params."""
    db = SessionLocal()
    try:
        query = db.query(Reservation)
        reservation_id = params.get("reservation_id")
        if reservation_id is not None:
            query = query.filter(Reservation.reservation_id == reservation_id)
        guest_id = params.get("guest_id")
        if guest_id is not None:
            query = query.filter(Reservation.guest_id == guest_id)
        room_id = params.get("room_id")
        if room_id is not None:
            query = query.filter(Reservation.room_id == room_id)
        status_str = params.get("status")
        if status_str:
            try:
                query = query.filter(Reservation.status == ReservationStatus(status_str))
            except ValueError:
                return (
                    f"Invalid status: {status_str}. "
                    f"Valid options: {', '.join(s.value for s in ReservationStatus)}"
                )
        check_in = params.get("check_in")
        if check_in:
            query = query.filter(Reservation.check_in_date == check_in)
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