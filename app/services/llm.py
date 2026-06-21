#!/usr/bin/env python3
"""
LLM service for querying guest information via an OpenAI-compatible endpoint.
"""

import xml.etree.ElementTree as ET
from pathlib import Path

from openai import OpenAI

from app.db import SessionLocal
from app.models import Guest, Reservation, Room


# Local vLLM instance (OpenAI-compatible)
_LLM_CLIENT = OpenAI(
    base_url="http://10.0.0.227:8000/v1",
    api_key="none",
)
_LLM_MODEL = "Qwen/Qwen3.6-27B"

# XML output path
_XML_OUTPUT_PATH = Path("data/guests_data.xml")

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
        f"```{data}```"
        f"Find all information about the customer named: {customer_name}"
    )


def _bool_to_str(value: bool) -> str:
    """Convert Python bool to lowercase string for XML."""
    return "true" if value else "false"


def fetch_all_guests_and_reservations() -> str:
    """
    Fetch all guests, rooms, and reservations from the database
    and return as an optimized XML string. Also saves the XML to disk.
    """
    db = SessionLocal()
    try:
        # Query all rooms once (static data)
        rooms = db.query(Room).all()

        # Query reservations joined with guest and room
        rows = (
            db.query(Reservation)
            .join(Guest, Reservation.guest_id == Guest.guest_id)
            .join(Room, Reservation.room_id == Room.room_id)
            .order_by(Guest.last_name, Guest.first_name, Reservation.check_in_date)
            .all()
        )

        # Build XML tree
        root = ET.Element("hotel_data")

        # <rooms> section — static, defined once
        rooms_elem = ET.SubElement(root, "rooms")
        for room in rooms:
            ET.SubElement(
                rooms_elem,
                "room",
                {
                    "id": str(room.room_id),
                    "name": room.name,
                    "allowed_booking_channel": room.allowed_booking_channel.value,
                    "checkin_time": room.checkin_time,
                    "checkout_time": room.checkout_time,
                },
            )

        # <guests> section — one entry per guest+reservation combination
        guests_elem = ET.SubElement(root, "guests")
        guests_map: dict[int, ET.Element] = {}
        for res in rows:
            gid = res.guest_id
            if gid not in guests_map:
                guests_map[gid] = ET.SubElement(
                    guests_elem,
                    "guest",
                    {
                        "id": str(gid),
                        "first_name": res.guest.first_name,
                        "last_name": res.guest.last_name,
                        "date_of_birth": res.guest.date_of_birth,
                        "is_special_guest": _bool_to_str(res.guest.is_special_guest),
                        "special_preferences": res.guest.special_preferences or "",
                    },
                )
            ET.SubElement(
                guests_map[gid],
                "reservation",
                {
                    "id": str(res.reservation_id),
                    "room_id": str(res.room_id),
                    "check_in": str(res.check_in_date),
                    "check_out": str(res.check_out_date),
                    "status": res.status.value,
                    "booking_source": res.booking_source.value,
                    "created_at": str(res.created_at) if res.created_at else "",
                },
            )

        # Generate XML string with declaration
        xml_bytes = ET.tostring(root, encoding="unicode")
        xml_output = '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_bytes

        # Save to disk
        _XML_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        _XML_OUTPUT_PATH.write_text(xml_output, encoding="utf-8")

        return xml_output
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