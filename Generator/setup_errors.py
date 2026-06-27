#!/usr/bin/env python3
"""
Setup Erroneous Reservations from Name Collisions

Identifies reservations that share the same Guest name (first_name + last_name)
across 2+ different rooms (name collisions) and introduces controlled errors:

  Error Type A - Erroneous Status (2 reservations):
    1. CHECKED_IN reservation (check_in past, check_out future) → set status to CANCELLED
    2. CONFIRMED reservation (check_in today, check_out future) → set status to CHECKED_OUT

  Error Type B - Unsynchronized Dates (2 reservations):
    3. CHECKED_IN reservation → move check_out_date to the past
    4. CHECKED_OUT reservation → move check_in_date to the future

Console output displays the before/after for each affected reservation.
IDs are persisted to erroneous_reservations.json for daily reuse.

Uses SQLAlchemy ORM models from the app package.

Usage:
    python Generator/setup_errors.py
"""

import json
import os
import sys
from datetime import date
from typing import Any, Dict, List, Optional, Tuple, cast

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.db import SessionLocal
from app.enums import BookingSource, ReservationStatus
from app.models import Guest, Reservation
from sqlalchemy.orm import Session
from utils import (
    BASE_DIR,
    DB_PATH,
    is_checked_in_type,
    is_confirmed_type,
    is_checked_out_type,
)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
OUTPUT_JSON = os.path.join(BASE_DIR, "erroneous_reservations.json")

# ---------------------------------------------------------------------------
# Excluded reservation IDs — these will NEVER be turned into erroneous data
# ---------------------------------------------------------------------------
EXCLUDED_RESERVATION_IDS: List[int] = [
    # Add IDs here, e.g.: 1, 42, 99
]

# ---------------------------------------------------------------------------
# Valid status values (matches the CHECK constraint in the schema)
# ---------------------------------------------------------------------------
VALID_STATUSES = tuple(s.value for s in ReservationStatus)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def fetch_collision_reservation_ids(db: Session) -> List[int]:
    """
    Return reservation_ids that belong to guests whose (first_name, last_name)
    appears on reservations in 2+ different rooms.

    These are the name-collision reservations created by populate_reservations.py.
    """
    from sqlalchemy import text

    result = db.execute(text("""
        SELECT DISTINCT r.reservation_id
        FROM Reservations r
        JOIN Guests g ON r.guest_id = g.guest_id
        WHERE EXISTS (
            SELECT 1
            FROM Reservations r2
            JOIN Guests g2 ON r2.guest_id = g2.guest_id
            WHERE g2.first_name = g.first_name
              AND g2.last_name = g.last_name
              AND r2.room_id <> r.room_id
        )
        ORDER BY r.reservation_id
    """))
    return [row[0] for row in result.fetchall()]


def fetch_reservation_details(db: Session, reservation_id: int) -> Optional[Dict[str, Any]]:
    """Return full reservation row as a dict, or None if not found."""
    reservation = (
        db.query(Reservation)
        .filter(Reservation.reservation_id == reservation_id)
        .first()
    )
    if not reservation:
        return None

    guest = reservation.guest
    return {
        "reservation_id": reservation.reservation_id,
        "room_id": reservation.room_id,
        "guest_id": reservation.guest_id,
        "check_in_date": reservation.check_in_date.isoformat() if isinstance(reservation.check_in_date, date) else str(reservation.check_in_date),
        "check_out_date": reservation.check_out_date.isoformat() if isinstance(reservation.check_out_date, date) else str(reservation.check_out_date),
        "status": reservation.status.value if isinstance(reservation.status, ReservationStatus) else str(reservation.status),
        "booking_source": reservation.booking_source.value if isinstance(reservation.booking_source, BookingSource) else str(reservation.booking_source),
        "first_name": guest.first_name,
        "last_name": guest.last_name,
    }


# ---------------------------------------------------------------------------
# Error introduction
# ---------------------------------------------------------------------------

class ErrorRecord:
    """Tracks a single erroneous change."""
    def __init__(self, reservation_id: int, error_type: str,
                 field: str, before: str, after: str, guest_name: str, room_id: int):
        self.reservation_id = reservation_id
        self.error_type = error_type       # "status" or "date"
        self.field = field                 # e.g. "status", "check_out_date"
        self.before = before
        self.after = after
        self.guest_name = guest_name
        self.room_id = room_id

    def __repr__(self) -> str:
        return (
            f"  reservation_id={self.reservation_id}, room={self.room_id}, "
            f"guest='{self.guest_name}', {self.error_type} error: "
            f"{self.field} '{self.before}' → '{self.after}'"
        )


