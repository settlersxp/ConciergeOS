#!/usr/bin/env python3
"""
Cache key builder for structured caching.

Generates deterministic cache keys based on:
- model_identifier: the database table/entity being queried (e.g., "guests", "rooms")
- resource_identifier: resolved database IDs (e.g., "guest_id=42")
- prompt_id: the prompt template identifier (e.g., "guest-search")
- prompt_version: the prompt version number
- model_name: the LLM model (e.g., "qwen", "gemma")

Cache key format (before hashing):
    model_identifier:resource_identifier:prompt_id:prompt_version:model_name

Example key string:
    guests:guest_id=42:guest-search:1:qwen

This ensures that queries for the same database resource (regardless of input language)
produce the same cache key, enabling multilingual cache hits.

Usage:
    from app.services.cache_key_builder import build_cache_key, build_batch_cache_key
    
    # Single resource query
    key = build_cache_key(
        tool_name="query_guests",
        params={"first_name": "Ahmed"},
        prompt_id="guest-search",
        prompt_version=1,
        model_name="qwen"
    )
    # Returns: SHA256("guests:guest_id=42:guest-search:1:qwen")
"""

import hashlib
import logging
from typing import Optional

from app.db import SessionLocal
from app.models import Guest, Reservation, Room

logger = logging.getLogger(__name__)

# Map tool names to database table/entity names
TOOL_TO_TABLE_MAP: dict[str, str] = {
    "query_guests": "guests",
    "query_rooms": "rooms",
    "query_reservations": "reservations",
    "get_hotel_summary": "summary",
}


def _tool_to_table(tool_name: str) -> str:
    """Map a tool name to its database table/entity name."""
    return TOOL_TO_TABLE_MAP.get(tool_name, tool_name)


def resolve_params(table: str, params: dict) -> dict[str, int]:
    """
    Resolve query parameters to canonical database IDs.

    Priority:
    1. If a direct ID (e.g., guest_id) is provided → use it directly
    2. If name-based (e.g., first_name/last_name) → lookup in database

    Args:
        table: Database table name ("Guests", "Rooms", "Reservations")
        params: Tool call parameters

    Returns:
        Dictionary mapping column name to resolved ID value.
        Empty dict if no ID could be resolved.
    """
    if table == "guests":
        return _resolve_guest_params(params)
    elif table == "rooms":
        return _resolve_room_params(params)
    elif table == "reservations":
        return _resolve_reservation_params(params)
    elif table == "summary":
        return {}
    else:
        return {}


def _resolve_guest_params(params: dict) -> dict[str, int]:
    """Resolve guest query parameters to guest_id."""
    # Priority 1: Direct guest_id
    if "guest_id" in params:
        return {"guest_id": int(params["guest_id"])}

    # Priority 2: Name-based lookup
    db = SessionLocal()
    try:
        query = db.query(Guest)

        if params.get("first_name"):
            query = query.filter(
                Guest.first_name.ilike(f"%{params['first_name']}%")
            )
        if params.get("last_name"):
            query = query.filter(
                Guest.last_name.ilike(f"%{params['last_name']}%")
            )
        if params.get("is_special_guest") is not None:
            is_special = bool(params["is_special_guest"])
            query = query.filter(Guest.is_special_guest == is_special)

        guest = query.first()
        if guest:
            return {"guest_id": guest.guest_id}
    finally:
        db.close()

    # Fallback: return params as-is for non-ID filters
    result = {}
    if params.get("is_special_guest") is not None:
        result["is_special_guest"] = int(params["is_special_guest"])
    return result


def _resolve_room_params(params: dict) -> dict[str, int]:
    """Resolve room query parameters to room_id."""
    if "room_id" in params:
        return {"room_id": int(params["room_id"])}

    db = SessionLocal()
    try:
        query = db.query(Room)
        if params.get("name"):
            query = query.filter(Room.name.ilike(f"%{params['name']}%"))

        room = query.first()
        if room:
            return {"room_id": room.room_id}
    finally:
        db.close()

    return {}


