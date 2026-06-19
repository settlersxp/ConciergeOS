#!/usr/bin/env python3
"""
Debug endpoints for administrative / development operations.

These endpoints are prefixed with /debug and are not intended for
production use.
"""

from typing import Any, Dict

from fastapi import APIRouter

from Generator.shift_reservations import shift_reservations as _shift_reservations

debug_router = APIRouter(prefix="/debug", tags=["debug"])


@debug_router.post("/shift-reservations")
def shift_reservations_endpoint(body: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """
    Shift all reservation check_in and check_out dates by a given number
    of days (default: 1).

    Request body (optional):
        {"days": 3}   – shift forward by 3 days
        {"days": -2}  – shift backward by 2 days
    """
    days = (body or {}).get("days", 1)
    if not isinstance(days, int):
        days = 1

    return _shift_reservations(days)