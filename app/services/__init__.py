#!/usr/bin/env python3
"""Services package – re-exports for backwards compatibility."""

from app.services.core import detect_errors, get_reservations_summary, get_all_reservations_grouped_by_room

__all__ = [
    "get_reservations_summary",
    "detect_errors",
    "get_all_reservations_grouped_by_room",
]