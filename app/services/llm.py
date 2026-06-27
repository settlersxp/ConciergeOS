#!/usr/bin/env python3
"""
LLM service for querying guest information via an OpenAI-compatible endpoint.

Provides unified system prompts, model management with Pydantic, and tool definitions
for database interactions.
"""

import csv
import io
import json
import logging
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Callable

from openai import OpenAI
from pydantic import BaseModel

from app.db import SessionLocal, engine
from app.models import Guest, Reservation, Room
from app.config import config_manager

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pydantic Models for LLM Model Management
# ---------------------------------------------------------------------------

class LLMModelInfo(BaseModel):
    """Represents an available LLM model from the server."""
    id: str
    object: str = "model"
    created: int = 0
    owned_by: str = "vllm"


class LLMModelList(BaseModel):
    """Response from the /v1/models endpoint."""
    object: str = "list"
    data: list[LLMModelInfo] = []


# ---------------------------------------------------------------------------
# SQLAlchemy Database Introspection for Schema Generation
# ---------------------------------------------------------------------------

def _generate_schema_from_database() -> str:
    """Generate a schema description by introspecting the actual database tables.
    
    Uses SQLAlchemy's MetaData.reflect() to read the actual database schema,
    as described in: https://stackoverflow.com/questions/44193823
    
    Returns a human-readable description of all tables, columns, types,
    constraints, and relationships.
    """
    from sqlalchemy import MetaData
    
    lines = [
        "## Database Schema",
        "",
        "You have access to a SQLite database with the following tables:",
        "",
    ]
    
    # Reflect all tables from the actual database
    metadata = MetaData()
    metadata.reflect(bind=engine)
    
    for table_name, table in metadata.tables.items():
        lines.append(f"### {table_name}")
        lines.append("```")
        lines.append(f"Table: {table_name}")
        
        for col_name, column in table.columns.items():
            col_type = str(column.type)
            constraints = []
            
            if column.primary_key:
                constraints.append("PRIMARY KEY")
            if not column.nullable:
                constraints.append("NOT NULL")
            if column.default is not None:
                # Try to get a static default value
                try:
                    default_val = column.default.arg if hasattr(column.default, 'arg') else str(column.default)
                    constraints.append(f"DEFAULT {default_val}")
                except Exception:
                    pass
            if column.server_default is not None:
                try:
                    constraints.append(f"ServerDefault: {column.server_default.arg}")
                except Exception:
                    pass
            
            # Check for foreign keys
            for fk in column.foreign_keys:
                constraints.append(f"FK->{fk.target_fullname}")
            
            constraint_str = ", ".join(constraints)
            lines.append(f"  {col_name}: {col_type}{' [' + constraint_str + ']' if constraint_str else ''}")
        
        # Add table-level comments for relationships
        if table.comment:
            lines.append(f"  -- {table.comment}")
        
        lines.append("```")
        lines.append("")
    
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Guest Information Generator
# ---------------------------------------------------------------------------

def _generate_guest_information() -> str:
    """Generate a list of all guests in the database for context.

    Returns a formatted markdown section with guest_id, first_name, and last_name.
    """
    try:
        db = SessionLocal()
        guests = db.query(Guest).order_by(Guest.guest_id).all()
        db.close()

        if not guests:
            return ""

        lines = [
            "## Guest Directory",
            "",
            "The following guests are currently in the database:",
            "",
            "| Guest ID | First Name | Last Name |",
            "|----------|-----------|----------|",
        ]

        for guest in guests:
            lines.append(f"| {guest.guest_id} | {guest.first_name} | {guest.last_name} |")

        lines.append("")
        lines.append(
            "Use this directory to quickly identify guests by name when receiving queries."
        )
        lines.append("")

        return "\n".join(lines)
    except Exception as e:
        logger.warning(f"Failed to generate guest information: {e}")
        return ""


# ---------------------------------------------------------------------------
# Shared System Prompt (unified across the application)
# ---------------------------------------------------------------------------