def apply_errors(db: Session,
                 collision_ids: List[int],
                 today: date) -> Tuple[List[ErrorRecord], List[ErrorRecord]]:
    """
    Pick up to 4 collision reservations and introduce errors:
      - 2 erroneous statuses
      - 2 unsynchronized dates

    Returns (status_errors, date_errors).
    """
    from typing import List, Tuple

    excluded_set = set(EXCLUDED_RESERVATION_IDS)
    candidates = [rid for rid in collision_ids if rid not in excluded_set]

    if len(candidates) < 4:
        print(f"❌ Not enough collision reservations (need 4, have {len(candidates)} excluding {len(excluded_set & set(collision_ids))}).")
        sys.exit(1)

    status_errors: List[ErrorRecord] = []
    date_errors: List[ErrorRecord] = []
    used_ids: set[int] = set()

    # ---- Error A1: CHECKED_IN type → set status to CANCELLED ----
    for rid in candidates:
        if rid in used_ids:
            continue
        rec = fetch_reservation_details(db, rid)
        if not rec:
            continue
        if rec["status"] == ReservationStatus.CHECKED_IN.value and is_checked_in_type(cast(str, rec["check_in_date"]), cast(str, rec["check_out_date"]), today):
            old_status = cast(str, rec["status"])
            reservation = db.query(Reservation).filter(Reservation.reservation_id == rid).first()
            if reservation:
                reservation.status = ReservationStatus.CANCELLED
                db.commit()
            status_errors.append(ErrorRecord(
                reservation_id=rid, error_type="status",
                field="status", before=old_status, after=ReservationStatus.CANCELLED.value,
                guest_name=f"{rec['first_name']} {rec['last_name']}",
                room_id=cast(int, rec["room_id"]),
            ))
            used_ids.add(rid)
            break

    # ---- Error A2: CONFIRMED type → set status to CHECKED_OUT ----
    for rid in candidates:
        if rid in used_ids:
            continue
        rec = fetch_reservation_details(db, rid)
        if not rec:
            continue
        if rec["status"] == ReservationStatus.CONFIRMED.value and is_confirmed_type(cast(str, rec["check_in_date"]), cast(str, rec["check_out_date"]), today):
            old_status = cast(str, rec["status"])
            reservation = db.query(Reservation).filter(Reservation.reservation_id == rid).first()
            if reservation:
                reservation.status = ReservationStatus.CHECKED_OUT
                db.commit()
            status_errors.append(ErrorRecord(
                reservation_id=rid, error_type="status",
                field="status", before=old_status, after=ReservationStatus.CHECKED_OUT.value,
                guest_name=f"{rec['first_name']} {rec['last_name']}",
                room_id=cast(int, rec["room_id"]),
            ))
            used_ids.add(rid)
            break

    # If we couldn't find a CONFIRMED type above, fall back to any CHECKED_IN with future checkout
    if len(status_errors) < 2:
        for rid in candidates:
            if rid in used_ids:
                continue
            rec = fetch_reservation_details(db, rid)
            if not rec:
                continue
            if rec["status"] == ReservationStatus.CHECKED_IN.value and is_checked_in_type(cast(str, rec["check_in_date"]), cast(str, rec["check_out_date"]), today):
                old_status = cast(str, rec["status"])
                reservation = db.query(Reservation).filter(Reservation.reservation_id == rid).first()
                if reservation:
                    reservation.status = ReservationStatus.CHECKED_OUT
                    db.commit()
                status_errors.append(ErrorRecord(
                    reservation_id=rid, error_type="status",
                    field="status", before=old_status, after=ReservationStatus.CHECKED_OUT.value,
                    guest_name=f"{rec['first_name']} {rec['last_name']}",
                    room_id=cast(int, rec["room_id"]),
                ))
                used_ids.add(rid)
                break

    # ---- Error B1: CHECKED_IN → move check_out_date to the past ----
    for rid in candidates:
        if rid in used_ids:
            continue
        rec = fetch_reservation_details(db, rid)
        if not rec:
            continue
        if rec["status"] == ReservationStatus.CHECKED_IN.value and is_checked_in_type(cast(str, rec["check_in_date"]), cast(str, rec["check_out_date"]), today):
            old_checkout = cast(str, rec["check_out_date"])
            # Set check_out to 3 days after check_in (both in the past)
            from datetime import timedelta
            ci = date.fromisoformat(cast(str, rec["check_in_date"]))
            new_checkout = (ci + timedelta(days=3)).isoformat()
            reservation = db.query(Reservation).filter(Reservation.reservation_id == rid).first()
            if reservation:
                reservation.check_out_date = date.fromisoformat(new_checkout)
                db.commit()
            date_errors.append(ErrorRecord(
                reservation_id=rid, error_type="date",
                field="check_out_date", before=old_checkout, after=new_checkout,
                guest_name=f"{rec['first_name']} {rec['last_name']}",
                room_id=cast(int, rec["room_id"]),
            ))
            used_ids.add(rid)
            break

    # ---- Error B2: CHECKED_OUT → move check_in_date to the future ----
    for rid in candidates:
        if rid in used_ids:
            continue
        rec = fetch_reservation_details(db, rid)
        if not rec:
            continue
        if rec["status"] == ReservationStatus.CHECKED_OUT.value and is_checked_out_type(cast(str, rec["check_in_date"]), cast(str, rec["check_out_date"]), today):
            old_checkin = cast(str, rec["check_in_date"])
            # Set check_in to 5 days in the future
            from datetime import timedelta
            new_checkin = (today + timedelta(days=5)).isoformat()
            # Also adjust check_out to be after the new check_in
            new_checkout = (today + timedelta(days=8)).isoformat()
            reservation = db.query(Reservation).filter(Reservation.reservation_id == rid).first()
            if reservation:
                reservation.check_in_date = date.fromisoformat(new_checkin)
                reservation.check_out_date = date.fromisoformat(new_checkout)
                db.commit()
            date_errors.append(ErrorRecord(
                reservation_id=rid, error_type="date",
                field="check_in_date", before=old_checkin, after=new_checkin,
                guest_name=f"{rec['first_name']} {rec['last_name']}",
                room_id=cast(int, rec["room_id"]),
            ))
            used_ids.add(rid)
            break

    return status_errors, date_errors


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def print_results(status_errors: List[ErrorRecord], date_errors: List[ErrorRecord], today: date) -> None:
    print("\n" + "=" * 65)
    print("🔴 ERRONEOUS RESERVATIONS CREATED")
    print(f"   Date: {today.isoformat()}")
    print("=" * 65)

    print("\n📌 Error Type A - Erroneous Status (2 reservations):")
    for e in status_errors:
        print(e)

    print("\n📌 Error Type B - Unsynchronized Dates (2 reservations):")
    for e in date_errors:
        print(e)

    all_ids = [e.reservation_id for e in status_errors + date_errors]
    print(f"\n⚠️  All erroneous reservation IDs: {sorted(all_ids)}")


