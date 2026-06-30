#!/usr/bin/env python3
"""
Shared enums for the ConciergeOS application.

These enums use str, Enum inheritance so they work seamlessly with:
- SQLAlchemy's Enum type (stored as strings in SQLite)
- Pydantic validation (auto-serialized to strings in JSON responses)
- Python comparisons (e.g., status == ReservationStatus.CANCELLED)
"""

from enum import Enum


class BookingChannel(str, Enum):
    """Allowed booking channel types for rooms."""

    ON_SITE_ONLY = "ON_SITE_ONLY"
    STAFF_ASSIGNMENT = "STAFF_ASSIGNMENT"
    ANY = "ANY"


class ReservationStatus(str, Enum):
    """Lifecycle statuses for reservations."""

    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    CHECKED_IN = "CHECKED_IN"
    CHECKED_OUT = "CHECKED_OUT"
    CANCELLED = "CANCELLED"


class BookingSource(str, Enum):
    """Where a reservation was created / booked from."""

    WALK_IN = "WALK_IN"
    WEBSITE = "WEBSITE"
    PHONE = "PHONE"
    OTA = "OTA"
    INTERNAL = "INTERNAL"