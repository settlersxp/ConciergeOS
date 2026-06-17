#!/usr/bin/env python3
"""
Hotel Database Generator (SQLite)
Single-tenant schema with room policies, special guests, preferences, and reservation tracking.
Run: python create_hotel_db.py [--recreate]
"""

import sqlite3
import sys
import os

DB_NAME = "hotel.db"

CREATE_ROOMS = """
CREATE TABLE IF NOT EXISTS Rooms (
    room_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    allowed_booking_channel TEXT NOT NULL DEFAULT 'ANY'
        CHECK (allowed_booking_channel IN ('ON_SITE_ONLY', 'STAFF_ASSIGNMENT', 'ANY')),
    checkin_time TEXT NOT NULL DEFAULT '15:00',
    checkout_time TEXT NOT NULL DEFAULT '09:00'
);
"""

CREATE_GUESTS = """
CREATE TABLE IF NOT EXISTS Guests (
    guest_id INTEGER PRIMARY KEY,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    date_of_birth TEXT NOT NULL,
    is_special_guest INTEGER DEFAULT 0,
    special_preferences TEXT  -- Free-text area for guest requests/notes
);
"""

CREATE_RESERVATIONS = """
CREATE TABLE IF NOT EXISTS Reservations (
    reservation_id INTEGER PRIMARY KEY,
    room_id INTEGER NOT NULL,
    guest_id INTEGER NOT NULL,
    check_in_date TEXT NOT NULL,
    check_out_date TEXT NOT NULL,
    status TEXT DEFAULT 'PENDING'
        CHECK (status IN ('PENDING', 'CONFIRMED', 'CHECKED_IN', 'CHECKED_OUT', 'CANCELLED')),
    booking_source TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (room_id) REFERENCES Rooms(room_id) ON DELETE RESTRICT,
    FOREIGN KEY (guest_id) REFERENCES Guests(guest_id) ON DELETE RESTRICT
);
"""

CREATE_INDEX_1 = """
CREATE INDEX IF NOT EXISTS idx_reservations_room_dates 
    ON Reservations(room_id, check_in_date, check_out_date, status);
"""

CREATE_INDEX_2 = """
CREATE INDEX IF NOT EXISTS idx_reservations_guest 
    ON Reservations(guest_id);
"""

def init_connection(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn

def create_tables(conn: sqlite3.Connection) -> None:
    cursor = conn.cursor()
    for stmt in [CREATE_ROOMS, CREATE_GUESTS, CREATE_RESERVATIONS]:
        cursor.execute(stmt)
    cursor.execute(CREATE_INDEX_1)
    cursor.execute(CREATE_INDEX_2)
    conn.commit()

def drop_existing(db_path: str) -> None:
    for suffix in [".db-wal", ".db-shm", ".db"]:
        try:
            os.remove(f"{db_path}{suffix if suffix != '.db' else ''}")
        except FileNotFoundError:
            pass
    if os.path.exists(db_path):
        os.remove(db_path)
        print(f"🗑️  Deleted existing database: {db_path}")

def main():
    recreate = "--recreate" in sys.argv
    
    if recreate:
        drop_existing(DB_NAME)
    
    print(f"🏨 Generating SQLite database: {DB_NAME}")
    conn = init_connection(DB_NAME)
    try:
        create_tables(conn)
        print("✅ Schema created successfully.")
        print("\n📋 Tables created:")
        print("   • Rooms (room_id, name, allowed_booking_channel, checkin_time, checkout_time)")
        print("   • Guests (guest_id, first_name, last_name, date_of_birth, is_special_guest, special_preferences)")
        print("   • Reservations (reservation_id, room_id, guest_id, check_in/out, status, booking_source, created_at)")
        print("\n💡 Notes:")
        print("   • SQLite uses INTEGER for booleans (0/1)")
        print("   • Dates stored as TEXT (YYYY-MM-DD) for optimal compatibility")
        print("   • special_preferences is a free-text TEXT column (no length limit)")
        print("   • 1–6 guest limit must be enforced at application layer")
        print("   • checkin_time/checkout_time are HH:MM format (STAFF_ASSIGNMENT: 00:00)")
        print("   • Run again with --recreate to reset the database")
    except Exception as e:
        print(f"❌ Failed to create database: {e}")
        sys.exit(1)
    finally:
        conn.close()

if __name__ == "__main__":
    main()