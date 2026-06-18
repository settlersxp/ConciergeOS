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

from utils import DB_NAME, init_connection


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


def main():
    days = parse_args()
    sign = "+" if days >= 0 else "-"
    abs_days = abs(days)
    modifier = f"{sign}{abs_days} day"

    print(f"📅 Shifting all reservations by {sign}{days} day(s) in '{DB_NAME}' ...")

    conn = init_connection()
    try:
        cursor = conn.cursor()

        # Show counts before the shift
        cursor.execute("SELECT COUNT(*) FROM Reservations")
        total = cursor.fetchone()[0]
        if total == 0:
            print("ℹ️  No reservations found. Nothing to shift.")
            return

        cursor.execute(
            "SELECT check_in_date, check_out_date FROM Reservations ORDER BY reservation_id LIMIT 5"
        )
        sample_before = cursor.fetchall()
        print(f"\n📋 Sample before ({min(5, total)} rows):")
        print(f"   {'Check-In':<14} {'Check-Out':<14}")
        for row in sample_before:
            print(f"   {row[0]:<14} {row[1]:<14}")

        # Perform the shift
        cursor.execute(
            f"""
            UPDATE Reservations
            SET check_in_date  = date(check_in_date, ?),
                check_out_date = date(check_out_date, ?)
            """,
            (modifier, modifier),
        )
        conn.commit()

        shifted = cursor.rowcount
        print(f"\n✅ Shifted {shifted} reservation(s) by {sign}{days} day(s).")

        # Show sample after the shift
        cursor.execute(
            "SELECT check_in_date, check_out_date FROM Reservations ORDER BY reservation_id LIMIT 5"
        )
        sample_after = cursor.fetchall()
        print(f"\n📋 Sample after ({min(5, total)} rows):")
        print(f"   {'Check-In':<14} {'Check-Out':<14}")
        for row in sample_after:
            print(f"   {row[0]:<14} {row[1]:<14}")

    except Exception as e:
        print(f"❌ Error: {e}")
        conn.rollback()
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()