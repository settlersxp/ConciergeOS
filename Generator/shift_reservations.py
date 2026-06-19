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
from typing import Any, Dict

from Generator.utils import DB_NAME, init_connection


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


def shift_reservations(days: int = 1) -> Dict[str, Any]:
    """
    Shift all reservation check_in and check_out dates by a given number
    of days and return a result summary.

    Returns a dict with keys:
        ok (bool), shifted (int), days (int), before (list), after (list),
        and optionally error (str) or message (str).
    """
    modifier = _build_modifier(days)

    conn = init_connection()
    try:
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM Reservations")
        total = cursor.fetchone()[0]
        if total == 0:
            return {
                "ok": True,
                "shifted": 0,
                "days": days,
                "message": "No reservations found. Nothing to shift.",
                "before": [],
                "after": [],
            }

        # Sample before
        cursor.execute(
            "SELECT check_in_date, check_out_date FROM Reservations "
            "ORDER BY reservation_id LIMIT 5"
        )
        sample_before = [
            {"check_in": r[0], "check_out": r[1]} for r in cursor.fetchall()
        ]

        # Perform the shift
        cursor.execute(
            """
            UPDATE Reservations
            SET check_in_date  = date(check_in_date, ?),
                check_out_date = date(check_out_date, ?)
            """,
            (modifier, modifier),
        )
        conn.commit()
        shifted = cursor.rowcount

        # Sample after
        cursor.execute(
            "SELECT check_in_date, check_out_date FROM Reservations "
            "ORDER BY reservation_id LIMIT 5"
        )
        sample_after = [
            {"check_in": r[0], "check_out": r[1]} for r in cursor.fetchall()
        ]

        return {
            "ok": True,
            "shifted": shifted,
            "days": days,
            "before": sample_before,
            "after": sample_after,
        }

    except Exception as e:
        conn.rollback()
        return {"ok": False, "error": str(e)}
    finally:
        conn.close()


def main():
    days = parse_args()
    sign = "+" if days >= 0 else "-"

    print(f"📅 Shifting all reservations by {sign}{days} day(s) in '{DB_NAME}' ...")

    result = shift_reservations(days)

    if not result["ok"]:
        print(f"❌ Error: {result['error']}")
        sys.exit(1)

    if result.get("message"):
        print(result["message"])
        return

    total_before = len(result["before"])
    print(f"\n📋 Sample before ({total_before} rows):")
    print(f"   {'Check-In':<14} {'Check-Out':<14}")
    for row in result["before"]:
        print(f"   {row['check_in']:<14} {row['check_out']:<14}")

    print(f"\n✅ Shifted {result['shifted']} reservation(s) by {sign}{days} day(s).")

    total_after = len(result["after"])
    print(f"\n📋 Sample after ({total_after} rows):")
    print(f"   {'Check-In':<14} {'Check-Out':<14}")
    for row in result["after"]:
        print(f"   {row['check_in']:<14} {row['check_out']:<14}")


if __name__ == "__main__":
    main()