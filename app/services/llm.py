#!/usr/bin/env python3
"""
LLM service for querying guest information via an OpenAI-compatible endpoint.
"""

import json

from openai import OpenAI

from app.db import SessionLocal
from app.models import Guest, Reservation, Room


# Local vLLM instance (OpenAI-compatible)
_LLM_CLIENT = OpenAI(
    base_url="http://10.0.0.227:8000/v1",
    api_key="none",
)
_LLM_MODEL = "Qwen/Qwen3.6-27B"

# ── Shared prompts (single source of truth) ─────────────────────────────────

SYSTEM_PROMPT = (
    "You are a helpful hotel concierge assistant. "
    "You will receive a JSON dataset containing all guests with their rooms and reservations. "
    "Given a customer name, return all available information about that guest, "
    "including personal details, rooms, and all reservations. "
    "If the guest is not found, say so clearly. "
    "Format your response in a clear, readable way."
)


def build_user_prompt(customer_name: str, data: str) -> str:
    """Build the user prompt for querying a guest by name."""
    return (
        f"Here is the full dataset of guests, rooms, and reservations:\n\n"
        f"{data}\n\n"
        f"Find all information about the customer named: {customer_name}"
    )


def fetch_all_guests_and_reservations() -> str:
    """
    Fetch all guests, rooms, and reservations from the database
    and return as a compact JSON string.
    """
    db = SessionLocal()
    try:
        rows = (
            db.query(Reservation)
            .join(Guest, Reservation.guest_id == Guest.guest_id)
            .join(Room, Reservation.room_id == Room.room_id)
            .order_by(Guest.last_name, Guest.first_name, Reservation.check_in_date)
            .all()
        )

        # Build compact dict of guests with their reservations and room info
        guests_map: dict[int, dict] = {}
        for res in rows:
            gid = res.guest_id
            if gid not in guests_map:
                guests_map[gid] = {
                    "gid": gid,
                    "first_name": res.guest.first_name,
                    "last_name": res.guest.last_name,
                    "dob": res.guest.date_of_birth,
                    "special_guest": res.guest.is_special_guest,
                    "preferences": res.guest.special_preferences,
                    "reservations": [],
                }
            guests_map[gid]["reservations"].append({
                "rid": res.reservation_id,
                "room_id": res.room_id,
                "room_name": res.room.name,
                "check_in": str(res.check_in_date),
                "check_out": str(res.check_out_date),
                "status": res.status.value,
                "source": res.booking_source.value,
            })

        # Use separators to minimize JSON size
        return json.dumps(list(guests_map.values()), separators=(",", ":"))
    finally:
        db.close()


def query_guest_with_llm(customer_name: str) -> str:
    """
    Query the LLM for all information about a given guest.
    Sends the full guest/reservation dataset as context and asks
    the LLM to return everything related to the requested customer.
    """
    data = fetch_all_guests_and_reservations()

    user_prompt = build_user_prompt(customer_name, data)

    response = _LLM_CLIENT.chat.completions.create(
        model=_LLM_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0,
        max_tokens=4096,
    )

    return response.choices[0].message.content or "The LLM returned an empty response."