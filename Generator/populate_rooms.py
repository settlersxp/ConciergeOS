#!/usr/bin/env python3
"""
Populate the Rooms table in the hotel database from generated room data.

Reads room data from rooms.json (output of generate_rooms.py) and inserts
each room into the Rooms table with the appropriate allowed_booking_channel
based on wing:
  - West (W)  -> ANY
  - North (N) -> ON_SITE_ONLY
  - East  (E) -> STAFF_ASSIGNMENT

Usage:
    python Generator/populate_rooms.py
"""

import json
import os
import sqlite3
from typing import Any, Tuple

from utils import BASE_DIR, DB_PATH, init_connection

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOMS_JSON_PATH = os.path.join(BASE_DIR, "rooms.json")

# Wing-to-channel mapping
WING_CHANNEL_MAP = {
    "W": "ANY",
    "N": "ON_SITE_ONLY",
    "E": "STAFF_ASSIGNMENT",
}

# Channel-to-times mapping: (checkin_time, checkout_time)
# STAFF_ASSIGNMENT rooms use 00:00 for both times
# Regular rooms: checkin at 15:00, checkout at 09:00
CHANNEL_TIMES_MAP = {
    "ANY": ("15:00", "09:00"),
    "ON_SITE_ONLY": ("15:00", "09:00"),
    "STAFF_ASSIGNMENT": ("00:00", "00:00"),
}


def load_rooms(json_path: str) -> list[dict[str, Any]]:
    """Load room data from the generated JSON file."""
    if not os.path.exists(json_path):
        print(f"Error: rooms.json not found at {json_path}")
        print("Please run 'python Generator/generate_rooms.py' first to generate room data.")
        return []

    with open(json_path, "r", encoding="utf-8") as f:
        rooms = json.load(f)

    print(f"Loaded {len(rooms)} rooms from {json_path}")
    return rooms


def get_booking_channel(wing_code: str) -> str:
    """Return the allowed_booking_channel for a given wing code."""
    channel = WING_CHANNEL_MAP.get(wing_code)
    if channel is None:
        raise ValueError(f"Unknown wing code: {wing_code}")
    return channel


def get_checkin_checkout_times(channel: str) -> Tuple[str, str]:
    """Return (checkin_time, checkout_time) for a given booking channel."""
    times = CHANNEL_TIMES_MAP.get(channel)
    if times is None:
        raise ValueError(f"Unknown booking channel: {channel}")
    return times


def populate_rooms(conn: sqlite3.Connection, rooms: list[dict[str, Any]]) -> None:
    """Insert all rooms into the Rooms table."""
    cursor = conn.cursor()

    # Prepare insert data: (room_name, allowed_booking_channel, checkin_time, checkout_time)
    insert_data: list[Tuple[str, str, str, str]] = []
    for room in rooms:
        room_name = room["room_number"]
        wing_code = room["wing_code"]
        channel = get_booking_channel(wing_code)
        checkin_time, checkout_time = get_checkin_checkout_times(channel)
        insert_data.append((room_name, channel, checkin_time, checkout_time))

    # Batch insert using executemany
    cursor.executemany(
        "INSERT INTO Rooms (name, allowed_booking_channel, checkin_time, checkout_time) VALUES (?, ?, ?, ?)",
        insert_data
    )

    conn.commit()
    print(f"Inserted {len(insert_data)} rooms into the Rooms table.")


def print_summary(conn: sqlite3.Connection) -> None:
    """Print a summary of rooms per booking channel."""
    cursor = conn.cursor()

    print("\n--- Room Population Summary ---")
    for channel in ["ANY", "ON_SITE_ONLY", "STAFF_ASSIGNMENT"]:
        cursor.execute(
            "SELECT COUNT(*) FROM Rooms WHERE allowed_booking_channel = ?",
            (channel,)
        )
        count = cursor.fetchone()[0]
        print(f"  {channel}: {count} rooms")

    cursor.execute("SELECT COUNT(*) FROM Rooms")
    total = cursor.fetchone()[0]
    print(f"  Total: {total} rooms")


def main():
    # Load room data
    rooms = load_rooms(ROOMS_JSON_PATH)
    if not rooms:
        return

    # Connect to database
    if not os.path.exists(DB_PATH):
        print(f"Error: Database not found at {DB_PATH}")
        print("Please run 'python create_hotel_db.py' first to create the database schema.")
        return

    conn = init_connection(DB_PATH)

    try:
        # Clear existing rooms to allow re-running the script
        cursor = conn.cursor()
        deleted = cursor.execute("DELETE FROM Rooms").rowcount
        if deleted > 0:
            conn.commit()
            print(f"Cleared {deleted} existing room(s) from the Rooms table.")

        # Populate rooms
        populate_rooms(conn, rooms)

        # Print summary
        print_summary(conn)

        print("\nDone! Rooms table populated successfully.")
    except Exception as e:
        print(f"Error populating rooms: {e}")
        conn.rollback()
    finally:
        conn.close()


if __name__ == "__main__":
    main()