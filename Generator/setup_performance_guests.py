#!/usr/bin/env python3
"""
Setup 13 test guests with exactly 4 reservations each for performance testing.

Creates a controlled, reproducible set of guests where each guest has
the same number of reservations to ensure constant LLM output and avoid
caching effects during performance tests.

Uses SQLAlchemy ORM models from the app package.

Usage:
    python Generator/setup_performance_guests.py
"""

import os
import random
import sys
from datetime import date, timedelta
from typing import Any, Dict, List

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.db import SessionLocal
from app.enums import BookingSource, ReservationStatus
from app.models import Guest, Reservation, Room
from sqlalchemy import func
from sqlalchemy.orm import Session
from utils import (
    generate_random_dob,
    get_bucket_dates,
    split_name,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
NUM_TEST_GUESTS = 13
RESERVATIONS_PER_GUEST = 4

# Use Arabic names from the existing list
ARABIC_NAMES_PATH = os.path.join(os.path.dirname(__file__), "arabic_names.txt")

# Date bucket ranges specific to performance test guests (tighter ranges)
PERF_BUCKET_RANGES = {
    "1": {"check_in": (7, 20), "check_out": (0, 0)},
    "2": {"check_in": (7, 20), "check_out": (1, 5)},
    "3": {"check_in": (10, 30), "check_out": (2, 8)},
    "4": {"check_in": (0, 0), "check_out": (1, 5)},
}


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
def load_arabic_names(path: str) -> List[str]:
    """Load Arabic names from the text file."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"Arabic names file not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        names = [line.strip() for line in f if line.strip()]

    if len(names) < NUM_TEST_GUESTS:
        raise ValueError(
            f"Not enough Arabic names in {path} "
            f"(need {NUM_TEST_GUESTS}, have {len(names)})"
        )

    return names


# ---------------------------------------------------------------------------
# Database operations (SQLAlchemy)
# ---------------------------------------------------------------------------
def delete_performance_test_guests(db: Session) -> int:
    """
    Delete previously created performance test guests (marked with
    special_preferences = 'performance_test').

    Returns the number of guests deleted.
    """
    guests = (
        db.query(Guest)
        .filter(Guest.special_preferences == "performance_test")
        .all()
    )

    count = len(guests)
    for guest in guests:
        # Delete reservations first (foreign key constraint)
        db.query(Reservation).filter(Reservation.guest_id == guest.guest_id).delete()
        db.delete(guest)

    db.commit()
    return count


def insert_test_guest(db: Session, first_name: str, last_name: str) -> Guest:
    """Insert a test guest into the Guests table and return the Guest object."""
    guest = Guest(
        first_name=first_name,
        last_name=last_name,
        date_of_birth=generate_random_dob(),
        is_special_guest=False,
        special_preferences="performance_test",
    )
    db.add(guest)
    db.commit()
    db.refresh(guest)
    return guest


def insert_reservation(
    db: Session,
    room: Room,
    guest: Guest,
    check_in_date: str,
    check_out_date: str,
    status: ReservationStatus,
    booking_source: BookingSource,
) -> Reservation:
    """Insert a reservation row and return the Reservation object."""
    reservation = Reservation(
        room_id=room.room_id,
        guest_id=guest.guest_id,
        check_in_date=date.fromisoformat(check_in_date),
        check_out_date=date.fromisoformat(check_out_date),
        status=status,
        booking_source=booking_source,
    )
    db.add(reservation)
    db.commit()
    db.refresh(reservation)
    return reservation


# ---------------------------------------------------------------------------
# Main logic
# ---------------------------------------------------------------------------
def setup_performance_test_guests() -> List[Dict[str, Any]]:
    """
    Create 13 test guests with exactly 4 reservations each.

    Returns a list of guest dicts with their details.
    """
    today = date.today()
    print(f"📅 Setting up {NUM_TEST_GUESTS} performance test guests ({RESERVATIONS_PER_GUEST} reservations each)")
    print(f"📅 Today's date: {today.isoformat()}")

    # Load names
    all_names = load_arabic_names(ARABIC_NAMES_PATH)

    # Select 13 names for testing
    test_names = all_names[:NUM_TEST_GUESTS]
    print(f"📋 Selected {len(test_names)} names for testing")

    db = SessionLocal()

    try:
        # Clean up any previous performance test guests
        deleted = delete_performance_test_guests(db)
        if deleted > 0:
            print(f"🗑️  Removed {deleted} previous performance test guest(s)")

        # Get available rooms
        available_rooms = db.query(Room).order_by(Room.room_id).all()
        if len(available_rooms) < RESERVATIONS_PER_GUEST:
            raise ValueError(
                f"Not enough rooms available (need at least {RESERVATIONS_PER_GUEST}, "
                f"have {len(available_rooms)})"
            )

        result_guests: List[Dict[str, Any]] = []

        for idx, full_name in enumerate(test_names):
            first_name, last_name = split_name(full_name)
            print(f"  [{idx + 1}/{NUM_TEST_GUESTS}] Creating guest: {first_name} {last_name}")

            # Insert the guest
            guest = insert_test_guest(db, first_name, last_name)

            # Create exactly 4 reservations with different buckets for variety
            reservation_count = 0
            for bucket_key in ["1", "2", "3", "4"]:
                check_in, check_out, status = get_bucket_dates(
                    bucket_key, today, PERF_BUCKET_RANGES
                )

                # Pick a random room (allow reuse across guests)
                room = random.choice(available_rooms)

                # Pick a random booking source
                booking_source = random.choice([
                    BookingSource.WEBSITE, BookingSource.PHONE, BookingSource.OTA
                ])

                insert_reservation(
                    db, room, guest,
                    check_in, check_out, status, booking_source
                )
                reservation_count += 1

            result_guests.append({
                "guest_id": guest.guest_id,
                "first_name": guest.first_name,
                "last_name": guest.last_name,
                "full_name": f"{guest.first_name} {guest.last_name}",
                "reservation_count": reservation_count,
            })

            print(f"    → {reservation_count} reservations created")

        # Verify
        for guest_dict in result_guests:
            gid = guest_dict["guest_id"]
            count = (
                db.query(func.count(Reservation.reservation_id))
                .filter(Reservation.guest_id == gid)
                .scalar()
            )
            guest_dict["reservation_count"] = count

            if count != RESERVATIONS_PER_GUEST:
                print(f"⚠️  Warning: Guest '{guest_dict['full_name']}' has {count} "
                      f"reservations (expected {RESERVATIONS_PER_GUEST})")

        # Summary
        print("\n" + "=" * 50)
        print("📊 PERFORMANCE TEST SETUP SUMMARY")
        print("=" * 50)
        print(f"  Test guests created:     {len(result_guests)}")
        print(f"  Reservations per guest:  {RESERVATIONS_PER_GUEST}")
        print(f"  Total reservations:      {len(result_guests) * RESERVATIONS_PER_GUEST}")
        print("\n  Guest list:")
        for i, g in enumerate(result_guests, 1):
            assignment = "Sequential" if i <= 5 else "Concurrent"
            print(f"    {i:2d}. {g['full_name']:<30s} ({g['reservation_count']} reservations) [{assignment}]")

        print("\n✅ Performance test guests setup complete!")

        return result_guests

    except Exception as e:
        db.rollback()
        print(f"❌ Error: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    guests = setup_performance_test_guests()