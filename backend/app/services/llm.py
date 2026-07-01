#!/usr/bin/env python3
"""
LLM service for querying guest information via an OpenAI-compatible endpoint.

Provides unified system prompts, model management with Pydantic, and tool definitions
for database interactions.
"""

import csv
import io
import inspect
import json
import logging
import threading
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

import httpx
from openai import OpenAI

from app.services import tool_logic
from pydantic import BaseModel, Field, create_model

from app.db import SessionLocal, engine
if TYPE_CHECKING:
    from sqlalchemy.orm import Session
from app.models import Guest, Reservation, Room
from app.config import config_manager
from app.utils.endpoints import strip_to_base_url

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
You have access to exactly one database query tool:

- `query_guest_with_reservations`: Search for guests by name or ID and retrieve ALL their reservations in a single tool call. Pass the guest's first name, last name, or guest_id in the params field.

**IMPORTANT:** This is your ONLY tool. Use it for every guest query. It returns complete guest information with all associated reservations in one response. Do not attempt to use any other tools.
"""

# Exported unified system prompt
SHARED_SYSTEM_PROMPT = _SYSTEM_PROMPT_WITH_SCHEMA


# ---------------------------------------------------------------------------
# Tool Definitions (OpenAI function calling format)
# ---------------------------------------------------------------------------

# Mapping of tool names to their executor functions and Pydantic schemas
# Only query_guest_with_reservations is registered — it handles all guest/reservation queries
# in a single tool call, eliminating the multi-turn workflow that was causing latency.
_TOOL_REGISTRY = {
    "query_guest_with_reservations": (tool_logic.execute_query_guest_with_reservations, tool_logic.GuestWithReservationsParam),
}

# Create batch schemas dynamically to support lists of parameters
class BatchParams(BaseModel):
    params: list[Any]

def _get_batch_schema(base_schema: type[BaseModel]) -> type[BaseModel]:
    """Creates a new Pydantic model that accepts a list of base_schema objects under the 'params' key."""
    return create_model(
        f"Batch{base_schema.__name__}",
        params=(list[base_schema], Field(..., description="A list of parameter objects. Use this to perform multiple queries in a single call for better efficiency.")),
    )

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": name,
            "description": (inspect.getdoc(func) or "") + " (Supports batch execution: you can pass a list of multiple parameter objects in the 'params' field to perform multiple queries at once)",
            "parameters": _get_batch_schema(schema).model_json_schema(),
        },
    }
    for name, (func, schema) in _TOOL_REGISTRY.items()
]


# ---------------------------------------------------------------------------
# LLM Client & Config
# ---------------------------------------------------------------------------

# Shared HTTP transport — all OpenAI clients share this single connection pool.
# This is critical: without a shared transport, each OpenAI client gets its own
# isolated pool and concurrent requests cannot reuse connections across calls.
_SHARED_TRANSPORT: httpx.HTTPTransport | None = None
_SHARED_HTTP_CLIENT: httpx.Client | None = None
_http_init_lock = threading.Lock()


def _get_shared_http_client() -> httpx.Client:
    """Return a module-level singleton httpx.Client with connection pooling.

    Created lazily on first use.  All OpenAI clients constructed via
    ``_get_base_client()`` share this single underlying transport, which means
    TCP connections are reused across ALL concurrent requests — not just within
    a single client.
    """
    global _SHARED_TRANSPORT, _SHARED_HTTP_CLIENT
    if _SHARED_HTTP_CLIENT is not None:
        return _SHARED_HTTP_CLIENT

    with _http_init_lock:
        # Double-check inside lock
        if _SHARED_HTTP_CLIENT is not None:
            return _SHARED_HTTP_CLIENT

        _SHARED_TRANSPORT = httpx.HTTPTransport(
            retries=3,
            limits=httpx.Limits(
                max_connections=20,
                max_keepalive_connections=20,
            ),
        )
        _SHARED_HTTP_CLIENT = httpx.Client(
            transport=_SHARED_TRANSPORT,
            timeout=httpx.Timeout(120.0),
        )
    return _SHARED_HTTP_CLIENT


def _get_base_client() -> tuple[OpenAI, str]:
    """Internal helper to create an OpenAI client that shares a connection pool.

    Every OpenAI client passes the **same** underlying ``httpx.Client`` so that
    TCP connections are reused across all concurrent requests.
    """
    models_endpoint = config_manager.test_settings.models_endpoint
    base_url = strip_to_base_url(models_endpoint)

    # Reuse the existing shared httpx.Client
    shared_client = _get_shared_http_client()
    client = OpenAI(
        http_client=shared_client,  # type: ignore[arg-type]
        base_url=base_url,
        api_key="none",
    )
    return client, base_url


def _build_client_from_model(model: Any) -> tuple[OpenAI, str]:
    """Build an OpenAI client pointed at a model's endpoint using shared transport.

    Parameters
    ----------
    model : Any
        An ORM instance with at least ``endpoint`` and ``model_name`` fields.

    Returns
    -------
    tuple[OpenAI, str]
        An OpenAI client and the resolved model name.
    """
    base_url = strip_to_base_url(model.endpoint)
    shared_client = _get_shared_http_client()
    client = OpenAI(
        http_client=shared_client,  # type: ignore[arg-type]
        base_url=base_url,
        api_key="none",
    )
    return client, model.model_name


def get_llm_config() -> tuple[OpenAI, str]:
    """
    Dynamically fetch the LLM client and model name from the global configuration.
    If the vLLM server is unreachable, returns a fallback client and model.
    """
    client, _ = _get_base_client()
    model_name = config_manager.test_settings.model_name
    
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
                logger.warning("Configured model '%s' not found. Using first available: %s", model_name, models.data[0].id)
                return client, models.data[0].id
    except Exception as e:
        logger.warning("Failed to fetch LLM config dynamically: %s. Using fallback.", e)
    
    # Extremely basic fallback if everything fails
    return client, "facebook/opt-125m"


def get_available_models() -> list[LLMModelInfo]:
    """Fetch all available models from the configured LLM endpoint.
    
    Returns:
        List of LLMModelInfo objects representing available models.
    """
    client, _ = _get_base_client()
    try:
        models = client.models.list()
        return [LLMModelInfo(id=m.id, object=m.object, created=m.created, owned_by=m.owned_by) for m in models.data]
    except Exception as e:
        logger.warning("Failed to fetch available models: %s", e)
        return []


# ---------------------------------------------------------------------------
# DB-based model lookup (replaces config-based model selection)
# ---------------------------------------------------------------------------

def get_llm_config_by_model_id(model_id: int | None) -> tuple[OpenAI, str]:
    """Resolve model config from the LLMModels table.

    Parameters
    ----------
    model_id : int or None
        The LLMModel.model_id to look up.  If ``None`` or if the model
        cannot be found, falls back to ``get_llm_config()``.

    Returns
    -------
    tuple[OpenAI, str]
        An OpenAI client and the resolved model name.
    """
    if model_id is None:
        return get_llm_config()

    from app.db import SessionLocal
    from app.models import LLMModel

    db = SessionLocal()
    try:
        model = db.query(LLMModel).filter(LLMModel.model_id == model_id).first()
        if model is None:
            logger.warning("LLMModel %s not found, falling back to default config", model_id)
            return get_llm_config()

        client, model_name = _build_client_from_model(model)
        return client, model_name
    except Exception as e:
        logger.warning("Failed to resolve model %s from DB: %s. Falling back.", model_id, e)
        return get_llm_config()
    finally:
        db.close()


def resolve_prompt_model(
    db: "Session",
    prompt_id: str,
    version: int | None,
) -> tuple[str | None, int | None]:
    """Resolve (model_name, model_id) for a prompt version.

    Returns (None, None) if no model is assigned or prompt not found.
    """
    from app.models import PromptVersion as PV

    pv = (
        db.query(PV)
        .filter(
            PV.prompt_id == prompt_id,
            PV.version == version,
        )
        .first()
    )
    if pv and pv.model_id:
        _, model_name = get_llm_config_by_model_id(pv.model_id)
        return model_name, pv.model_id
    return None, None


def get_llm_config_by_name(name: str) -> tuple[OpenAI, str]:
    """Resolve model config by the model's friendly name.

    Parameters
    ----------
    name : str
        The LLMModel.name to look up.

    Returns
    -------
    tuple[OpenAI, str]
        An OpenAI client and the resolved model name.
    """
    from app.db import SessionLocal
    from app.models import LLMModel

    db = SessionLocal()
    try:
        model = db.query(LLMModel).filter(LLMModel.name == name).first()
        if model is None:
            logger.warning("LLMModel '%s' not found, falling back to default config", name)
            return get_llm_config()

        client, model_name = _build_client_from_model(model)
        return client, model_name
    except Exception as e:
        logger.warning("Failed to resolve model '%s' from DB: %s. Falling back.", name, e)
        return get_llm_config()
    finally:
        db.close()


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

# ---------------------------------------------------------------------------
# Dataset caching — fetch once, reuse everywhere
# ---------------------------------------------------------------------------

_CACHED_DATASET: str | None = None
_DATASET_LOCK: threading.Lock = threading.Lock()


def _get_cached_dataset() -> str:
    """Return the pre-computed dataset string, computing it once on first call.

    Thread-safe with double-checked locking: the first call fetches from the
    database and serialises to CSV.  Every subsequent call returns the cached
    string instantly without touching the database.
    """
    global _CACHED_DATASET
    if _CACHED_DATASET is None:
        with _DATASET_LOCK:
            # Double-check inside lock in case another thread computed it
            if _CACHED_DATASET is None:
                rooms, guests = _fetch_raw_data()
                _CACHED_DATASET = _to_csv(rooms, guests)
    return _CACHED_DATASET


def dataset_refresh() -> str:
    """Force-refresh the cached dataset from the database.

    Call this after bulk data changes (e.g. population scripts, migrations).

    Returns:
        The freshly-computed CSV dataset string.
    """
    global _CACHED_DATASET
    with _DATASET_LOCK:
        rooms, guests = _fetch_raw_data()
        _CACHED_DATASET = _to_csv(rooms, guests)
    return _CACHED_DATASET


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


def query_guest_with_llm(
    customer_name: str,
    prompt_id: str = "guest-search",
    version: int | None = None,
    runtime_variables: dict[str, str] | None = None,
) -> tuple[str, bool]:
    """
    Query the LLM for all information about a given guest using tool calling.

    This function uses the tool calling loop to allow the LLM to query the database
    directly via tools like query_guests, query_reservations, etc.

    If prompt_id is provided, resolves the prompt template from the PromptStore.
    Falls back to hardcoded behavior if no prompt is found.

    The system prompt is composed from: intention + restrictions + output_structure
    The user message is composed from: user_prompt_template with {customer_name} replaced.

    The LLM client is resolved based on the prompt's model_id. If the prompt version
    has a model_id, that specific model is used. Otherwise, falls back to the first
    configured model in the database.

    Uses lazy import to avoid circular import with tool_calling module.

    Returns:
        A tuple of (llm_response, was_cached) where was_cached is True if the
        response was served from the cache.
    """
    from app.services.prompts import PromptStore
    from app.services.response_cache import call_llm_with_db_tools_with_cache_flag

    store = PromptStore()

    try:
        system_prompt_text, user_template = store.resolve_prompt(prompt_id, version)
        if system_prompt_text:
            # Use resolved prompt: combine stored system prompt with SHARED_SYSTEM_PROMPT
            # The stored intention may already contain the base system instructions
            final_system = system_prompt_text
        else:
            final_system = SHARED_SYSTEM_PROMPT

        # Build runtime variables from the customer_name.
        # The user_prompt_template may contain {table.field} placeholders that
        # need to be resolved at query-time.  By default we map the customer name
        # to the conventional "customers.first_name" and "customers.last_name"
        # keys, but the template author can use any keys they like.
        from app.services.placeholders import resolve_all_placeholders
        runtime_vars: dict[str, str] = {}

        # Split customer_name into first/last for common {table.field} patterns
        name_parts = customer_name.strip().split(None, 1)
        if len(name_parts) == 2:
            first, last = name_parts
            runtime_vars["customers.first_name"] = first
            runtime_vars["customers.last_name"] = last
            runtime_vars["customers.name"] = customer_name
        elif len(name_parts) == 1:
            runtime_vars["customers.first_name"] = name_parts[0]
            runtime_vars["customers.last_name"] = ""
            runtime_vars["customers.name"] = name_parts[0]
        else:
            runtime_vars["customers.first_name"] = ""
            runtime_vars["customers.last_name"] = ""
            runtime_vars["customers.name"] = customer_name

        # Merge user-provided runtime_variables (allow overrides from user input)
        if runtime_variables:
            runtime_vars.update(runtime_variables)

        user_prompt = resolve_all_placeholders(user_template, runtime_vars)
    except ValueError:
        # Prompt not found — fall back to legacy hardcoded behavior
        final_system = SHARED_SYSTEM_PROMPT
        user_prompt = (
            f"Please find all information about the guest named. "
            f"The guest's name can have it's name translated into the following languages "
            f"Arabic, Chinese, Devanagari, Japanese, Korean, Latin or Nordic. "
            f"It is unclear if is the user's first name or last name. "
            f"Retry once with every translated language if needed. "
            f"Also bring the information about its reservations. : {customer_name}"
        )

    # Resolve model from the prompt version
    model_name = None
    db = SessionLocal()
    try:
        model_name, _ = resolve_prompt_model(db, prompt_id, version)
        if model_name:
            logger.info(
                "query_guest_with_llm resolved model '%s' from prompt '%s' v%d",
                model_name, prompt_id, version or 'default',
            )
        else:
            logger.info(
                "query_guest_with_llm using default model (no model_id on prompt '%s' v%d)",
                prompt_id, version or 'default',
            )
    except Exception as e:
        logger.warning("Failed to resolve model for prompt '%s' v%d: %s", prompt_id, version, e)
    finally:
        db.close()
    
    try:
        result, was_cached = call_llm_with_db_tools_with_cache_flag(
            user_prompt,
            model=model_name,
            system_prompt=final_system,
        )
        
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
