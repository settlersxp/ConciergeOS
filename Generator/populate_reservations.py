#!/usr/bin/env python3
"""
Populate Guests and Reservations from name data.

For each room in the Rooms table, this script:
1. Picks 1-6 random names from all_names.json
2. Inserts those guests into the Guests table (first_name, last_name, date_of_birth)
3. Inserts one reservation row per guest (same room_id, check_in_date, check_out_date, status)

Date/status buckets for non-STAFF_ASSIGNMENT rooms:
  Bucket 1: check_in past (7-30d ago), check_out today → CHECKED_IN
  Bucket 2: check_in past (7-30d ago), check_out future (1-7d) → CHECKED_IN
  Bucket 3: check_in past (14-60d ago), check_out past (2-10d ago) → CHECKED_OUT
  Bucket 4: check_in today, check_out future (1-7d) → CONFIRMED

STAFF_ASSIGNMENT rooms always use bucket 2 (check_in past, check_out future, CHECKED_IN).

Name collisions for testing:
  5 CHECKED_OUT collisions + 5 CHECKED_IN collisions (same first+last name, overlapping dates).

Booking source rules:
  ON_SITE_ONLY  → WALK_IN
  ANY           → random of WEBSITE, PHONE, OTA
  STAFF_ASSIGNMENT → INTERNAL

Uses SQLAlchemy ORM models from the app package.

Usage:
    python Generator/populate_reservations.py
"""

import json
import os
import random
import sys
from datetime import date, timedelta
from typing import Dict, List

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.db import SessionLocal
from app.enums import BookingChannel, BookingSource, ReservationStatus
from app.models import Guest, Reservation, Room
from sqlalchemy import func
from sqlalchemy.orm import Session
from utils import (
    BASE_DIR,
    booking_channel_to_source,
    generate_random_dob,
    get_bucket_dates,
    split_name,
    weighted_random_bucket,
)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
NAMES_JSON_PATH = os.path.join(BASE_DIR, "all_names.json")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
MAX_GUESTS_PER_RESERVATION = 6
MIN_GUESTS_PER_RESERVATION = 1
NUM_CHECKED_OUT_COLLISIONS = 5
NUM_CHECKED_IN_COLLISIONS = 5


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
def load_names(json_path: str) -> List[str]:
    """Load all full names from all_names.json across every alphabet. Crash if empty/missing."""
    if not os.path.exists(json_path):
        raise FileNotFoundError(f"Names file not found: {json_path}\n"
                                "Please run 'python Generator/generate_names.py' first.")

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # data is a dict: { "latin": [name, ...], "cyrillic": [name, ...], ... }
    all_names: List[str] = []
    for alphabet, names in data.items():
        if not isinstance(names, list):
            raise ValueError(f"Expected a list of names for alphabet '{alphabet}', got {type(names).__name__}")
        all_names.extend(names)

    if not all_names:
        raise ValueError(f"Names file is empty: {json_path}")

    print(f"✅ Loaded {len(all_names)} names from {json_path}")
    return all_names


# ---------------------------------------------------------------------------
# Database operations (SQLAlchemy ORM)
# ---------------------------------------------------------------------------
def insert_guest(db: Session, first_name: str, last_name: str) -> Guest:
    """Insert a guest into the Guests table and return the Guest object."""
    guest = Guest(
        first_name=first_name,
        last_name=last_name,
        date_of_birth=generate_random_dob(),
        is_special_guest=False,
        special_preferences=None,
    )
    db.add(guest)
    db.commit()
    db.refresh(guest)
    return guest


