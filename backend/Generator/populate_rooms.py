#!/usr/bin/env python3
"""
Populate the Rooms table in the hotel database from generated room data.

Reads room data from rooms.json (output of generate_rooms.py) and inserts
each room into the Rooms table with the appropriate allowed_booking_channel
based on wing:
  - West (W)  -> ANY
  - North (N) -> ON_SITE_ONLY
  - East  (E) -> STAFF_ASSIGNMENT

Uses SQLAlchemy ORM models from the app package.

Usage:
    python Generator/populate_rooms.py
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.db import SessionLocal
from app.enums import BookingChannel
from app.models import Room
from sqlalchemy.orm import Session
from utils import (
    BASE_DIR,
    get_booking_channel,
    get_checkin_checkout_times,
)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOMS_JSON_PATH = os.path.join(BASE_DIR, "rooms.json")


def load_rooms(json_path: str) -> list:
    """Load room data from the generated JSON file."""
    if not os.path.exists(json_path):
        print(f"Error: rooms.json not found at {json_path}")
        print("Please run 'python Generator/generate_rooms.py' first to generate room data.")
        return []

    with open(json_path, "r", encoding="utf-8") as f:
        rooms = json.load(f)

    print(f"Loaded {len(rooms)} rooms from {json_path}")
    return rooms


def populate_rooms(db: Session, rooms: list) -> int:
    """Insert all rooms into the Rooms table using SQLAlchemy ORM.
    
    Returns the number of rooms inserted.
    """
    count = 0
    for room in rooms:
        room_name = room["room_number"]
        wing_code = room["wing_code"]
        channel = get_booking_channel(wing_code)
        checkin_time, checkout_time = get_checkin_checkout_times(channel)
        
        room_obj = Room(
            name=room_name,
            allowed_booking_channel=BookingChannel(channel),
            checkin_time=checkin_time,
            checkout_time=checkout_time,
        )
        db.add(room_obj)
        count += 1

    db.commit()
    print(f"Inserted {count} rooms into the Rooms table.")
    return count


def print_summary(db: Session) -> None:
    """Print a summary of rooms per booking channel using SQLAlchemy ORM."""
    print("\n--- Room Population Summary ---")
    for channel in [BookingChannel.ANY, BookingChannel.ON_SITE_ONLY, BookingChannel.STAFF_ASSIGNMENT]:
        count = db.query(Room).filter(Room.allowed_booking_channel == channel).count()
        print(f"  {channel.value}: {count} rooms")

    total = db.query(Room).count()
    print(f"  Total: {total} rooms")


def main():
    # Load room data
    rooms = load_rooms(ROOMS_JSON_PATH)
    if not rooms:
        return

    # Get SQLAlchemy session
    db = SessionLocal()

    try:
        # Clear existing rooms to allow re-running the script
        deleted = db.query(Room).count()
        if deleted > 0:
            db.query(Room).delete()
            db.commit()
            print(f"Cleared {deleted} existing room(s) from the Rooms table.")

        # Populate rooms
        populate_rooms(db, rooms)

        # Print summary
        print_summary(db)

        print("\nDone! Rooms table populated successfully.")
    except Exception as e:
        print(f"Error populating rooms: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()