_BASE_SYSTEM_INSTRUCTIONS = """\
You are a helpful hotel concierge assistant with access to database query tools.

When providing information about a guest, always use the following markdown structure:

### Guest [Number] (ID: [ID])
* **Full Name:** [First name] [Last name]
* **Date of Birth:** [YYYY-MM-DD]
* **Special Guest:** [Yes/No]
* **Special Preferences:** [Preferences or 'None']
* **Reservations:**
  1. **Reservation ID:** [ID]
     * **Room id:** [ID]
     * **Room:** [Room Name]
     * **Check-in:** [YYYY-MM-DD] | **Check-out:** [YYYY-MM-DD]
     * **Status:** [STATUS] | **Source:** [SOURCE]
  2. ... (continue for all reservations)
"""

_SCHEMA_DESCRIPTION = _generate_schema_from_database()
_GUEST_INFORMATION = _generate_guest_information()

_SYSTEM_PROMPT_WITH_SCHEMA = f"""\
{_BASE_SYSTEM_INSTRUCTIONS}

{_SCHEMA_DESCRIPTION}

{_GUEST_INFORMATION}
## Available Tools
You have access to the following database query tools:
- `query_guests`: Search for guests by name, ID, or attributes
- `query_rooms`: Search for rooms by ID or name
- `query_reservations`: Search for reservations by various criteria
- `get_hotel_summary`: Get overall hotel statistics

Use these tools to answer questions about the hotel database. Always call the appropriate tool rather than guessing at data.
"""

# Legacy system prompt (for backward compatibility - data-prompting approach)
SYSTEM_PROMPT = (
    "You are a helpful hotel concierge assistant. "
    "You will receive a JSON dataset containing all guests with their rooms and reservations. "
    "Given a customer name, return all available information about that guest, "
    "including personal details, rooms, and all reservations. "
    "If the guest is not found, say so clearly. "
    "Format your response in a clear, readable way."
)

# Exported unified system prompt
SHARED_SYSTEM_PROMPT = _SYSTEM_PROMPT_WITH_SCHEMA


