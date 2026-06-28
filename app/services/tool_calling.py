#!/usr/bin/env python3
"""
SQLAlchemy tool calling service for LLM interactions.

Provides a set of read-only database tools that an LLM can call via function calling.
Supports multiple tool calls in a single response and chains them across multiple turns.

Imports tool definitions and system prompt from app.services.llm for consistency.

Usage:
    from app.services.tool_calling import call_llm_with_db_tools
    
    response = call_llm_with_db_tools("Show me all special guests and their reservations")
    print(response)
"""

import json
from typing import Any

from app.db import SessionLocal
from app.models import Guest, Reservation, Room
from app.services.llm import TOOL_DEFINITIONS, SHARED_SYSTEM_PROMPT, get_llm_config


# ---------------------------------------------------------------------------
# Tool Execution Functions (Read-Only)
# ---------------------------------------------------------------------------


def _format_guest(guest: Guest) -> dict[str, Any]:
    """Format a Guest object into a dictionary."""
    return {
        "guest_id": guest.guest_id,
        "first_name": guest.first_name,
        "last_name": guest.last_name,
        "date_of_birth": str(guest.date_of_birth) if guest.date_of_birth else "",
        "is_special_guest": guest.is_special_guest,
        "special_preferences": guest.special_preferences or "",
    }


def _format_reservation(reservation: Reservation) -> dict[str, Any]:
    """Format a Reservation object into a dictionary with room and guest info."""
    return {
        "reservation_id": reservation.reservation_id,
        "room_id": reservation.room_id,
        "guest_id": reservation.guest_id,
        "check_in": str(reservation.check_in_date),
        "check_out": str(reservation.check_out_date),
        "status": reservation.status.value,
        "booking_source": reservation.booking_source.value,
        "created_at": str(reservation.created_at) if reservation.created_at else "",
        "room_name": reservation.room.name if reservation.room else "",
        "guest_name": f"{reservation.guest.first_name} {reservation.guest.last_name}" if reservation.guest else "",
    }


def _execute_query_guests(params: dict[str, Any]) -> str:
    """Query guests from the database by their guest IDs.
    
    Accepts a single guest ID or an array of guest IDs.
    Returns all matching guests with their details.
    
    Args:
        params: Must contain 'guest_ids' - a single integer or array of integers.
    
    Returns:
        JSON string with guest count and array of guest objects.
    """
    db = SessionLocal()
    try:
        guest_ids = params.get("guest_ids")
        if guest_ids is None:
            return "No guest IDs provided. The 'guest_ids' parameter is required."

        # Accept a single ID or an array of IDs
        if isinstance(guest_ids, int):
            guest_ids = [guest_ids]

        if not isinstance(guest_ids, list) or not guest_ids:
            return "Invalid 'guest_ids' parameter. Must be a single integer or an array of integers."

        query = db.query(Guest).filter(Guest.guest_id.in_(guest_ids))

        guests = query.all()

        if not guests:
            return f"No guests found with the provided IDs: {guest_ids}"

        results = [_format_guest(g) for g in guests]
        return json.dumps({"count": len(results), "guests": results}, indent=2)
    finally:
        db.close()


def _execute_query_rooms(params: dict[str, Any]) -> str:
    """Query rooms from the database based on filters.
    
    Accepts:
        room_ids: A single room ID integer or an array of room ID integers.
        names: A single room name pattern string or an array of name patterns.
    
    Returns:
        JSON string with room count and array of room objects.
    """
    db = SessionLocal()
    try:
        query = db.query(Room)

        # Filter: room_ids (accepts a single ID or an array of IDs)
        room_ids = params.get("room_ids")
        if room_ids is not None:
            if isinstance(room_ids, int):
                room_ids = [room_ids]
            elif not isinstance(room_ids, list):
                room_ids = [room_ids]
            if room_ids:
                query = query.filter(Room.room_id.in_(room_ids))

        # Filter: names (accepts a single pattern or an array of patterns)
        names = params.get("names")
        if names is not None:
            if isinstance(names, str):
                names = [names]
            elif not isinstance(names, list):
                names = [names]
            if names:
                # Use OR logic: match any of the name patterns
                name_conditions = [Room.name.ilike(f"%{name}%") for name in names]
                query = query.filter(*name_conditions)

        rooms = query.all()

        if not rooms:
            return "No rooms found matching the criteria."

        results = [
            {
                "room_id": r.room_id,
                "name": r.name,
                "allowed_booking_channel": r.allowed_booking_channel.value,
                "checkin_time": r.checkin_time,
                "checkout_time": r.checkout_time,
            }
            for r in rooms
        ]
        return json.dumps({"count": len(results), "rooms": results}, indent=2)
    finally:
        db.close()


