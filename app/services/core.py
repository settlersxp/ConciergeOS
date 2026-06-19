#!/usr/bin/env python3
"""
Business logic for querying reservations and detecting errors.

Uses SQLAlchemy ORM for database access and Pydantic schemas for validation.
"""

import json
import os
from datetime import date
from pathlib import Path
from typing import Any, Dict, List

from app.db import SessionLocal
from app.enums import ReservationStatus
from app.models import Guest, Reservation, Room
from app.schemas import ErrorResponse, ReservationResponse

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_BASE_DIR = Path(os.path.dirname(os.path.abspath(__file__))).parent
ERRONEOUS_JSON = _BASE_DIR / "Generator" / "erroneous_reservations.json"


# ---------------------------------------------------------------------------
# Data conversion
# ---------------------------------------------------------------------------

def _orm_to_reservation(resp: ReservationResponse) -> Dict[str, Any]:
    """Convert a Pydantic ReservationResponse to a plain dict for template rendering."""
    return resp.model_dump()


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------

def get_all_reservations_grouped_by_room() -> Dict[str, List[Dict[str, Any]]]:
    """
    Fetch all reservations joined with room and guest data,
    grouped by room name.
    """
    db = SessionLocal()
    try:
        rows = (
            db.query(Reservation)
            .join(Room, Reservation.room_id == Room.room_id)
            .join(Guest, Reservation.guest_id == Guest.guest_id)
            .order_by(Room.name, Reservation.room_id, Reservation.check_in_date)
            .all()
        )

        rooms: Dict[str, List[Dict[str, Any]]] = {}
        for res in rows:
            room_name = res.room.name
            if room_name not in rooms:
                rooms[room_name] = []

            schema = ReservationResponse(
                reservation_id=res.reservation_id,
                room_id=res.room_id,
                room_name=room_name,
                guest_id=res.guest_id,
                first_name=res.guest.first_name,
                last_name=res.guest.last_name,
                check_in_date=res.check_in_date,
                check_out_date=res.check_out_date,
                status=res.status,
                booking_source=res.booking_source,
            )
            rooms[room_name].append(_orm_to_reservation(schema))

        return rooms
    finally:
        db.close()


def get_error_ids() -> Dict[str, List[int]]:
    """
    Load the erroneous_reservations.json created by setup_errors.py
    and return the error ID sets.
    """
    if not os.path.exists(ERRONEOUS_JSON):
        return {"status_errors": [], "date_errors": [], "all_error_ids": []}

    with open(ERRONEOUS_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)

    return {
        "status_errors": data.get("status_errors", []),
        "date_errors": data.get("date_errors", []),
        "all_error_ids": data.get("all_error_ids", []),
    }


def detect_errors() -> List[Dict[str, Any]]:
    """
    Return a list of error details for reservations flagged in
    erroneous_reservations.json, including what's wrong with each.
    """
    error_info = get_error_ids()
    status_error_ids = set(error_info["status_errors"])
    date_error_ids = set(error_info["date_errors"])
    all_error_ids = status_error_ids | date_error_ids

    if not all_error_ids:
        return []

    db = SessionLocal()
    try:
        today = date.today()

        rows = (
            db.query(Reservation)
            .join(Room, Reservation.room_id == Room.room_id)
            .join(Guest, Reservation.guest_id == Guest.guest_id)
            .filter(Reservation.reservation_id.in_(all_error_ids))
            .order_by(Reservation.reservation_id)
            .all()
        )

        errors: List[Dict[str, Any]] = []

        for res in rows:
            rid = res.reservation_id
            check_in = date.fromisoformat(res.check_in_date)
            check_out = date.fromisoformat(res.check_out_date)
            status = res.status

            descriptions = []

            # Status error analysis
            if rid in status_error_ids:
                if status == ReservationStatus.CANCELLED and check_in < today and check_out >= today:
                    descriptions.append(
                        f"Status is CANCELLED but dates ({res.check_in_date} → {res.check_out_date}) "
                        f"indicate an active stay (likely should be CHECKED_IN)."
                    )
                elif status == ReservationStatus.CHECKED_OUT and check_in == today and check_out > today:
                    descriptions.append(
                        f"Status is CHECKED_OUT but check-in is today ({res.check_in_date}) "
                        f"with future check-out ({res.check_out_date}) (likely should be CONFIRMED)."
                    )
                elif status == ReservationStatus.CHECKED_OUT and check_in < today and check_out >= today:
                    descriptions.append(
                        f"Status is CHECKED_OUT but dates ({res.check_in_date} → {res.check_out_date}) "
                        f"indicate an active stay (likely should be CHECKED_IN)."
                    )

            # Date error analysis
            if rid in date_error_ids:
                if status == ReservationStatus.CHECKED_IN and check_out < today:
                    descriptions.append(
                        f"Status is CHECKED_IN but check-out date ({res.check_out_date}) "
                        f"is in the past — dates are unsynchronized."
                    )
                elif status == ReservationStatus.CHECKED_OUT and check_in > today:
                    descriptions.append(
                        f"Status is CHECKED_OUT but check-in date ({res.check_in_date}) "
                        f"is in the future — dates are unsynchronized."
                    )

            # If no specific description matched, provide a generic one
            if not descriptions:
                if rid in status_error_ids:
                    descriptions.append("Flagged as a status error (status may not match date range).")
                if rid in date_error_ids:
                    descriptions.append("Flagged as a date error (dates may be unsynchronized with status).")

            error_type = []
            if rid in status_error_ids:
                error_type.append("status")
            if rid in date_error_ids:
                error_type.append("date")

            error_schema = ErrorResponse(
                reservation_id=rid,
                room_name=res.room.name,
                room_id=res.room_id,
                guest_name=f"{res.guest.first_name} {res.guest.last_name}",
                check_in_date=res.check_in_date,
                check_out_date=res.check_out_date,
                status=status,
                error_type=" / ".join(error_type),
                description=" ".join(descriptions),
            )
            errors.append(error_schema.model_dump())

        return errors
    finally:
        db.close()


def get_reservations_summary() -> Dict[str, Any]:
    """
    Return the full data payload for the dashboard:
    reservations grouped by room and the list of errors.
    """
    return {
        "rooms": get_all_reservations_grouped_by_room(),
        "errors": detect_errors(),
    }