def _resolve_reservation_params(params: dict) -> dict:
    """Resolve reservation query parameters to reservation_id or foreign keys.
    
    Handles both singular (reservation_id, guest_id, room_id) and plural
    (reservation_ids, guest_ids, room_ids) parameter names to support
    array-based queries.
    """
    result: dict = {}

    # Handle reservation_ids (array or single)
    reservation_ids = params.get("reservation_ids") or params.get("reservation_id")
    if reservation_ids is not None:
        if isinstance(reservation_ids, int):
            reservation_ids = [reservation_ids]
        elif not isinstance(reservation_ids, list):
            reservation_ids = [reservation_ids]
        if reservation_ids:
            result["reservation_ids"] = list(map(int, reservation_ids))

    # Handle guest_ids (array or single)
    guest_ids = params.get("guest_ids") or params.get("guest_id")
    if guest_ids is not None:
        if isinstance(guest_ids, int):
            guest_ids = [guest_ids]
        elif not isinstance(guest_ids, list):
            guest_ids = [guest_ids]
        if guest_ids:
            result["guest_ids"] = list(map(int, guest_ids))

    # Handle room_ids (array or single)
    room_ids = params.get("room_ids") or params.get("room_id")
    if room_ids is not None:
        if isinstance(room_ids, int):
            room_ids = [room_ids]
        elif not isinstance(room_ids, list):
            room_ids = [room_ids]
        if room_ids:
            result["room_ids"] = list(map(int, room_ids))

    return result


def format_resource_identifier(resolved: dict) -> str:
    """
    Format resolved parameters into a resource identifier string.

    List values are sorted numerically to ensure deterministic keys
    regardless of the order IDs are returned by the LLM.

    Args:
        resolved: Dictionary of column name → ID value (int or list of ints)

    Returns:
        e.g., "guest_id=42" or "guest_id=42:room_id=5" or "guest_ids=[1,2,3]" or "_all_"
    """
    if not resolved:
        return "_all_"
    sorted_items = sorted(resolved.items())
    parts = []
    for k, v in sorted_items:
        if isinstance(v, list):
            # Sort list values numerically for deterministic cache keys
            sorted_values = sorted(v, key=lambda x: int(x) if isinstance(x, (int, str)) else x)
            parts.append(f"{k}=[{','.join(str(x) for x in sorted_values)}]")
        else:
            parts.append(f"{k}={v}")
    return ":".join(parts)


def build_cache_key(
    tool_name: str,
    params: dict,
    prompt_id: str,
    prompt_version: int,
    model_name: str,
) -> str:
    """
    Build a deterministic cache key from tool call parameters.

    The cache key string format is:
        model_identifier:resource_identifier:prompt_id:prompt_version:model_name

    Example:
        guests:guest_id=42:guest-search:1:qwen

    This ensures:
    - Same database resource → same cache key (regardless of input language)
    - Different prompts → different cache keys (different output format/language)
    - Different models → different cache keys (different response content)
    - Different prompt versions → different cache keys (updated prompts)

    Args:
        tool_name: The tool being called (e.g., "query_guests")
        params: Tool call parameters (e.g., {"first_name": "Ahmed"})
        prompt_id: Prompt template identifier (e.g., "guest-search")
        prompt_version: Prompt version number
        model_name: LLM model name (e.g., "qwen")

    Returns:
        SHA256 hex digest string
    """
    # 1. Map tool name to table/entity name
    table = _tool_to_table(tool_name)

    # 2. Resolve parameters to database IDs
    resolved = resolve_params(table, params)

    # 3. Format resource identifier
    resource_id = format_resource_identifier(resolved)

    # 4. Build key string
    key_string = f"{table}:{resource_id}:{prompt_id}:{prompt_version}:{model_name}"

    # 5. Hash and return
    return hashlib.sha256(key_string.encode("utf-8")).hexdigest()


def build_cache_key_string(
    tool_name: str,
    params: dict,
    prompt_id: str,
    prompt_version: int,
    model_name: str,
) -> str:
    """
    Build the raw (unhashed) cache key string for debugging/logging.

    Example output: "guests:guest_id=42:guest-search:1:qwen"
    """
    table = _tool_to_table(tool_name)
    resolved = resolve_params(table, params)
    resource_id = format_resource_identifier(resolved)
    return f"{table}:{resource_id}:{prompt_id}:{prompt_version}:{model_name}"


def build_summary_cache_key(
    prompt_id: str,
    prompt_version: int,
    model_name: str,
) -> str:
    """
    Build cache key for summary/aggregated queries (no specific resource).

    Example key string: "summary:_all_:hotel-summary:1:qwen"
    """
    key_string = f"summary:_all_:{prompt_id}:{prompt_version}:{model_name}"
    return hashlib.sha256(key_string.encode("utf-8")).hexdigest()