#!/usr/bin/env python3
"""
Business logic for querying reservations and detecting errors.

Imports database helpers from Generator/utils to maintain a single
source of truth for DB connection management.
"""

import json
import os
import sqlite3
from datetime import date
from typing import Any, Dict, List

from Generator.utils import DB_PATH, init_connection

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
GENERATOR_DIR = os.path.dirname(DB_PATH)
ERRONEOUS_JSON = os.path.join(GENERATOR_DIR, "Generator", "erroneous_reservations.json")


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

def _row_to_reservation(row: sqlite3.Row) -> Dict[str, Any]:
    """Convert a database row to a reservation dict."""
    return {
        "reservation_id": row["reservation_id"],
        "room_id": row["room_id"],
        "room_name": row["name"],
        "guest_id": row["guest_id"],
        "first_name": row["first_name"],
        "last_name": row["last_name"],
        "check_in_date": row["check_in_date"],
        "check_out_date": row["check_out_date"],
        "status": row["status"],
        "booking_source": row["booking_source"],
    }


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------

def get_all_reservations_grouped_by_room() -> Dict[str, List[Dict[str, Any]]]:
    """
    Fetch all reservations joined with room and guest data,
    grouped by room name.
    """
    conn = init_connection(DB_PATH)
    try:
        query = """
            SELECT r.reservation_id, r.room_id, Rooms.name,
                   r.guest_id, g.first_name, g.last_name,
                   r.check_in_date, r.check_out_date,
                   r.status, r.booking_source
            FROM Reservations r
            JOIN Rooms ON r.room_id = Rooms.room_id
            JOIN Guests g ON r.guest_id = g.guest_id
            ORDER BY Rooms.name, r.room_id, r.check_in_date
        """
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(query)
        rows = cursor.fetchall()

        rooms: Dict[str, List[Dict[str, Any]]] = {}
        for row in rows:
            room_name = row["name"]
            if room_name not in rooms:
                rooms[room_name] = []
            rooms[room_name].append(_row_to_reservation(row))

        return rooms
    finally:
        conn.close()


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

    conn = init_connection(DB_PATH)
    try:
        conn.row_factory = sqlite3.Row
        today = date.today()

        errors: List[Dict[str, Any]] = []

        placeholders = ",".join("?" for _ in all_error_ids)
        query = f"""
            SELECT r.reservation_id, r.room_id, Rooms.name,
                   r.guest_id, g.first_name, g.last_name,
                   r.check_in_date, r.check_out_date,
                   r.status, r.booking_source
            FROM Reservations r
            JOIN Rooms ON r.room_id = Rooms.room_id
            JOIN Guests g ON r.guest_id = g.guest_id
            WHERE r.reservation_id IN ({placeholders})
            ORDER BY r.reservation_id
        """
        cursor = conn.execute(query, list(all_error_ids))

        for row in cursor.fetchall():
            rid = row["reservation_id"]
            check_in = date.fromisoformat(row["check_in_date"])
            check_out = date.fromisoformat(row["check_out_date"])
            status = row["status"]

            descriptions = []

            # Status error analysis
            if rid in status_error_ids:
                if status == "CANCELLED" and check_in < today and check_out >= today:
                    descriptions.append(
                        f"Status is CANCELLED but dates ({row['check_in_date']} → {row['check_out_date']}) "
                        f"indicate an active stay (likely should be CHECKED_IN)."
                    )
                elif status == "CHECKED_OUT" and check_in == today and check_out > today:
                    descriptions.append(
                        f"Status is CHECKED_OUT but check-in is today ({row['check_in_date']}) "
                        f"with future check-out ({row['check_out_date']}) (likely should be CONFIRMED)."
                    )
                elif status == "CHECKED_OUT" and check_in < today and check_out >= today:
                    descriptions.append(
                        f"Status is CHECKED_OUT but dates ({row['check_in_date']} → {row['check_out_date']}) "
                        f"indicate an active stay (likely should be CHECKED_IN)."
                    )

            # Date error analysis
            if rid in date_error_ids:
                if status == "CHECKED_IN" and check_out < today:
                    descriptions.append(
                        f"Status is CHECKED_IN but check-out date ({row['check_out_date']}) "
                        f"is in the past — dates are unsynchronized."
                    )
                elif status == "CHECKED_OUT" and check_in > today:
                    descriptions.append(
                        f"Status is CHECKED_OUT but check-in date ({row['check_in_date']}) "
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

            errors.append({
                "reservation_id": rid,
                "room_name": row["name"],
                "room_id": row["room_id"],
                "guest_name": f"{row['first_name']} {row['last_name']}",
                "check_in_date": row["check_in_date"],
                "check_out_date": row["check_out_date"],
                "status": status,
                "error_type": " / ".join(error_type),
                "description": " ".join(descriptions),
            })

        return errors
    finally:
        conn.close()


def get_reservations_summary() -> Dict[str, Any]:
    """
    Return the full data payload for the dashboard:
    reservations grouped by room and the list of errors.
    """
    return {
        "rooms": get_all_reservations_grouped_by_room(),
        "errors": detect_errors(),
    }