#!/usr/bin/env python3
"""Placeholder system for prompt templates."""

import logging
import re
from datetime import datetime

from app.db import engine
from app.models import Guest, Reservation, Room

logger = logging.getLogger(__name__)

AVAILABLE_PLACEHOLDERS: dict[str, dict] = {
    "DATABASE_TABLES": {
        "description": "Full schema of all database tables, including column names, types, constraints, and foreign keys",
        "category": "schema",
        "dynamic": True,
        "example": "Table: Guests\n  guest_id: INTEGER [PRIMARY KEY, NOT NULL]\n  first_name: VARCHAR [NOT NULL]",
        "resolver": "_resolve_database_tables",
    },
    "GUEST_INFORMATION": {
        "description": "Current guest directory showing all guests in the database (ID, first name, last name)",
        "category": "data",
        "dynamic": True,
        "example": "| Guest ID | First Name | Last Name |\n|---------|-----------|----------|\n| 1 | John | Doe |",
        "resolver": "_resolve_guest_information",
    },
    "ROOM_INFORMATION": {
        "description": "List of all hotel rooms with their names, booking channels, and check-in/check-out times",
        "category": "data",
        "dynamic": True,
        "example": "| Room ID | Name | Channel | Check-in | Check-out |\n|---------|------|---------|----------|-----------|",
        "resolver": "_resolve_room_information",
    },
    "CURRENT_DATE": {
        "description": "Today's date in ISO format (YYYY-MM-DD)",
        "category": "context",
        "dynamic": True,
        "example": "2026-06-27",
        "resolver": "_resolve_current_date",
    },
    "AVAILABLE_TOOLS": {
        "description": "Human-readable description of all available database query tools",
        "category": "schema",
        "dynamic": True,
        "example": "- query_guests: Search for guests by their guest IDs (accepts 1 or more IDs)\n- query_rooms: Search for rooms by ID or name",
        "resolver": "_resolve_available_tools",
    },
}


def _get_db_schema() -> dict:
    """Return structured schema info for all database tables.

    Returns a dict mapping table names to lists of column info dicts.
    Reused by both the {DATABASE_TABLES} resolver and the /field-schema API endpoint.
    """
    from sqlalchemy import MetaData
    metadata = MetaData()
    metadata.reflect(bind=engine)
    schema: dict[str, list[dict]] = {}
    for table_name, table in metadata.tables.items():
        columns: list[dict] = []
        for col_name, column in table.columns.items():
            col_type = str(column.type)
            constraints: list[str] = []
            if column.primary_key:
                constraints.append("PRIMARY KEY")
            if not column.nullable:
                constraints.append("NOT NULL")
            for fk in column.foreign_keys:
                constraints.append(f"FK->{fk.target_fullname}")
            columns.append({
                "field": col_name,
                "type": col_type,
                "constraints": constraints,
                "nullable": not column.nullable,
                "primary_key": column.primary_key,
                "foreign_keys": [fk.target_fullname for fk in column.foreign_keys],
            })
        schema[table_name] = columns
    return schema


def _resolve_database_tables() -> str:
    """Generate a schema description by introspecting the actual database tables."""
    schema = _get_db_schema()
    lines = ["## Database Schema", "", "You have access to a SQLite database with the following tables:", ""]
    for table_name, columns in schema.items():
        lines.append(f"### {table_name}")
        lines.append("```")
        lines.append(f"Table: {table_name}")
        for col in columns:
            col_type = col["type"]
            constraint_str = ", ".join(col["constraints"])
            lines.append(f"  {col['field']}: {col_type}{' [' + constraint_str + ']' if constraint_str else col_type}")
        lines.append("```")
        lines.append("")
    return "\n".join(lines)


def _resolve_guest_information() -> str:
    """Generate a list of all guests in the database for context."""
    try:
        from app.db import SessionLocal
        db = SessionLocal()
        guests = db.query(Guest).order_by(Guest.guest_id).all()
        db.close()
        if not guests:
            return "## Guest Directory\n\nNo guests found."
        lines = [
            "## Guest Directory", "", "The following guests are currently in the database:", "",
            "| Guest ID | First Name | Last Name |", "|----------|-----------|----------|",
        ]
        for guest in guests:
            lines.append(f"| {guest.guest_id} | {guest.first_name} | {guest.last_name} |")
        lines.append("")
        return "\n".join(lines)
    except Exception as e:
        logger.warning(f"Failed to generate guest information: {e}")
        return ""


def _resolve_room_information() -> str:
    """Generate a list of all hotel rooms."""
    try:
        from app.db import SessionLocal
        db = SessionLocal()
        rooms = db.query(Room).order_by(Room.room_id).all()
        db.close()
        if not rooms:
            return "## Room Directory\n\nNo rooms found."
        lines = [
            "## Room Directory", "", "The following rooms are available:", "",
            "| Room ID | Name | Channel | Check-in | Check-out |",
            "|---------|------|---------|----------|-----------|",
        ]
        for room in rooms:
            ch = room.allowed_booking_channel
            ch_str = ch.value if hasattr(ch, "value") else str(ch)
            lines.append(f"| {room.room_id} | {room.name} | {ch_str} | {room.checkin_time} | {room.checkout_time} |")
        lines.append("")
        return "\n".join(lines)
    except Exception as e:
        logger.warning(f"Failed to generate room information: {e}")
        return ""


