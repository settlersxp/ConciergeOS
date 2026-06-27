#!/usr/bin/env python3
"""
Shared constants and helpers for all Generator scripts, exposed via the app package.

This module is the single source of truth for:
  - Name parsing (split_name)
  - Date/status bucket helpers (get_bucket_dates, weighted_random_bucket)
  - Guest creation helper (generate_random_dob)
  - Booking channel mappings (booking_channel_to_source, get_booking_channel,
    get_checkin_checkout_times)
  - Reservation date classification (is_checked_in_type, is_confirmed_type,
    is_checked_out_type, classify_reservation_type)

Generator scripts import via: from utils import ...
                               (where utils.py re-exports from app)
The app imports via:          from app.services.generator_utils import ...
"""

from __future__ import annotations

import random

from app.enums import BookingChannel, BookingSource
from app.enums import ReservationStatus
from datetime import date, timedelta


# ---------------------------------------------------------------------------
# Name parsing
# ---------------------------------------------------------------------------
def split_name(full_name: str) -> tuple[str, str]:
    """Split a full name string into (first_name, last_name)."""
    parts = full_name.strip().split()
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


# ---------------------------------------------------------------------------
# Date helpers - reservation buckets
# ---------------------------------------------------------------------------

# Default bucket ranges (used by populate_reservations.py)
DEFAULT_BUCKET_RANGES: dict[str, dict[str, tuple[int, int]]] = {
    "1": {"check_in": (7, 30), "check_out": (0, 0)},  # check_out = today
    "2": {"check_in": (7, 30), "check_out": (1, 7)},
    "3": {"check_in": (14, 60), "check_out": (2, 10)},
    "4": {"check_in": (0, 0), "check_out": (1, 7)},  # check_in = today
}

# Default bucket weights
DEFAULT_BUCKET_WEIGHTS: dict[str, int] = {
    "1": 1,
    "2": 3,
    "3": 1,
    "4": 1,
}


def get_bucket_dates(
    bucket: str,
    today: date,
    ranges: dict[str, dict[str, tuple[int, int]]] | None = None,
) -> tuple[str, str, ReservationStatus]:  # noqa: F821
    """Return (check_in_date, check_out_date, status) for a given bucket.

    Uses the default ranges unless custom ranges are provided.
    This function is shared by populate_reservations.py and
    setup_performance_guests.py.
    """

    rng = ranges if ranges is not None else DEFAULT_BUCKET_RANGES
    if bucket == "1":
        ci_min, ci_max = rng["1"]["check_in"]
        check_in = today - timedelta(days=random.randint(ci_min, ci_max))
        return check_in.isoformat(), today.isoformat(), ReservationStatus.CHECKED_IN

    if bucket == "2":
        ci_min, ci_max = rng["2"]["check_in"]
        co_min, co_max = rng["2"]["check_out"]
        check_in = today - timedelta(days=random.randint(ci_min, ci_max))
        check_out = today + timedelta(days=random.randint(co_min, co_max))
        return check_in.isoformat(), check_out.isoformat(), ReservationStatus.CHECKED_IN

    if bucket == "3":
        co_min, co_max = rng["3"]["check_out"]
        ci_min, ci_max = rng["3"]["check_in"]
        check_out = today - timedelta(days=random.randint(co_min, co_max))
        # check_in must be before check_out
        ci_range = (max(1, (today - check_out).days + 1), ci_max)
        check_in = today - timedelta(days=random.randint(*ci_range))
        if check_in >= check_out:
            check_in = check_out - timedelta(days=random.randint(1, 5))
        return (
            check_in.isoformat(),
            check_out.isoformat(),
            ReservationStatus.CHECKED_OUT,
        )

    if bucket == "4":
        co_min, co_max = rng["4"]["check_out"]
        check_out = today + timedelta(days=random.randint(co_min, co_max))
        return today.isoformat(), check_out.isoformat(), ReservationStatus.CONFIRMED

    raise ValueError(f"Unknown bucket: {bucket}")


def weighted_random_bucket(
    weights: dict[str, int] | None = None,
) -> str:
    """Pick a bucket key (1-4) using defined weights."""
    w = weights if weights is not None else DEFAULT_BUCKET_WEIGHTS
    keys = list(w.keys())
    vals = list(w.values())
    return random.choices(keys, weights=vals, k=1)[0]


