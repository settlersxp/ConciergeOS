#!/usr/bin/env python3
"""
Shift all reservation dates forward by a specified number of days.
Usage:
    python Generator/shift_reservations.py              # shift by 1 day (default)
    python Generator/shift_reservations.py --days 3     # shift by 3 days
    python Generator/shift_reservations.py --days -2    # shift backward by 2 days
"""

import argparse
import sys

from sqlalchemy.orm import Session

from app.schemas import ShiftResponse
from app.db import DB_PATH
from Generator.utils import get_session
from app.services.reservations import shift_reservations_service


def parse_args() -> int:
    parser = argparse.ArgumentParser(
        description="Shift all reservation check_in and check_out dates by a given number of days."
    )
    parser.add_argument(
        "--days",
        type=int,
        default=1,
        help="Number of days to shift (positive = forward, negative = backward). Default: 1",
    )
    args = parser.parse_args()
    return args.days


def _build_modifier(days: int) -> str:
    sign = "+" if days >= 0 else "-"
    abs_days = abs(days)
    return f"{sign}{abs_days} day"


def shift_reservations(days: int = 1) -> ShiftResponse:
    """
    Wrapper for the service-level shift_reservations_service to maintain 
    compatibility with the CLI script.
    """
    db: Session = get_session()
    try:
        return shift_reservations_service(db, days)
    finally:
        db.close()


def main():
    days = parse_args()
    sign = "+" if days >= 0 else "-"

    print(f"📅 Shifting all reservations by {sign}{days} day(s) in '{DB_PATH}' ...")

    result = shift_reservations(days)

    if not result.ok:
        print(f"❌ Error: {result.error}")
        sys.exit(1)

    if result.message:
        print(result.message)
        return

    total_before = len(result.before)
    print(f"\n📋 Sample before ({total_before} rows):")
    print(f"   {'Check-In':<14} {'Check-Out':<14}")
    for row in result.before:
        print(f"   {row.check_in:<14} {row.check_out:<14}")

    print(f"\n✅ Shifted {result.shifted} reservation(s) by {sign}{days} day(s).")

    total_after = len(result.after)
    print(f"\n📋 Sample after ({total_after} rows):")
    print(f"   {'Check-In':<14} {'Check-Out':<14}")
    for row in result.after:
        print(f"   {row.check_in:<14} {row.check_out:<14}")


if __name__ == "__main__":
    main()