def _resolve_hotel_summary() -> str:
    """Generate high-level hotel statistics."""
    try:
        from app.db import SessionLocal
        db = SessionLocal()
        total_guests = db.query(Guest).count()
        total_rooms = db.query(Room).count()
        total_res = db.query(Reservation).count()
        res_by_status: dict[str, int] = {}
        for st in ["PENDING", "CONFIRMED", "CHECKED_IN", "CHECKED_OUT", "CANCELLED"]:
            c = db.query(Reservation).filter(Reservation.status == st).count()
            if c > 0:
                res_by_status[st] = c
        special = db.query(Guest).filter(Guest.is_special_guest == True).count()
        rl = ["## Hotel Summary", "", f"- **Total Guests:** {total_guests} (Special: {special}, Regular: {total_guests - special})", f"- **Total Rooms:** {total_rooms}", f"- **Total Reservations:** {total_res}"]
        if res_by_status:
            rl += ["", "### Reservations by Status", "", "| Status | Count |", "|--------|-------|"]
            for st, cnt in sorted(res_by_status.items()):
                rl.append(f"| {st} | {cnt} |")
            rl.append("")
        db.close()
        return "\n".join(rl)
    except Exception as e:
        logger.warning(f"Failed to generate hotel summary: {e}")
        return ""


def _resolve_current_date() -> str:
    """Return today's date in ISO format."""
    return datetime.now().strftime("%Y-%m-%d")


def _resolve_available_tools() -> str:
    """Generate human-readable description of available database query tools."""
    from app.services.llm import TOOL_DEFINITIONS
    rl = ["## Available Tools", "", "You have access to the following database query tools:", ""]
    for td in TOOL_DEFINITIONS:
        func = td.get("function", {})
        name = func.get("name", "unknown")
        desc = func.get("description", "No description available.")
        rl.append(f"- `{name}`: {desc}")
    rl.append("")
    return "\n".join(rl)


RESOLVERS: dict[str, callable] = {
    "_resolve_database_tables": lambda: _resolve_database_tables(),
    "_resolve_guest_information": lambda: _resolve_guest_information(),
    "_resolve_room_information": lambda: _resolve_room_information(),
    "_resolve_hotel_summary": lambda: _resolve_hotel_summary(),
    "_resolve_current_date": lambda: _resolve_current_date(),
    "_resolve_available_tools": lambda: _resolve_available_tools(),
}


def resolve_placeholders(text: str) -> str:
    """Replace all {PLACEHOLDER_NAME} occurrences with their resolved content."""
    def replacer(match: re.Match) -> str:
        name = match.group(1).upper()
        meta = AVAILABLE_PLACEHOLDERS.get(name)
        if meta and meta.get("resolver") in RESOLVERS:
            try:
                return RESOLVERS[meta["resolver"]]()
            except Exception as e:
                logger.warning(f"Failed to resolve placeholder '{{{name}}}': {e}")
                return match.group(0)
        return match.group(0)
    return re.sub(r"\{([A-Za-z_][A-Za-z0-9_]*)\}", replacer, text)


# ---------------------------------------------------------------------------
# Runtime variables: {table.field} → user-provided value
# ---------------------------------------------------------------------------


def resolve_all_placeholders(
    text: str,
    runtime_variables: dict[str, str] | None = None,
) -> str:
    """Replace ALL placeholders: static (DB-resolved) + runtime (user-provided).

    Phase 1 — Static placeholders (DATABASE_TABLES, GUEST_INFORMATION, etc.)
      Resolved from database schema, current date, tool definitions, etc.
      These are the same for every query.

    Phase 2 — Runtime variables ({table.field} → user-provided value)
      Resolved from a key-value map supplied at call time.
      Examples: {"customers.first_name": "عائشة", "rooms.room_id": "42"}

    Order matters: static placeholders are resolved first so their content
    never gets partially mangled by runtime-variable replacement.

    Args:
        text: The template string containing placeholders like {DATABASE_TABLES}
              and/or {table.field}.
        runtime_variables: Optional dict mapping runtime variable keys (e.g.
              "customers.first_name") to their runtime values.

    Returns:
        The fully resolved string with all placeholders replaced.
    """
    # Phase 1: Static placeholders (DATABASE_TABLES, GUEST_INFORMATION, etc.)
    text = resolve_placeholders(text)

    # Phase 2: Runtime variables ({table.field} → user-provided value)
    if runtime_variables:
        for key, value in runtime_variables.items():
            placeholder = f"{{{key}}}"
            if placeholder in text:
                text = text.replace(placeholder, str(value))

    return text


def get_all_placeholders() -> dict:
    """Return metadata for the frontend (no resolver functions)."""
    return {
        key: {
            "description": meta["description"],
            "category": meta["category"],
            "dynamic": meta["dynamic"],
            "example": meta["example"][:200] + ("..." if len(meta["example"]) > 200 else ""),
        }
        for key, meta in AVAILABLE_PLACEHOLDERS.items()
    }