# ---------------------------------------------------------------------------
# Guest creation helper
# ---------------------------------------------------------------------------
def generate_random_dob() -> str:
    """Generate a random date of birth string (ISO format) for a person aged 18-80."""
    min_dob = date.today() - timedelta(days=80 * 365)
    max_dob = date.today() - timedelta(days=18 * 365)
    delta = (max_dob - min_dob).days
    dob = min_dob + timedelta(days=random.randint(0, delta))
    return dob.isoformat()


# ---------------------------------------------------------------------------
# Booking channel mappings
# ---------------------------------------------------------------------------
def booking_channel_to_source(
    allowed_booking_channel: BookingChannel,  # noqa: F821
) -> BookingSource:  # noqa: F821
    """Determine booking_source based on room's allowed_booking_channel."""

    if allowed_booking_channel == BookingChannel.ON_SITE_ONLY:
        return BookingSource.WALK_IN
    if allowed_booking_channel == BookingChannel.ANY:
        return random.choice(
            [BookingSource.WEBSITE, BookingSource.PHONE, BookingSource.OTA]
        )
    if allowed_booking_channel == BookingChannel.STAFF_ASSIGNMENT:
        return BookingSource.INTERNAL
    raise ValueError(f"Unknown booking channel: {allowed_booking_channel}")


# Wing-to-channel and channel-to-times mappings shared by populate_rooms.py
WING_CHANNEL_MAP: dict[str, str] = {
    "W": "ANY",
    "N": "ON_SITE_ONLY",
    "E": "STAFF_ASSIGNMENT",
}

CHANNEL_TIMES_MAP: dict[str, tuple[str, str]] = {
    "ANY": ("15:00", "09:00"),
    "ON_SITE_ONLY": ("15:00", "09:00"),
    "STAFF_ASSIGNMENT": ("00:00", "00:00"),
}


def get_booking_channel(wing_code: str) -> str:
    """Return the allowed_booking_channel value for a given wing code."""
    channel = WING_CHANNEL_MAP.get(wing_code)
    if channel is None:
        raise ValueError(f"Unknown wing code: {wing_code}")
    return channel


def get_checkin_checkout_times(channel: str) -> tuple[str, str]:
    """Return (checkin_time, checkout_time) for a given booking channel value."""
    times = CHANNEL_TIMES_MAP.get(channel)
    if times is None:
        raise ValueError(f"Unknown booking channel: {channel}")
    return times


# ---------------------------------------------------------------------------
# Reservation date classification helpers
# These are the single source of truth for date-status classification logic.
# Both Generator scripts and app.services.core import from here.
# ---------------------------------------------------------------------------

def _coerce_date(value: date | str) -> date:
    """Convert a date string or date object to a date object."""
    return date.fromisoformat(value) if isinstance(value, str) else value


def is_checked_in_type(
    check_in_date: date | str,
    check_out_date: date | str,
    today: date,
) -> bool:
    """check_in in the past, check_out today or future -> CHECKED_IN."""
    ci = _coerce_date(check_in_date)
    co = _coerce_date(check_out_date)
    return ci < today and co >= today


def is_confirmed_type(
    check_in_date: date | str,
    check_out_date: date | str,
    today: date,
) -> bool:
    """check_in is today, check_out in the future -> CONFIRMED."""
    ci = _coerce_date(check_in_date)
    co = _coerce_date(check_out_date)
    return ci == today and co > today


def is_checked_out_type(
    check_in_date: date | str,
    check_out_date: date | str,
    today: date,
) -> bool:
    """Both dates in the past -> CHECKED_OUT."""
    ci = _coerce_date(check_in_date)
    co = _coerce_date(check_out_date)
    return ci < today and co < today


def classify_reservation_type(
    check_in_date: date | str, check_out_date: date | str, today: date
) -> str | None:
    """Classify a reservation's natural type based on its dates relative to today.

    Returns one of: "CHECKED_IN", "CONFIRMED", "CHECKED_OUT", or None.
    """
    if is_checked_in_type(check_in_date, check_out_date, today):
        return "CHECKED_IN"
    if is_confirmed_type(check_in_date, check_out_date, today):
        return "CONFIRMED"
    if is_checked_out_type(check_in_date, check_out_date, today):
        return "CHECKED_OUT"
    return None
