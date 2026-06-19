#!/usr/bin/env python3
"""
Debug endpoints for administrative / development operations.

These endpoints are prefixed with /debug and are not intended for
production use.
"""

from fastapi import APIRouter

from app.schemas import ShiftRequest, ShiftResponse
from Generator.shift_reservations import shift_reservations as _shift_reservations

debug_router = APIRouter(prefix="/debug", tags=["debug"])


@debug_router.post("/shift-reservations", response_model=ShiftResponse)
def shift_reservations_endpoint(body: ShiftRequest = ShiftRequest()) -> ShiftResponse:
    """
    Shift all reservation check_in and check_out dates by a given number
    of days (default: 1).

    Request body (optional):
        {"days": 3}   – shift forward by 3 days
        {"days": -2}  – shift backward by 2 days
    """
    result = _shift_reservations(body.days)
    return ShiftResponse.model_validate(result)
