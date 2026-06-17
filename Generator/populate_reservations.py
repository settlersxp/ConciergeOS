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

Usage:
    python Generator/populate_reservations.py
"""

import json
import os
import random
import sqlite3
from datetime import date, timedelta
from typing import Tuple, List, cast

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
DB_PATH = os.path.join(PROJECT_ROOT, "hotel.db")
NAMES_JSON_PATH = os.path.join(BASE_DIR, "all_names.json")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
BUCKET: dict[str, dict[str, object]] = {
    "1": {"label": "CHECKED_IN (checking out today)", "weight": 1},
    "2": {"label": "CHECKED_IN (future checkout)", "weight": 3},
    "3": {"label": "CHECKED_OUT", "weight": 1},
    "4": {"label": "CONFIRMED", "weight": 1},
}

BOOKING_SOURCES_ANY = ["WEBSITE", "PHONE", "OTA"]
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


def split_name(full_name: str) -> Tuple[str, str]:
    """Split a full name string into (first_name, last_name)."""
    parts = full_name.strip().split()
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


# ---------------------------------------------------------------------------
# Date helpers
# ---------------------------------------------------------------------------
def random_date_between(start: date, end: date) -> str:
    """Return a random date as YYYY-MM-DD string between start and end (inclusive)."""
    delta = (end - start).days
    if delta < 0:
        delta = 0
    random_day = start + timedelta(days=random.randint(0, delta))
    return random_day.isoformat()


def get_bucket_dates(bucket: str, today: date) -> Tuple[str, str, str]:
    """Return (check_in_date, check_out_date, status) for a given bucket."""
    if bucket == "1":
        # check_in: 7-30 days ago, check_out: today, status: CHECKED_IN
        check_in = random_date_between(today - timedelta(days=30), today - timedelta(days=7))
        return check_in, today.isoformat(), "CHECKED_IN"

    elif bucket == "2":
        # check_in: 7-30 days ago, check_out: 1-7 days in future, status: CHECKED_IN
        check_in = random_date_between(today - timedelta(days=30), today - timedelta(days=7))
        check_out = random_date_between(today + timedelta(days=1), today + timedelta(days=7))
        return check_in, check_out, "CHECKED_IN"

    elif bucket == "3":
        # check_in: 14-60 days ago, check_out: 2-10 days ago, status: CHECKED_OUT
        check_out_str = random_date_between(today - timedelta(days=10), today - timedelta(days=2))
        check_out_date = date.fromisoformat(check_out_str)
        check_in = random_date_between(today - timedelta(days=60), check_out_date - timedelta(days=1))
        return check_in, check_out_str, "CHECKED_OUT"

    elif bucket == "4":
        # check_in: today, check_out: 1-7 days in future, status: CONFIRMED
        check_out = random_date_between(today + timedelta(days=1), today + timedelta(days=7))
        return today.isoformat(), check_out, "CONFIRMED"

    raise ValueError(f"Unknown bucket: {bucket}")


def weighted_random_bucket() -> str:
    """Pick a bucket key (1-4) using defined weights."""
    keys = list(BUCKET.keys())
    weights = [cast(int, BUCKET[k]["weight"]) for k in keys]
    return random.choices(keys, weights=weights, k=1)[0]


# ---------------------------------------------------------------------------
# Booking source
# ---------------------------------------------------------------------------
def get_booking_source(allowed_booking_channel: str) -> str:
    """Determine booking_source based on room's allowed_booking_channel."""
    if allowed_booking_channel == "ON_SITE_ONLY":
        return "WALK_IN"
    elif allowed_booking_channel == "ANY":
        return random.choice(BOOKING_SOURCES_ANY)
    elif allowed_booking_channel == "STAFF_ASSIGNMENT":
        return "INTERNAL"
    raise ValueError(f"Unknown booking channel: {allowed_booking_channel}")


