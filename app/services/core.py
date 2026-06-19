#!/usr/bin/env python3
"""
Business logic for querying reservations and detecting errors.

Uses SQLAlchemy ORM for database access and Pydantic schemas for validation.
"""

import json
import os
from datetime import date
from pathlib import Path
from typing import Dict, List

from sqlalchemy.orm import Query, Session

from app.db import SessionLocal
from app.enums import ReservationStatus
from app.models import Guest, Reservation, Room
from app.schemas import ErrorResponse, ReservationResponse, ReservationsSummary


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_BASE_DIR = Path(os.path.dirname(os.path.abspath(__file__))).parent.parent
ERRONEOUS_JSON = _BASE_DIR / "Generator" / "erroneous_reservations.json"


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------

def _base_reservation_query(db: Session) -> Query[Reservation]:
    """
    Build the base query for reservations joined with Room and Guest.
    Reused by both get_all_reservations_grouped_by_room and detect_errors.
    """
    return (
        db.query(Reservation)
        .join(Room, Reservation.room_id == Room.room_id)
        .join(Guest, Reservation.guest_id == Guest.guest_id)
    )


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------

def get_all_reservations_grouped_by_room() -> Dict[str, List[ReservationResponse]]:
    """
    Fetch all reservations joined with room and guest data,
    grouped by room name. Returns Pydantic ReservationResponse objects.
    """
    db = SessionLocal()
    try:
        rows = (
            _base_reservation_query(db)
            .order_by(Room.name, Reservation.room_id, Reservation.check_in_date)
            .all()
        )

        rooms: Dict[str, List[ReservationResponse]] = {}
        for res in rows:
            room_name = res.room.name
            if room_name not in rooms:
                rooms[room_name] = []

            rooms[room_name].append(ReservationResponse.from_orm_reservation(res))

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


def detect_errors() -> List[ErrorResponse]:
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
            _base_reservation_query(db)
            .filter(Reservation.reservation_id.in_(all_error_ids))
            .order_by(Reservation.reservation_id)
            .all()
        )

        errors: List[ErrorResponse] = []

        for res in rows:
            rid = res.reservation_id
            # Dates are now native `date` objects thanks to SQLAlchemy Date type
            check_in = res.check_in_date
            check_out = res.check_out_date
            status = res.status

            descriptions = []

            # Status error analysis
            if rid in status_error_ids:
                if status == ReservationStatus.CANCELLED and check_in < today and check_out >= today:
                    descriptions.append(
                        f"Status is CANCELLED but dates ({check_in.isoformat()} → {check_out.isoformat()}) "
                        f"indicate an active stay (likely should be CHECKED_IN)."
                    )
                elif status == ReservationStatus.CHECKED_OUT and check_in == today and check_out > today:
                    descriptions.append(
                        f"Status is CHECKED_OUT but check-in is today ({check_in.isoformat()}) "
                        f"with future check-out ({check_out.isoformat()}) (likely should be CONFIRMED)."
                    )
                elif status == ReservationStatus.CHECKED_OUT and check_in < today and check_out >= today:
                    descriptions.append(
                        f"Status is CHECKED_OUT but dates ({check_in.isoformat()} → {check_out.isoformat()}) "
                        f"indicate an active stay (likely should be CHECKED_IN)."
                    )

            # Date error analysis
            if rid in date_error_ids:
                if status == ReservationStatus.CHECKED_IN and check_out < today:
                    descriptions.append(
                        f"Status is CHECKED_IN but check-out date ({check_out.isoformat()}) "
                        f"is in the past — dates are unsynchronized."
                    )
                elif status == ReservationStatus.CHECKED_OUT and check_in > today:
                    descriptions.append(
                        f"Status is CHECKED_OUT but check-in date ({check_in.isoformat()}) "
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

            errors.append(ErrorResponse(
                reservation_id=rid,
                room_name=res.room.name,
                room_id=res.room_id,
                guest_name=f"{res.guest.first_name} {res.guest.last_name}",
                check_in_date=check_in,
                check_out_date=check_out,
                status=status,
                error_type=" / ".join(error_type),
                description=" ".join(descriptions),
            ))

        return errors
    finally:
        db.close()


def get_reservations_summary() -> ReservationsSummary:
    """
    Return the full data payload for the dashboard:
    reservations grouped by room and the list of errors.
    """
    return ReservationsSummary(
        rooms=get_all_reservations_grouped_by_room(),
        errors=detect_errors(),
    )