def save_ids_to_json(status_errors: List[ErrorRecord],
                     date_errors: List[ErrorRecord],
                     today: date) -> None:
    payload: Dict[str, Any] = {
        "last_run": today.isoformat(),
        "status_errors": sorted([e.reservation_id for e in status_errors]),
        "date_errors": sorted([e.reservation_id for e in date_errors]),
        "all_error_ids": sorted([e.reservation_id for e in status_errors + date_errors]),
        "excluded_ids": EXCLUDED_RESERVATION_IDS,
    }
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    print(f"\n💾 IDs saved to {OUTPUT_JSON}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    today = date.today()
    print(f"📅 Today's date: {today.isoformat()}")
    print(f"🏨 Database: {DB_PATH}")

    if not os.path.exists(DB_PATH):
        print(f"❌ Database not found at {DB_PATH}")
        print("   Please run 'python create_hotel_db.py' first.")
        sys.exit(1)

    db: Session = SessionLocal()
    try:
        # Step 1: Find collision reservations
        collision_ids = fetch_collision_reservation_ids(db)
        print(f"🔍 Found {len(collision_ids)} reservation(s) with name collisions.")

        if EXCLUDED_RESERVATION_IDS:
            filtered = set(collision_ids) & set(EXCLUDED_RESERVATION_IDS)
            if filtered:
                print(f"🚫 Filtering out {len(filtered)} excluded ID(s): {sorted(filtered)}")

        # Step 2: Apply errors
        status_errors, date_errors = apply_errors(db, collision_ids, today)

        if len(status_errors) + len(date_errors) < 4:
            print(f"\n❌ Only created {len(status_errors) + len(date_errors)} error(s) (expected 4).")
            print("   The database may not have enough collision reservations of the required types.")
            sys.exit(1)

        # Step 3: Print & persist
        print_results(status_errors, date_errors, today)
        save_ids_to_json(status_errors, date_errors, today)

        print("\n✅ Done.")

    except Exception as e:
        db.rollback()
        print(f"\n❌ Error: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()