# ---------------------------------------------------------------------------
# Database operations
# ---------------------------------------------------------------------------
def init_connection(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn


def insert_guest(conn: sqlite3.Connection, first_name: str, last_name: str) -> int:
    """Insert a guest into the Guests table and return the guest_id."""
    # Generate a random date of birth (between 18 and 80 years old)
    min_dob = date.today() - timedelta(days=80 * 365)
    max_dob = date.today() - timedelta(days=18 * 365)
    dob = random_date_between(min_dob, max_dob)

    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO Guests (first_name, last_name, date_of_birth, is_special_guest, special_preferences) "
        "VALUES (?, ?, ?, 0, NULL)",
        (first_name, last_name, dob),
    )
    return cursor.lastrowid  # type: ignore[return-value]


def insert_reservation(
    conn: sqlite3.Connection,
    room_id: int,
    guest_id: int,
    check_in_date: str,
    check_out_date: str,
    status: str,
    booking_source: str,
) -> int:
    """Insert a reservation row and return the reservation_id."""
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO Reservations (room_id, guest_id, check_in_date, check_out_date, status, booking_source) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (room_id, guest_id, check_in_date, check_out_date, status, booking_source),
    )
    return cursor.lastrowid  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Main logic
# ---------------------------------------------------------------------------
def create_collision_reservations(
    conn: sqlite3.Connection,
    all_names: List[str],
    rooms_by_channel: dict[str, list[dict[str, object]]],
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
    available_channels = ["ANY", "ON_SITE_ONLY"]
    candidate_rooms: list[dict[str, object]] = []
    for ch in available_channels:
        candidate_rooms.extend(rooms_by_channel.get(ch, []))

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

    status = "CHECKED_OUT" if bucket == "3" else "CHECKED_IN"

    print(f"\n📛 Creating {collision_count} name collisions for '{first_name} {last_name}' "
          f"(status={status}, check_in={fixed_check_in}, check_out={fixed_check_out})")

    total_rows = 0
    for room in selected_rooms:
        room_id = cast(int, room["room_id"])
        channel = cast(str, room["allowed_booking_channel"])
        booking_source = get_booking_source(channel)

        # Each collision reservation also has 1-6 guests, but the PRIMARY guest
        # (first inserted) always has the collision name
        num_guests = random.randint(MIN_GUESTS_PER_RESERVATION, MAX_GUESTS_PER_RESERVATION)

        # Insert the collision-named guest first
        guest_id = insert_guest(conn, first_name, last_name)
        insert_reservation(conn, room_id, guest_id, fixed_check_in, fixed_check_out, status, booking_source)
        total_rows += 1

        # Then insert additional guests with random names
        for _ in range(num_guests - 1):
            other_name = random.choice(all_names)
            other_first, other_last = split_name(other_name)
            other_guest_id = insert_guest(conn, other_first, other_last)
            insert_reservation(conn, room_id, other_guest_id, fixed_check_in, fixed_check_out, status, booking_source)
            total_rows += 1

    return total_rows


def populate_reservations() -> None:
    today = date.today()
    print(f"📅 Today's date: {today.isoformat()}")

    # Load names
    all_names = load_names(NAMES_JSON_PATH)

    # Connect to database
    if not os.path.exists(DB_PATH):
        raise FileNotFoundError(f"Database not found at {DB_PATH}\n"
                                "Please run 'python create_hotel_db.py' first.")

    conn = init_connection(DB_PATH)

    try:
        cursor = conn.cursor()

        # Clear existing data to allow re-running
        del_res = cursor.execute("DELETE FROM Reservations").rowcount
        del_guests = cursor.execute("DELETE FROM Guests").rowcount
        if del_res > 0 or del_guests > 0:
            conn.commit()
            print(f"🗑️  Cleared {del_guests} guest(s) and {del_res} reservation(s) from database.")

        # Load all rooms
        cursor.execute("SELECT room_id, name, allowed_booking_channel FROM Rooms ORDER BY room_id")
        rooms = [{"room_id": r[0], "name": r[1], "allowed_booking_channel": r[2]} for r in cursor.fetchall()]
        print(f"🏨 Loaded {len(rooms)} rooms from database.")

        if not rooms:
            raise ValueError("No rooms found in the database. Run 'python Generator/populate_rooms.py' first.")

        # Group rooms by channel for collision selection
        rooms_by_channel: dict[str, list[dict[str, object]]] = {}
        for room in rooms:
            ch = room["allowed_booking_channel"]
            rooms_by_channel.setdefault(ch, []).append(room)

        # -----------------------------------------------------------------------
        # Step 1: Create name collision reservations first
        # -----------------------------------------------------------------------
        collision_rows = 0

        out_coll_rooms = create_collision_reservations(
            conn, all_names, rooms_by_channel, today,
            NUM_CHECKED_OUT_COLLISIONS, "3"  # CHECKED_OUT
        )
        collision_rows += out_coll_rooms

        in_coll_rooms = create_collision_reservations(
            conn, all_names, rooms_by_channel, today,
            NUM_CHECKED_IN_COLLISIONS, "2"  # CHECKED_IN
        )
        collision_rows += in_coll_rooms

        # Track which rooms already have collision reservations
        cursor.execute("SELECT DISTINCT room_id FROM Reservations")
        occupied_room_ids = {r[0] for r in cursor.fetchall()}
        print(f"\n📝 Collision reservations occupy {len(occupied_room_ids)} rooms.")

        # -----------------------------------------------------------------------
        # Step 2: Create normal reservations for remaining rooms
        # -----------------------------------------------------------------------
        remaining_rooms = [r for r in rooms if r["room_id"] not in occupied_room_ids]
        print(f"📋 Creating normal reservations for {len(remaining_rooms)} remaining rooms...")

        normal_rows = 0
        status_counts: dict[str, int] = {"CHECKED_IN": 0, "CHECKED_OUT": 0, "CONFIRMED": 0}

        for room in remaining_rooms:
            room_id = room["room_id"]
            channel = room["allowed_booking_channel"]

            # Determine bucket
            if channel == "STAFF_ASSIGNMENT":
                bucket = "2"  # Always CHECKED_IN with past check_in, future check_out
            else:
                bucket = weighted_random_bucket()

            check_in, check_out, status = get_bucket_dates(bucket, today)
            booking_source = get_booking_source(channel)

            # Pick 1-6 guests
            num_guests = random.randint(MIN_GUESTS_PER_RESERVATION, MAX_GUESTS_PER_RESERVATION)
            selected_names = random.sample(all_names, num_guests)

            for full_name in selected_names:
                first_name, last_name = split_name(full_name)
                guest_id = insert_guest(conn, first_name, last_name)
                insert_reservation(conn, room_id, guest_id, check_in, check_out, status, booking_source)
                normal_rows += 1

            status_counts[status] = status_counts.get(status, 0) + 1

        conn.commit()

        # -----------------------------------------------------------------------
        # Summary
        # -----------------------------------------------------------------------
        print("\n" + "=" * 50)
        print("📊 POPULATION SUMMARY")
        print("=" * 50)

        cursor.execute("SELECT COUNT(*) FROM Guests")
        total_guests = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM Reservations")
        total_reservations = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(DISTinct room_id) FROM Reservations")
        rooms_with_reservations = cursor.fetchone()[0]

        print(f"  Guests inserted:        {total_guests}")
        print(f"  Reservation rows:       {total_reservations}")
        print(f"    • Normal:             {normal_rows}")
        print(f"    • Name collisions:    {collision_rows}")
        print(f"  Rooms with reservations: {rooms_with_reservations}")
        print(f"\n  Status distribution (normal reservations):")
        for status, count in sorted(status_counts.items()):
            print(f"    • {status}: {count}")

        # Show collision details
        print(f"\n  🔍 Name collision verification:")
        cursor.execute(
            "SELECT g.first_name, g.last_name, COUNT(DISTINCT r.room_id) as room_count, r.status, r.check_in_date "
            "FROM Reservations r "
            "JOIN Guests g ON r.guest_id = g.guest_id "
            "GROUP BY g.first_name, g.last_name, r.status "
            "HAVING room_count >= 2 "
            "ORDER BY room_count DESC LIMIT 20"
        )
        collisions = cursor.fetchall()
        for first, last, cnt, status, check_in in collisions:
            print(f"    • '{first} {last}' → {cnt} rooms (status={status}, check_in={check_in})")

        print("\n✅ Done! Guests and Reservations populated successfully.")

    except Exception as e:
        conn.rollback()
        print(f"❌ Error: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    populate_reservations()