# ---------------------------------------------------------------------------
# Tool Definitions (OpenAI function calling format)
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "query_guests",
            "description": "Search for guests in the hotel database. All parameters are optional filters.",
            "parameters": {
                "type": "object",
                "properties": {
                    "guest_id": {
                        "type": "integer",
                        "description": "Filter by specific guest ID",
                    },
                    "first_name": {
                        "type": "string",
                        "description": "Filter by first name (case-insensitive partial match)",
                    },
                    "last_name": {
                        "type": "string",
                        "description": "Filter by last name (case-insensitive partial match)",
                    },
                    "is_special_guest": {
                        "type": "boolean",
                        "description": "Filter by special guest status. true for special guests only, false for regular guests.",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_rooms",
            "description": "Search for rooms in the hotel. All parameters are optional filters.",
            "parameters": {
                "type": "object",
                "properties": {
                    "room_id": {
                        "type": "integer",
                        "description": "Filter by specific room ID",
                    },
                    "name": {
                        "type": "string",
                        "description": "Filter by room name (case-insensitive partial match)",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_reservations",
            "description": "Search for reservations in the hotel database. All parameters are optional filters.",
            "parameters": {
                "type": "object",
                "properties": {
                    "reservation_id": {
                        "type": "integer",
                        "description": "Filter by specific reservation ID",
                    },
                    "guest_id": {
                        "type": "integer",
                        "description": "Filter by guest ID",
                    },
                    "room_id": {
                        "type": "integer",
                        "description": "Filter by room ID",
                    },
                    "status": {
                        "type": "string",
                        "enum": ["PENDING", "CONFIRMED", "CHECKED_IN", "CHECKED_OUT", "CANCELLED"],
                        "description": "Filter by reservation status",
                    },
                    "check_in": {
                        "type": "string",
                        "description": "Filter by check-in date (ISO format YYYY-MM-DD)",
                    },
                    "check_out": {
                        "type": "string",
                        "description": "Filter by check-out date (ISO format YYYY-MM-DD)",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_hotel_summary",
            "description": "Get an overview of the hotel including total counts of guests, rooms, and reservations broken down by status.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
]


# ---------------------------------------------------------------------------
# LLM Client & Config
# ---------------------------------------------------------------------------

def get_llm_config() -> tuple[OpenAI, str]:
    """
    Dynamically fetch the LLM client and model name from the global configuration.
    If the vLLM server is unreachable, returns a fallback client and model.
    Derives base_url from models_endpoint by removing '/models' suffix.
    """
    models_endpoint = config_manager.test_settings.models_endpoint
    model_name = config_manager.test_settings.model_name
    
    # Derive base URL from models endpoint (remove '/models' suffix)
    base_url = models_endpoint.rstrip('/').replace('/models', '')
    
    client = OpenAI(base_url=base_url, api_key="none")
    try:
        # Verify connectivity and model availability
        models = client.models.list()
        if models.data:
            # If the configured model is in the list, use it. 
            # Otherwise, use the first available model.
            available_model_ids = [m.id for m in models.data]
            if model_name in available_model_ids:
                return client, model_name
            else:
                print(f"Warning: Configured model '{model_name}' not found. Using first available: {models.data[0].id}")
                return client, models.data[0].id
    except Exception as e:
        print(f"Warning: Failed to fetch LLM config dynamically: {e}. Using fallback.")
    
    # Extremely basic fallback if everything fails
    return client, "facebook/opt-125m"


def get_available_models() -> list[LLMModelInfo]:
    """Fetch all available models from the configured LLM endpoint.
    
    Returns:
        List of LLMModelInfo objects representing available models.
    """
    models_endpoint = config_manager.test_settings.models_endpoint
    base_url = models_endpoint.rstrip('/').replace('/models', '')
    
    client = OpenAI(base_url=base_url, api_key="none")
    try:
        models = client.models.list()
        return [LLMModelInfo(id=m.id, object=m.object, created=m.created, owned_by=m.owned_by) for m in models.data]
    except Exception as e:
        print(f"Warning: Failed to fetch available models: {e}")
        return []


# ---------------------------------------------------------------------------
# User Prompt Builder
# ---------------------------------------------------------------------------

def build_user_prompt(customer_name: str, data: str) -> str:
    """Build the user prompt for querying a guest by name."""
    return (
        f"Here is the full dataset of guests, rooms, and reservations:\n\n"
        f"```{data}```"
        f"Find all information about the customer named: {customer_name}"
    )


# ---------------------------------------------------------------------------
# Data Fetching & Transformation
# ---------------------------------------------------------------------------

def _fetch_raw_data() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Fetch all guests, rooms, and reservations from the database.
    Returns structured data: (rooms_list, guests_list)
    """
    db = SessionLocal()
    try:
        rooms = db.query(Room).order_by(Room.room_id).all()
        guests = db.query(Guest).order_by(Guest.guest_id).all()
        reservations = db.query(Reservation).order_by(Reservation.reservation_id).all()

        rooms_list: list[dict[str, Any]] = [
            {
                "room_id": room.room_id,
                "name": room.name,
                "allowed_booking_channel": room.allowed_booking_channel.value,
                "checkin_time": room.checkin_time,
                "checkout_time": room.checkout_time,
            }
            for room in rooms
        ]

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


def _save_to_disk(path: Path, content: str) -> None:
    """Helper to ensure directory exists and write content to file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


# Output paths
_OUTPUT_PATHS: dict[str, Path] = {
    "csv": Path("data/guests_data.csv"),
    "json": Path("data/guests_data.json"),
    "xml": Path("data/guests_data.xml"),
}


def _to_csv(rooms_list: list[dict[str, Any]], guests_list: list[dict[str, Any]]) -> str:
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
            room_info: dict[str, Any] = next((r for r in rooms_list if r["room_id"] == res["room_id"]), {"name": "", "allowed_booking_channel": "", "checkin_time": "", "checkout_time": ""})
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
    return output.getvalue()


def _to_json(rooms_list: list[dict[str, Any]], guests_list: list[dict[str, Any]]) -> str:
    data = {"rooms": rooms_list, "guests": guests_list}
    return json.dumps(data, indent=2, ensure_ascii=False)


def _to_xml(rooms_list: list[dict[str, Any]], guests_list: list[dict[str, Any]]) -> str:
    root = ET.Element("hotel_data")

    rooms_elem = ET.SubElement(root, "rooms")
    for room in rooms_list:
        room_e = ET.SubElement(rooms_elem, "room")
        ET.SubElement(room_e, "id").text = str(room["room_id"])
        ET.SubElement(room_e, "name").text = room["name"]
        ET.SubElement(room_e, "allowed_booking_channel").text = room["allowed_booking_channel"]
        ET.SubElement(room_e, "checkin_time").text = room["checkin_time"]
        ET.SubElement(room_e, "checkout_time").text = room["checkout_time"]

    guests_elem = ET.SubElement(root, "guests")
    for guest in guests_list:
        guest_e = ET.SubElement(guests_elem, "guest")
        ET.SubElement(guest_e, "id").text = str(guest["guest_id"])
        ET.SubElement(guest_e, "first_name").text = guest["first_name"]
        ET.SubElement(guest_e, "last_name").text = guest["last_name"]
        ET.SubElement(guest_e, "date_of_birth").text = guest["date_of_birth"]
        ET.SubElement(guest_e, "is_special_guest").text = str(guest["is_special_guest"]).lower()
        ET.SubElement(guest_e, "special_preferences").text = guest["special_preferences"]

        res_elem = ET.SubElement(guest_e, "reservations")
        for res in guest["reservations"]:
            res_e = ET.SubElement(res_elem, "reservation")
            ET.SubElement(res_e, "id").text = str(res["reservation_id"])
            ET.SubElement(res_e, "room_id").text = str(res["room_id"])
            ET.SubElement(res_e, "check_in").text = res["check_in"]
            ET.SubElement(res_e, "check_out").text = res["check_out"]
            ET.SubElement(res_e, "status").text = res["status"]
            ET.SubElement(res_e, "booking_source").text = res["booking_source"]
            ET.SubElement(res_e, "created_at").text = res["created_at"]

    xml_decl = "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
    return xml_decl + ET.tostring(root, encoding="unicode")


def _fetch_and_save(format_key: str) -> str:
    """Orchestrates fetching, transforming, and saving data."""
    rooms, guests = _fetch_raw_data()
    
    # Explicit type hint for the registry to ensure type safety and analyzer stability
    transformers: dict[str, Callable[[list[dict[str, Any]], list[dict[str, Any]]], str]] = {
        "csv": _to_csv,
        "json": _to_json,
        "xml": _to_xml
    }
    
    content: str = transformers[format_key](rooms, guests)
    _save_to_disk(_OUTPUT_PATHS[format_key], content)
    return content


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def fetch_all_guests_and_reservations() -> str:
    """Returns CSV string and saves to disk."""
    return _fetch_and_save("csv")


def fetch_all_as_json() -> str:
    """Returns JSON string and saves to disk."""
    return _fetch_and_save("json")


def fetch_all_as_xml() -> str:
    """Returns XML string and saves to disk."""
    return _fetch_and_save("xml")


def query_guest_with_llm(customer_name: str) -> tuple[str, bool]:
    """
    Query the LLM for all information about a given guest using tool calling.
    
    This function uses the tool calling loop to allow the LLM to query the database
    directly via tools like query_guests, query_reservations, etc.
    
    Uses lazy import to avoid circular import with tool_calling module.
    
    Returns:
        A tuple of (llm_response, was_cached) where was_cached is True if the
        response was served from the cache.
    """
    # Use response_cache wrapper for diagnostic logging and caching support.
    # This captures finish_reason, token usage, truncation warnings, and response checksums.
    # To enable: ensure response_cache.py log_level is set appropriately (INFO or DEBUG)
    from app.services.response_cache import call_llm_with_db_tools_with_cache_flag
    
    user_prompt = f"Please find all information about the guest named. The guest's name can have it's name translated into the following languages Arabic, Chinese, Devanagari, Japanese, Jorean, Latin or Nordic. It is unclear if is the user's first name or last name. Retry once with every translated language if needed. Also bring the information about its reservations. : {customer_name}"
    
    try:
        result, was_cached = call_llm_with_db_tools_with_cache_flag(user_prompt)
        
        if was_cached:
            logger.info(f"Served cached response for guest: {customer_name}")
        elif result and result != "The LLM returned an empty response.":
            logger.info(f"Successfully got response for guest: {customer_name}")
        else:
            logger.warning(f"Empty response received for guest: {customer_name}")
            
        return result, was_cached
        
    except Exception as e:
        logger.error(f"Error in query_guest_with_llm for {customer_name}: {str(e)}", exc_info=True)
        return f"Error querying guest information: {str(e)}", False
