#!/usr/bin/env python3
"""Reservations dashboard routes."""

from fastapi import APIRouter

from app.services import get_reservations_summary

router = APIRouter()


@router.get("/api/reservations")
async def api_reservations():
    """JSON endpoint returning reservations grouped by room and errors."""
    summary = get_reservations_summary()
    return summary.model_dump(mode="json")