def _execute_query_reservations(params: dict[str, Any]) -> str:
    """Query reservations from the database with flexible filtering.
    
    All parameters are optional. The LLM can use any combination of filters:
    - reservation_ids: Filter by specific reservation ID(s)
    - guest_ids: Filter by guest ID(s)
    - room_ids: Filter by room ID(s)
    - statuses: Filter by reservation status(ies)
    - check_in / check_out: Filter by date(s)
    
    If no parameters are provided, returns all reservations (not recommended for large datasets).
    
    Args:
        params: Any combination of optional filter parameters.
    
    Returns:
        JSON string with reservation count and array of reservation objects.
    """
    db = SessionLocal()
    try:
        query = db.query(Reservation)

        # Filter: reservation_ids (array or single integer)
        reservation_ids = params.get("reservation_ids")
        if reservation_ids is not None:
            if isinstance(reservation_ids, int):
                reservation_ids = [reservation_ids]
            elif not isinstance(reservation_ids, list):
                reservation_ids = [reservation_ids]
            if reservation_ids:
                query = query.filter(Reservation.reservation_id.in_(reservation_ids))

        # Optional filter: guest_ids (array of integers)
        guest_ids = params.get("guest_ids")
        if guest_ids is not None:
            if isinstance(guest_ids, int):
                guest_ids = [guest_ids]
            elif not isinstance(guest_ids, list):
                guest_ids = [guest_ids]
            if guest_ids:
                query = query.filter(Reservation.guest_id.in_(guest_ids))

        # Optional filter: room_ids (array of integers)
        room_ids = params.get("room_ids")
        if room_ids is not None:
            if isinstance(room_ids, int):
                room_ids = [room_ids]
            elif not isinstance(room_ids, list):
                room_ids = [room_ids]
            if room_ids:
                query = query.filter(Reservation.room_id.in_(room_ids))

        # Optional filter: statuses (array of string enum values)
        statuses = params.get("statuses")
        if statuses is not None:
            from app.enums import ReservationStatus
            if isinstance(statuses, str):
                # Accept single status string for backward compatibility
                statuses = [statuses]
            if isinstance(statuses, list) and statuses:
                # Validate each status value against the enum
                valid_statuses = []
                invalid_statuses = []
                for s in statuses:
                    try:
                        valid_statuses.append(ReservationStatus(s))
                    except ValueError:
                        invalid_statuses.append(s)
                
                if invalid_statuses:
                    valid_options = ", ".join(s.value for s in ReservationStatus)
                    return f"Invalid status values: {invalid_statuses}. Valid options: {valid_options}"
                
                if valid_statuses:
                    query = query.filter(Reservation.status.in_(valid_statuses))

        # Optional filter: check_in (date string)
        check_in = params.get("check_in")
        if check_in:
            query = query.filter(Reservation.check_in_date == check_in)

        # Optional filter: check_out (date string)
        check_out = params.get("check_out")
        if check_out:
            query = query.filter(Reservation.check_out_date == check_out)

        reservations = query.all()

        if not reservations:
            return "No reservations found matching the criteria."

        # Warn if too many results returned (no filters applied)
        if len(reservations) > 1000:
            return f"Warning: {len(reservations)} reservations found. Consider adding filters (reservation_ids, guest_ids, room_ids, statuses, check_in, check_out) to narrow results.\n\n" + json.dumps({"count": len(reservations), "reservations": [_format_reservation(r) for r in reservations]}, indent=2)

        results = [_format_reservation(r) for r in reservations]
        return json.dumps({"count": len(results), "reservations": results}, indent=2)
    finally:
        db.close()