def insert_reservation(
    db: Session,
    room_id: int,
    guest_id: int,
    check_in_date: str,
    check_out_date: str,
    status: ReservationStatus,
    booking_source: BookingSource,
) -> Reservation:
    """Insert a reservation row and return the Reservation object."""
    reservation = Reservation(
        room_id=room_id,
        guest_id=guest_id,
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
def create_collision_reservations(
    db: Session,
    all_names: List[str],
    rooms_by_channel: Dict[str, List[Room]],
    today: date,
    collision_count: int,
    bucket: str,
) -> int:
    """
    Create collision reservations where the same guest name appears on different rooms
    with overlapping dates to test name-collision scenarios.

    Returns the number of collision reservation rows created.
    """
    # Pick a name that will be reused
    collision_name = random.choice(all_names)
    first_name, last_name = split_name(collision_name)

    # Select rooms for collisions (non-STAFF_ASSIGNMENT preferred for collisions)
    available_channels = [BookingChannel.ANY, BookingChannel.ON_SITE_ONLY]
    candidate_rooms: List[Room] = []
    for ch in available_channels:
        candidate_rooms.extend(rooms_by_channel.get(ch.value, []))

    if len(candidate_rooms) < collision_count:
        raise ValueError(
            f"Not enough non-STAFF_ASSIGNMENT rooms for {collision_count} collisions "
            f"(need {collision_count}, have {len(candidate_rooms)})"
        )

    selected_rooms = random.sample(candidate_rooms, collision_count)

    # Generate a fixed check_in_date for all collisions to ensure overlap
    if bucket == "3":
        # CHECKED_OUT: pick a date 10-20 days ago
        fixed_check_in = (today - timedelta(days=random.randint(10, 20))).isoformat()
        fixed_check_out = (today - timedelta(days=random.randint(2, 8))).isoformat()
        # Ensure check_out > check_in
        check_in_date_o = date.fromisoformat(fixed_check_in)
        check_out_date_o = date.fromisoformat(fixed_check_out)
        if check_out_date_o <= check_in_date_o:
            fixed_check_out = (check_in_date_o + timedelta(days=random.randint(1, 5))).isoformat()
    else:
        # CHECKED_IN (bucket 2): pick a date in the past, checkout in the future
        fixed_check_in = (today - timedelta(days=random.randint(5, 15))).isoformat()
        fixed_check_out = (today + timedelta(days=random.randint(2, 5))).isoformat()

    status = ReservationStatus.CHECKED_OUT if bucket == "3" else ReservationStatus.CHECKED_IN

    print(f"\n📛 Creating {collision_count} name collisions for '{first_name} {last_name}' "
          f"(status={status.value}, check_in={fixed_check_in}, check_out={fixed_check_out})")

    total_rows = 0
    for room in selected_rooms:
        room_id = room.room_id
        channel = room.allowed_booking_channel
        booking_source = booking_channel_to_source(channel)

        # Each collision reservation also has 1-6 guests, but the PRIMARY guest
        # (first inserted) always has the collision name
        num_guests = random.randint(MIN_GUESTS_PER_RESERVATION, MAX_GUESTS_PER_RESERVATION)

        # Insert the collision-named guest first
        guest = insert_guest(db, first_name, last_name)
        insert_reservation(db, room_id, guest.guest_id, fixed_check_in, fixed_check_out, status, booking_source)
        total_rows += 1

        # Then insert additional guests with random names
        for _ in range(num_guests - 1):
            other_name = random.choice(all_names)
            other_first, other_last = split_name(other_name)
            other_guest = insert_guest(db, other_first, other_last)
            insert_reservation(db, room_id, other_guest.guest_id, fixed_check_in, fixed_check_out, status, booking_source)
            total_rows += 1

    return total_rows


def populate_reservations() -> None:
    today = date.today()
    print(f"📅 Today's date: {today.isoformat()}")

    # Load names
    all_names = load_names(NAMES_JSON_PATH)

    db: Session = SessionLocal()

    try:
        # Clear existing data to allow re-running
        del_res = db.query(Reservation).count()
        del_guests = db.query(Guest).count()
        if del_res > 0 or del_guests > 0:
            db.query(Reservation).delete()
            db.query(Guest).delete()
            db.commit()
            print(f"🗑️  Cleared {del_guests} guest(s) and {del_res} reservation(s) from database.")

        # Load all rooms
        rooms = db.query(Room).order_by(Room.room_id).all()
        print(f"🏨 Loaded {len(rooms)} rooms from database.")

        if not rooms:
            raise ValueError("No rooms found in the database. Run 'python Generator/populate_rooms.py' first.")

        # Group rooms by channel for collision selection
        rooms_by_channel: Dict[str, List[Room]] = {}
        for room in rooms:
            rooms_by_channel.setdefault(room.allowed_booking_channel.value, []).append(room)

        # -----------------------------------------------------------------------
        # Step 1: Create name collision reservations first
        # -----------------------------------------------------------------------
        collision_rows = 0

        out_coll_rooms = create_collision_reservations(
            db, all_names, rooms_by_channel, today,
            NUM_CHECKED_OUT_COLLISIONS, "3"  # CHECKED_OUT
        )
        collision_rows += out_coll_rooms

        in_coll_rooms = create_collision_reservations(
            db, all_names, rooms_by_channel, today,
            NUM_CHECKED_IN_COLLISIONS, "2"  # CHECKED_IN
        )
        collision_rows += in_coll_rooms

        # Track which rooms already have collision reservations
        occupied_room_ids = {r.room_id for r in db.query(Reservation.room_id).distinct().all()}
        print(f"\n📝 Collision reservations occupy {len(occupied_room_ids)} rooms.")

        # -----------------------------------------------------------------------
        # Step 2: Create normal reservations for remaining rooms
        # -----------------------------------------------------------------------
        occupied_set = set(occupied_room_ids)
        remaining_rooms = [r for r in rooms if r.room_id not in occupied_set]
        print(f"📋 Creating normal reservations for {len(remaining_rooms)} remaining rooms...")

        normal_rows = 0
        status_counts: Dict[str, int] = {"CHECKED_IN": 0, "CHECKED_OUT": 0, "CONFIRMED": 0}

        for room in remaining_rooms:
            room_id = room.room_id
            channel = room.allowed_booking_channel

            # Determine bucket
            if channel == BookingChannel.STAFF_ASSIGNMENT:
                bucket = "2"  # Always CHECKED_IN with past check_in, future check_out
            else:
                bucket = weighted_random_bucket()

            check_in, check_out, status = get_bucket_dates(bucket, today)
            booking_source = booking_channel_to_source(channel)

            # Pick 1-6 guests
            num_guests = random.randint(MIN_GUESTS_PER_RESERVATION, MAX_GUESTS_PER_RESERVATION)
            selected_names = random.sample(all_names, num_guests)

            for full_name in selected_names:
                first_name, last_name = split_name(full_name)
                guest = insert_guest(db, first_name, last_name)
                insert_reservation(db, room_id, guest.guest_id, check_in, check_out, status, booking_source)
                normal_rows += 1

            status_counts[status.value] = status_counts.get(status.value, 0) + 1

        # -----------------------------------------------------------------------
        # Summary
        # -----------------------------------------------------------------------
        print("\n" + "=" * 50)
        print("📊 POPULATION SUMMARY")
        print("=" * 50)

        total_guests = db.query(func.count(Guest.guest_id)).scalar()
        total_reservations = db.query(func.count(Reservation.reservation_id)).scalar()
        rooms_with_reservations = db.query(func.count(Reservation.room_id.distinct())).scalar()

        print(f"  Guests inserted:        {total_guests}")
        print(f"  Reservation rows:       {total_reservations}")
        print(f"    • Normal:             {normal_rows}")
        print(f"    • Name collisions:    {collision_rows}")
        print(f"  Rooms with reservations: {rooms_with_reservations}")
        print(f"\n  Status distribution (normal reservations):")
        for st, count in sorted(status_counts.items()):
            print(f"    • {st}: {count}")

        # Show collision details
        print(f"\n  🔍 Name collision verification:")
        collision_distinct = func.count(Reservation.room_id.distinct()).label("room_count")
        collisions = (
            db.query(
                Guest.first_name,
                Guest.last_name,
                collision_distinct,
                Reservation.status,
                Reservation.check_in_date,
            )
            .join(Reservation, Guest.guest_id == Reservation.guest_id)
            .group_by(Guest.first_name, Guest.last_name, Reservation.status)
            .having(collision_distinct >= 2)
            .order_by(collision_distinct.desc())
            .limit(20)
            .all()
        )
        for first, last, cnt, st, check_in in collisions:
            print(f"    • '{first} {last}' → {cnt} rooms (status={st.value}, check_in={check_in})")

        print("\n✅ Done! Guests and Reservations populated successfully.")

    except Exception as e:
        db.rollback()
        print(f"❌ Error: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    populate_reservations()