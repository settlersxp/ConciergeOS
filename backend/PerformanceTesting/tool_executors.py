"""Tool executor functions and registry for LLM tool calling.

Each executor queries the hotel database and returns a JSON string result.
The ``TOOL_EXECUTORS`` dictionary maps tool names (as referenced in LLM
tool definitions) to these callable implementations.
"""

from __future__ import annotations

from typing import Any, Callable

from app.services.tool_logic import (
    execute_query_guests,
    execute_query_rooms,
    execute_query_reservations,
    execute_get_hotel_summary,
)


# ── Registry ────────────────────────────────────────────────────────────────

TOOL_EXECUTORS: dict[str, Callable[[dict[str, Any]], str]] = {
    "query_guests": execute_query_guests,
    "query_rooms": execute_query_rooms,
    "query_reservations": execute_query_reservations,
    "get_hotel_summary": execute_get_hotel_summary,
}