def _execute_get_hotel_summary(params: dict[str, Any]) -> str:
    """Get hotel summary statistics."""
    db = SessionLocal()
    try:
        from app.enums import ReservationStatus

        total_guests = db.query(Guest).count()
        total_rooms = db.query(Room).count()
        total_reservations = db.query(Reservation).count()

        # Count by status
        status_counts = {}
        for status in ReservationStatus:
            count = db.query(Reservation).filter(Reservation.status == status).count()
            status_counts[status.value] = count

        # Special guests count
        special_guests = db.query(Guest).filter(Guest.is_special_guest == True).count()

        summary = {
            "total_guests": total_guests,
            "total_rooms": total_rooms,
            "total_reservations": total_reservations,
            "special_guests": special_guests,
            "reservations_by_status": status_counts,
        }
        return json.dumps(summary, indent=2)
    finally:
        db.close()


# Map tool names to their execution functions
TOOL_EXECUTORS = {
    "query_guests": _execute_query_guests,
    "query_rooms": _execute_query_rooms,
    "query_reservations": _execute_query_reservations,
    "get_hotel_summary": _execute_get_hotel_summary,
}

# ---------------------------------------------------------------------------
# Response Cache Integration
# ---------------------------------------------------------------------------
# The response_cache module provides diagnostic logging and future caching.
# To enable response logging/caching, change the import below to use
# the wrapper from response_cache instead.
#
# To ENABLE diagnostic logging, uncomment the following import and remove
# the standard import above:
#
#   from app.services.response_cache import call_llm_with_db_tools  # WITH logging
#
# For now, this module provides the base implementation. The response_cache
# module wraps this with diagnostics.
# ---------------------------------------------------------------------------


def call_llm_with_db_tools(
    user_message: str,
    model: str | None = None,
    max_turns: int = 100,
) -> str:
    """
    Call the LLM with database tools and handle the tool calling loop.

    This function:
    1. Sends the user message with system prompt and tool definitions to the LLM
    2. Collects any function calls from the response
    3. Executes all function calls (supports multiple in one response)
    4. Sends the results back to the LLM
    5. Repeats until the LLM stops calling tools (or max_turns reached)
    6. Returns the final response text

    Args:
        user_message: The user's question or request
        model: Optional model name (uses configured model from llm.py if None)
        max_turns: Maximum number of LLM turns (default 10)

    Returns:
        The final response text from the LLM
    """
    client, model_name = get_llm_config()
    if model:
        model_name = model

    # Initialize conversation - uses unified system prompt from llm.py
    messages = [
        {"role": "system", "content": SHARED_SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]

    for turn in range(max_turns):
        # Call LLM with tools
        response = client.chat.completions.create(
            model=model_name,
            messages=messages,
            tools=TOOL_DEFINITIONS,
            temperature=0.1,
            max_tokens=102400,
        )

        assistant_message = response.choices[0].message

        # Check if the assistant wants to call tools
        tool_calls = assistant_message.tool_calls or []

        if not tool_calls:
            # No more tool calls - this is the final response
            return assistant_message.content or "The LLM returned an empty response."

        # Append assistant message to conversation
        messages.append(assistant_message)

        # Execute ALL tool calls in this response (batch execution)
        for tool_call in tool_calls:
            func_name = tool_call.function.name
            func_args = json.loads(tool_call.function.arguments)
            call_id = tool_call.id

            # Execute the tool
            if func_name in TOOL_EXECUTORS:
                try:
                    result = TOOL_EXECUTORS[func_name](func_args)
                except Exception as e:
                    result = f"Error executing {func_name}: {str(e)}"
            else:
                result = f"Unknown tool: {func_name}"

            # Append tool result to conversation
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call_id,
                    "content": result,
                }
            )

    # If we exhausted max_turns, return a message
    return f"The request exceeded the maximum of {max_turns} turns. Please simplify your request."