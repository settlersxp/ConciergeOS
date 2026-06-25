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
    """Query guests from the database based on filters."""
    db = SessionLocal()
    try:
        query = db.query(Guest)

        if "guest_id" in params and params["guest_id"] is not None:
            query = query.filter(Guest.guest_id == params["guest_id"])

        if "first_name" in params and params["first_name"]:
            query = query.filter(
                Guest.first_name.ilike(f"%{params['first_name']}%")
            )

        if "last_name" in params and params["last_name"]:
            query = query.filter(
                Guest.last_name.ilike(f"%{params['last_name']}%")
            )

        if "is_special_guest" in params and params["is_special_guest"] is not None:
            is_special = bool(params["is_special_guest"])
            query = query.filter(Guest.is_special_guest == is_special)

        guests = query.all()

        if not guests:
            return "No guests found matching the criteria."

        results = [_format_guest(g) for g in guests]
        return json.dumps({"count": len(results), "guests": results}, indent=2)
    finally:
        db.close()


def _execute_query_rooms(params: dict[str, Any]) -> str:
    """Query rooms from the database based on filters."""
    db = SessionLocal()
    try:
        query = db.query(Room)

        if "room_id" in params and params["room_id"] is not None:
            query = query.filter(Room.room_id == params["room_id"])

        if "name" in params and params["name"]:
            query = query.filter(Room.name.ilike(f"%{params['name']}%"))

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
    """Query reservations from the database based on filters."""
    db = SessionLocal()
    try:
        query = db.query(Reservation)

        if "reservation_id" in params and params["reservation_id"] is not None:
            query = query.filter(Reservation.reservation_id == params["reservation_id"])

        if "guest_id" in params and params["guest_id"] is not None:
            query = query.filter(Reservation.guest_id == params["guest_id"])

        if "room_id" in params and params["room_id"] is not None:
            query = query.filter(Reservation.room_id == params["room_id"])

        if "status" in params and params["status"]:
            from app.enums import ReservationStatus
            try:
                status_enum = ReservationStatus(params["status"])
                query = query.filter(Reservation.status == status_enum)
            except ValueError:
                return f"Invalid status: {params['status']}. Valid options: PENDING, CONFIRMED, CHECKED_IN, CHECKED_OUT, CANCELLED"

        if "check_in" in params and params["check_in"]:
            query = query.filter(Reservation.check_in_date == params["check_in"])

        if "check_out" in params and params["check_out"]:
            query = query.filter(Reservation.check_out_date == params["check_out"])

        reservations = query.all()

        if not reservations:
            return "No reservations found matching the criteria."

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
# Main Tool Calling Loop
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
            max_tokens=10240,
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