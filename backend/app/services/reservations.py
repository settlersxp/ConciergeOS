#!/usr/bin/env python3
"""
Services for reservation management.
"""

from sqlalchemy import update, func
from sqlalchemy.orm import Session
from app.models import Reservation
from app.schemas import ShiftResponse, ShiftSampleEntry


def shift_reservations_service(db: Session, days: int) -> ShiftResponse:
    """
    Shift all reservation check_in and check_out dates by a given number
    of days and return a result summary.
    """
    sign = "+" if days >= 0 else "-"
    abs_days = abs(days)
    modifier = f"{sign}{abs_days} day"

    try:
        # Count total reservations
        total = db.query(Reservation).count()
        if total == 0:
            return ShiftResponse(
                ok=True,
                shifted=0,
                days=days,
                message="No reservations found. Nothing to shift.",
            )

        # Sample before
        sample_before = (
            db.query(Reservation.check_in_date, Reservation.check_out_date)
            .order_by(Reservation.reservation_id)
            .limit(5)
            .all()
        )
        before_list = [
            ShiftSampleEntry(
                check_in=row.check_in_date.isoformat(),
                check_out=row.check_out_date.isoformat(),
            )
            for row in sample_before
        ]

        # Perform the shift using SQLAlchemy Core UPDATE
        result = (
            db.execute(
                update(Reservation)
                .values(
                    check_in_date=func.date(Reservation.check_in_date, modifier),
                    check_out_date=func.date(Reservation.check_out_date, modifier),
                )
            )
        )
        db.commit()
        # Use getattr to avoid Pylance error with Result[Any]
        shifted = getattr(result, "rowcount", 0)

        # Sample after
        sample_after = (
            db.query(Reservation.check_in_date, Reservation.check_out_date)
            .order_by(Reservation.reservation_id)
            .limit(5)
            .all()
        )
        after_list = [
            ShiftSampleEntry(
                check_in=row.check_in_date.isoformat(),
                check_out=row.check_out_date.isoformat(),
            )
            for row in sample_after
        ]

        return ShiftResponse(
            ok=True,
            shifted=shifted,
            days=days,
            before=before_list,
            after=after_list,
        )

    except Exception as e:
        db.rollback()
        return ShiftResponse(ok=False, error=str(e))