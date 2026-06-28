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
import time
from typing import Optional

from app.db import SessionLocal
from app.models import Guest, Reservation, Room

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Name-to-ID resolution cache
# ---------------------------------------------------------------------------
# TTL for cached name-to-ID lookups (in seconds).
# When guest data changes, call resolve_cache_clear() to invalidate.
_NAME_CACHE_TTL = 300  # 5 minutes

# In-memory cache: "table:column:value" -> {"ids": [...], "timestamp": float}
_name_cache: dict[str, dict] = {}


def _get_name_cache_key(table: str, column: str, value: str) -> str:
    """Generate a cache key for a name lookup."""
    return f"{table}:{column}:{value}"


def resolve_cache_get(cache_key: str) -> list[int] | None:
    """
    Get a cached name-to-ID resolution result.
    
    Returns None if not cached or expired.
    """
    entry = _name_cache.get(cache_key)
    if entry is None:
        return None
    if time.time() - entry["timestamp"] > _NAME_CACHE_TTL:
        del _name_cache[cache_key]
        return None
    return entry["ids"]


def resolve_cache_set(cache_key: str, ids: list[int]) -> None:
    """Cache a name-to-ID resolution result."""
    _name_cache[cache_key] = {
        "ids": ids,
        "timestamp": time.time(),
    }


def resolve_cache_clear() -> int:
    """Clear the name-to-ID resolution cache. Returns the count of entries cleared."""
    count = len(_name_cache)
    _name_cache.clear()
    return count


def resolve_cache_cleanup() -> int:
    """Remove expired entries. Returns the count removed."""
    now = time.time()
    expired_keys = [
        k for k, v in _name_cache.items()
        if now - v["timestamp"] > _NAME_CACHE_TTL
    ]
    for key in expired_keys:
        del _name_cache[key]
    return len(expired_keys)


def resolve_cache_stats() -> dict:
    """Return cache statistics."""
    return {
        "size": len(_name_cache),
        "ttl": _NAME_CACHE_TTL,
    }

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


def _resolve_guest_params(params: dict) -> dict:
    """Resolve guest query parameters to guest_id or guest_ids.
    
    Handles both singular (guest_id) and plural (guest_ids) parameter names
    to support single and array-based queries.
    
    Uses an in-memory cache for name-based lookups to avoid redundant DB queries.
    """
    # Priority 1: Direct guest_ids (plural) or guest_id (singular)
    guest_ids = params.get("guest_ids") or params.get("guest_id")
    if guest_ids is not None:
        if isinstance(guest_ids, int):
            guest_ids = [guest_ids]
        elif not isinstance(guest_ids, list):
            guest_ids = [guest_ids]
        return {"guest_ids": list(map(int, guest_ids))}

    # Priority 2: Name-based lookup (with caching)
    cache_key_parts = []
    if params.get("first_name"):
        cache_key_parts.append(f"first:{params['first_name']}")
    if params.get("last_name"):
        cache_key_parts.append(f"last:{params['last_name']}")
    if params.get("is_special_guest") is not None:
        cache_key_parts.append(f"special:{params['is_special_guest']}")
    
    name_cache_key = _get_name_cache_key("guests", ":".join(cache_key_parts), "") if cache_key_parts else None
    
    if name_cache_key:
        cached = resolve_cache_get(name_cache_key)
        if cached is not None:
            logger.debug(f"[NAME-CACHE] HIT for guests lookup: {cache_key_parts}")
            if len(cached) == 1:
                return {"guest_ids": cached}
            elif len(cached) > 1:
                return {"guest_ids": cached}
            # Multiple matches or none - fall through to DB query for accuracy
    
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

        guests = query.all()
        guest_ids = [g.guest_id for g in guests]
        
        # Cache name-based results
        if name_cache_key and guest_ids:
            resolve_cache_set(name_cache_key, guest_ids)
            if len(guest_ids) == 1:
                logger.debug(f"[NAME-CACHE] SET for guests lookup: {cache_key_parts} -> {guest_ids}")
            else:
                logger.debug(f"[NAME-CACHE] SET for guests lookup: {cache_key_parts} -> {len(guest_ids)} results")

        if guests:
            return {"guest_ids": guest_ids}
    finally:
        db.close()

    # Fallback: return params as-is for non-ID filters
    result = {}
    if params.get("is_special_guest") is not None:
        result["is_special_guest"] = int(params["is_special_guest"])
    return result


def _resolve_room_params(params: dict) -> dict:
    """Resolve room query parameters to room_id or room_ids.
    
    Handles both singular (room_id) and plural (room_ids) parameter names
    to support single and array-based queries.
    """
    # Priority 1: Direct room_ids (plural) or room_id (singular)
    room_ids = params.get("room_ids") or params.get("room_id")
    if room_ids is not None:
        if isinstance(room_ids, int):
            room_ids = [room_ids]
        elif not isinstance(room_ids, list):
            room_ids = [room_ids]
        return {"room_ids": list(map(int, room_ids))}

    # Priority 2: Name-based lookup
    db = SessionLocal()
    try:
        query = db.query(Room)
        if params.get("name"):
            query = query.filter(Room.name.ilike(f"%{params['name']}%"))

        room = query.first()
        if room:
            return {"room_ids": [room.room_id]}
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