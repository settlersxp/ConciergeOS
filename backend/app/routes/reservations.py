#!/usr/bin/env python3
"""Reservations dashboard routes."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.services import get_reservations_summary
from app.services.reservations import shift_reservations_service
from app.schemas import ShiftRequest, ShiftResponse
from app.db import get_db

router = APIRouter()


@router.get("/api/reservations")
async def api_reservations():
    """JSON endpoint returning reservations grouped by room and errors."""
    summary = get_reservations_summary()
    return summary.model_dump(mode="json")


@router.post("/api/reservations/shift", response_model=ShiftResponse)
async def api_shift_reservations(request: ShiftRequest, db: Session = Depends(get_db)):
    """Shift all reservation dates forward/backward by the specified number of days."""
    return shift_reservations_service(db, request.days)
