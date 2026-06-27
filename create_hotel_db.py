#!/usr/bin/env python3
"""
DEPRECATED: Hotel Database Generator

This script is no longer needed. The database schema is now managed by Alembic migrations.

To initialize/reset the database, use:
    uv run alembic upgrade head

To reset the database completely:
    rm -f database.db database.db-wal database.db-shm
    uv run alembic upgrade head

Original schema (now in alembic/versions/d3f04a295bc8_add_hotel_tables_rooms_guests_.py):
   - Rooms (room_id, name, allowed_booking_channel, checkin_time, checkout_time)
   - Guests (guest_id, first_name, last_name, date_of_birth, is_special_guest, special_preferences)
   - Reservations (reservation_id, room_id, guest_id, check_in/out_date, status, booking_source, created_at)
   - test_results (performance testing results)
"""

import sys

def main():
    print("⚠️  This script is DEPRECATED.")
    print("The database schema is now managed by Alembic migrations.")
    print()
    print("To initialize the database, run:")
    print("    uv run alembic upgrade head")
    print()
    print("To reset the database:")
    print("    rm -f database.db database.db-wal database.db-shm")
    print("    uv run alembic upgrade head")
    sys.exit(0)

if __name__ == "__main__":
    main()