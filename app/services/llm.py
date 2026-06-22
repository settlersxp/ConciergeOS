#!/usr/bin/env python3
"""
LLM service for querying guest information via an OpenAI-compatible endpoint.
"""

import csv
import io
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from openai import OpenAI

from app.db import SessionLocal
from app.models import Guest, Reservation, Room


# Local vLLM instance (OpenAI-compatible)
_LLM_CLIENT = OpenAI(
    base_url="http://10.0.0.227:8000/v1",
    api_key="none",
)
_LLM_MODEL = "google/gemma-4-26B-A4B-it"

# Output paths
_CSV_OUTPUT_PATH = Path("data/guests_data.csv")
_JSON_OUTPUT_PATH = Path("data/guests_data.json")
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


def _fetch_raw_data():
    """
    Fetch all guests, rooms, and reservations from the database.
    Returns structured data: (rooms_list, guests_dict_with_reservations)
    """
    db = SessionLocal()
    try:
        rooms = db.query(Room).order_by(Room.room_id).all()
        guests = db.query(Guest).order_by(Guest.guest_id).all()
        reservations = db.query(Reservation).order_by(Reservation.reservation_id).all()

        rooms_list = []
        for room in rooms:
            rooms_list.append({
                "room_id": room.room_id,
                "name": room.name,
                "allowed_booking_channel": room.allowed_booking_channel.value,
                "checkin_time": room.checkin_time,
                "checkout_time": room.checkout_time,
            })

        # Build guest dict with nested reservations
        guests_dict: dict[int, dict[str, Any]] = {}
        for guest in guests:
            guests_dict[guest.guest_id] = {
                "guest_id": guest.guest_id,
                "first_name": guest.first_name,
                "last_name": guest.last_name,
                "date_of_birth": str(guest.date_of_birth) if guest.date_of_birth else "",
                "is_special_guest": guest.is_special_guest,
                "special_preferences": guest.special_preferences or "",
                "reservations": [],
            }

        for res in reservations:
            if res.guest_id in guests_dict:
                guests_dict[res.guest_id]["reservations"].append({
                    "reservation_id": res.reservation_id,
                    "room_id": res.room_id,
                    "check_in": str(res.check_in_date),
                    "check_out": str(res.check_out_date),
                    "status": res.status.value,
                    "booking_source": res.booking_source.value,
                    "created_at": str(res.created_at) if res.created_at else "",
                })

        return rooms_list, list(guests_dict.values())
    finally:
        db.close()


def fetch_all_guests_and_reservations() -> str:
    """
    Fetch all guests, rooms, and reservations from the database
    and return as a CSV string. Also saves the CSV to disk.
    """
    rooms_list, guests_list = _fetch_raw_data()

    # Build CSV using StringIO
    headers = [
        "room_id", "room_name", "allowed_booking_channel",
        "checkin_time", "checkout_time",
        "guest_id", "first_name", "last_name", "date_of_birth",
        "is_special_guest", "special_preferences",
        "reservation_id", "check_in", "check_out",
        "status", "booking_source", "created_at",
    ]

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=headers)
    writer.writeheader()

    for guest in guests_list:
        for res in guest["reservations"]:
            # Find the room info
            room_info = next((r for r in rooms_list if r["room_id"] == res["room_id"]), {})
            writer.writerow({
                "room_id": res["room_id"],
                "room_name": room_info.get("name", ""),
                "allowed_booking_channel": room_info.get("allowed_booking_channel", ""),
                "checkin_time": room_info.get("checkin_time", ""),
                "checkout_time": room_info.get("checkout_time", ""),
                "guest_id": guest["guest_id"],
                "first_name": guest["first_name"],
                "last_name": guest["last_name"],
                "date_of_birth": guest["date_of_birth"],
                "is_special_guest": guest["is_special_guest"],
                "special_preferences": guest["special_preferences"],
                "reservation_id": res["reservation_id"],
                "check_in": res["check_in"],
                "check_out": res["check_out"],
                "status": res["status"],
                "booking_source": res["booking_source"],
                "created_at": res["created_at"],
            })

    csv_output = output.getvalue()
    output.close()

    # Save to disk
    _CSV_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    _CSV_OUTPUT_PATH.write_text(csv_output, encoding="utf-8")

    return csv_output


def fetch_all_as_json() -> str:
    """
    Fetch all guests, rooms, and reservations and return as a JSON string.
    Also saves the JSON to disk.
    """
    rooms_list, guests_list = _fetch_raw_data()

    data = {
        "rooms": rooms_list,
        "guests": guests_list,
    }

    json_output = json.dumps(data, indent=2, ensure_ascii=False)

    # Save to disk
    _JSON_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    _JSON_OUTPUT_PATH.write_text(json_output, encoding="utf-8")

    return json_output


def fetch_all_as_xml() -> str:
    """
    Fetch all guests, rooms, and reservations and return as an XML string.
    Also saves the XML to disk.
    """
    rooms_list, guests_list = _fetch_raw_data()

    root = ET.Element("hotel_data")

    # Rooms section
    rooms_elem = ET.SubElement(root, "rooms")
    for room in rooms_list:
        room_e = ET.SubElement(rooms_elem, "room")
        ET.SubElement(room_e, "id").text = str(room["room_id"])
        ET.SubElement(room_e, "name").text = room["name"]
        ET.SubElement(room_e, "allowed_booking_channel").text = room["allowed_booking_channel"]
        ET.SubElement(room_e, "checkin_time").text = room["checkin_time"]
        ET.SubElement(room_e, "checkout_time").text = room["checkout_time"]

    # Guests section
    guests_elem = ET.SubElement(root, "guests")
    for guest in guests_list:
        guest_e = ET.SubElement(guests_elem, "guest")
        ET.SubElement(guest_e, "id").text = str(guest["guest_id"])
        ET.SubElement(guest_e, "first_name").text = guest["first_name"]
        ET.SubElement(guest_e, "last_name").text = guest["last_name"]
        ET.SubElement(guest_e, "date_of_birth").text = guest["date_of_birth"]
        ET.SubElement(guest_e, "is_special_guest").text = str(guest["is_special_guest"]).lower()
        prefs = ET.SubElement(guest_e, "special_preferences")
        prefs.text = guest["special_preferences"]

        # Reservations nested inside guest
        res_elem = ET.SubElement(guest_e, "reservations")
        for res in guest["reservations"]:
            res_e = ET.SubElement(res_elem, "reservation")
            ET.SubElement(res_e, "id").text = str(res["reservation_id"])
            ET.SubElement(res_e, "room_id").text = str(res["room_id"])
            ET.SubElement(res_e, "check_in").text = res["check_in"]
            ET.SubElement(res_e, "check_out").text = res["check_out"]
            ET.SubElement(res_e, "status").text = res["status"]
            ET.SubElement(res_e, "booking_source").text = res["booking_source"]
            created = ET.SubElement(res_e, "created_at")
            created.text = res["created_at"]

    # Convert to string with proper formatting
    xml_decl = "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
    xml_body = ET.tostring(root, encoding="unicode")
    xml_output = xml_decl + xml_body

    # Save to disk
    _XML_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    _XML_OUTPUT_PATH.write_text(xml_output, encoding="utf-8")

    return xml_output


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
        max_tokens=40960,
    )

    return response.choices[0].message.content or "The LLM returned an empty response."