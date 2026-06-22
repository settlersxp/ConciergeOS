#!/usr/bin/env python3
"""
Performance testing for query_guest_with_llm().
Runs sequential and concurrent batches, logging results to a SQLite database.

Database initialization is decoupled into :mod:`PerformanceTesting.db` so the
testing logic can be used independently of storage concerns.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

# Add project root to path so we can import app modules
_PROJECT_ROOT = Path(__file__).parent.parent

# Import shared prompts from the single source of truth
from app.services.llm import (  # noqa: E402
    SYSTEM_PROMPT as DEFAULT_SYSTEM_PROMPT,
    SHARED_SYSTEM_PROMPT,
    TOOL_DEFINITIONS,
    build_user_prompt,
    fetch_all_as_json,
    fetch_all_as_xml,
    fetch_all_guests_and_reservations,
)

try:
    from .db import PerformanceTestLogger, ensure_database, get_next_run_id
except ImportError:
    # Fallback when run directly as a script (python -m or __main__)
    from PerformanceTesting.db import PerformanceTestLogger, ensure_database, get_next_run_id  # noqa: cwd


from app.config import config_manager

# ── Test settings ────────────────────────────────────────────────────────────

@dataclass
class TestSettings:
    """All configurable settings for a performance test run."""
    customer_name: str = "عائشة إبراهيم"
    vllm_url: str = ""  # Derived from models_endpoint if not provided
    models_endpoint: str = "http://localhost:8000/v1/models"
    database_path: Path = field(default_factory=lambda: Path(__file__).parent.parent / "performance_tests.db")
    sequential_batch_size: int = 5
    concurrent_batch_size: int = 8
    # Test mode: "single" (one guest for all tests) or "multi" (different guest per test)
    test_mode: str = "single"
    # Guest names for multi-guest mode (first N for sequential, remaining for concurrent)
    guest_names: List[str] = field(default_factory=list)
    # Batch identification
    batch_uuid: str = ""
    friendly_name: str = ""
    # Model metadata (auto-filled from vLLM API, but editable by user)
    model_name: str = ""
    vllm_version: str = ""
    thinking_enabled: bool = False
    # Prompt settings
    system_prompt: str = DEFAULT_SYSTEM_PROMPT
    user_prompt: str = ""  # If empty, auto-built from customer_name + DB data
    # Response format expectation
    expected_response_format: str = "auto"  # "json", "text", or "auto"
    # Data format: which file format to embed in the user prompt
    data_format: str = "csv"  # "csv", "json", "xml", or "tool_calling"
    # Tool calling support
    use_tool_calling: bool = False  # Whether to use function/tool calling instead of embedding data
    tool_definitions: List[Dict[str, Any]] = field(default_factory=list)  # Tool definitions to send to LLM


# ── Model info retrieval ────────────────────────────────────────────────────

def fetch_model_info(url: str) -> dict[str, Any]:
    """Fetch loaded model information from the vLLM /v1/models endpoint."""
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    data = resp.json()

    models: List[Dict[str, Any]] = data.get("data", [])
    if not models:
        return {"model_name": "unknown", "vllm_version": "unknown", "thinking_enabled": False}

    model: Dict[str, Any] = models[0]
    model_name: str = str(model.get("id", model.get("model", "unknown")))

    # Try to extract vllm version from various possible fields
    vllm_version: str = str(model.get("vllm_version", ""))
    if not vllm_version or vllm_version == "None":
        extra = model.get("extra")
        if isinstance(extra, dict):
            vllm_version = str(extra.get("vllm_version", "unknown"))
        else:
            vllm_version = "unknown"

    # Check if thinking is enabled
    thinking_enabled: bool = False
    capabilities = model.get("capabilities")
    if isinstance(capabilities, dict):
        thinking_enabled = bool(capabilities.get("thinking", False))
    
    model_type = str(model.get("type", "")).lower()
    if "thinking" in model_type:
        thinking_enabled = True

    return {
        "model_name": model_name,
        "vllm_version": vllm_version,
        "thinking_enabled": thinking_enabled,
    }


# ── LLM query wrapper ───────────────────────────────────────────────────────

def _build_user_prompt(customer_name: str, data_format: str = "csv") -> str:
    """Build the full user prompt with embedded DB data using the specified format."""
    if data_format == "json":
        data = fetch_all_as_json()
    elif data_format == "xml":
        data = fetch_all_as_xml()
    else:
        data = fetch_all_guests_and_reservations()
    return build_user_prompt(customer_name, data)


def _query_guest_with_llm(settings: TestSettings) -> str:
    """Query the LLM using the provided settings."""
    from openai import OpenAI

    client = OpenAI(
        base_url=settings.vllm_url,
        api_key="none",
    )

    model_name = settings.model_name or "Qwen/Qwen3.6-27B"
    
    # Determine the user prompt content
    if settings.use_tool_calling:
        # For tool calling mode, use a simple prompt - the tools handle the data fetching
        user_prompt = settings.user_prompt or f"Find all information about the customer named: {settings.customer_name}"
    else:
        user_prompt = settings.user_prompt or _build_user_prompt(settings.customer_name, settings.data_format)

    # For tool calling mode, use the unified system prompt that describes tools
    system_content = settings.system_prompt
    if settings.use_tool_calling:
        system_content = SHARED_SYSTEM_PROMPT
    
    # Build the API request
    api_messages = [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_prompt},
    ]
    
    # Prepare the API call parameters
    api_params: Dict[str, Any] = {
        "model": model_name,
        "messages": api_messages,
        "temperature": 0,
        "max_tokens": 4096,
    }
    
    # Add tools if tool calling is enabled and tool definitions are provided
    if settings.use_tool_calling and settings.tool_definitions:
        api_params["tools"] = settings.tool_definitions

    # If tool calling is enabled, use the dedicated tool calling loop
    if settings.use_tool_calling and settings.tool_definitions:
        return _execute_tool_calling_loop(client, api_messages, model_name, settings.tool_definitions)

    response = client.chat.completions.create(**api_params)

    return response.choices[0].message.content or "The LLM returned an empty response."


def _execute_tool_calling_loop(
    client: Any,
    messages: List[Dict[str, Any]],
    model_name: str,
    tool_definitions: List[Dict[str, Any]],
    max_turns: int = 10,
) -> str:
    """Execute the tool calling loop: send tools to LLM, execute returned function calls, repeat.
    
    This implements the multi-turn tool calling protocol:
    1. Send message with tools to LLM
    2. If LLM returns tool_calls, execute them and send results back
    3. Repeat until LLM responds with content (no tool calls) or max_turns reached
    """
    # Map of tool names to their executor functions
    # Import these here to avoid circular imports and use the same implementation
    import json
    from app.db import SessionLocal
    from app.models import Guest, Reservation, Room
    from app.enums import ReservationStatus
    
    def _format_guest(guest: Guest) -> dict:
        return {
            "guest_id": guest.guest_id,
            "first_name": guest.first_name,
            "last_name": guest.last_name,
            "date_of_birth": str(guest.date_of_birth) if guest.date_of_birth else "",
            "is_special_guest": guest.is_special_guest,
            "special_preferences": guest.special_preferences or "",
        }
    
    def _format_reservation(reservation: Reservation) -> dict:
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
    
    def _execute_query_guests(params: dict) -> str:
        db = SessionLocal()
        try:
            query = db.query(Guest)
            if "guest_id" in params and params["guest_id"] is not None:
                query = query.filter(Guest.guest_id == params["guest_id"])
            if "first_name" in params and params["first_name"]:
                query = query.filter(Guest.first_name.ilike(f"%{params['first_name']}%"))
            if "last_name" in params and params["last_name"]:
                query = query.filter(Guest.last_name.ilike(f"%{params['last_name']}%"))
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
    
    def _execute_query_rooms(params: dict) -> str:
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
    
    def _execute_query_reservations(params: dict) -> str:
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
    
    def _execute_get_hotel_summary(params: dict) -> str:
        db = SessionLocal()
        try:
            total_guests = db.query(Guest).count()
            total_rooms = db.query(Room).count()
            total_reservations = db.query(Reservation).count()
            status_counts = {}
            for status in ReservationStatus:
                count = db.query(Reservation).filter(Reservation.status == status).count()
                status_counts[status.value] = count
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
    
    TOOL_EXECUTORS = {
        "query_guests": _execute_query_guests,
        "query_rooms": _execute_query_rooms,
        "query_reservations": _execute_query_reservations,
        "get_hotel_summary": _execute_get_hotel_summary,
    }
    
    for turn in range(max_turns):
        # Call LLM with tools
        response = client.chat.completions.create(
            model=model_name,
            messages=messages,
            tools=tool_definitions,
            temperature=0.1,
            max_tokens=1024,
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


# ── Single request execution ────────────────────────────────────────────────

def run_single_request(
    batch_type: str,
    request_index: int,
    run_id: int,
    settings: TestSettings,
    logger: PerformanceTestLogger,
) -> dict[str, Any]:
    """Execute a single LLM query and log the result.

    Args:
        batch_type: Either ``"sequential"`` or ``"concurrent"``.
        request_index: 1-based index within the batch.
        run_id: The auto-incremented run identifier.
        settings: Configured test parameters.
        logger: Pluggable result logger (decoupled from storage).
    """
    # Resolve the user_prompt once (cache on settings for subsequent calls)
    # For tool calling mode, the user prompt is simpler
    if not settings.user_prompt:
        if settings.use_tool_calling:
            settings.user_prompt = f"Find all information about the customer named: {settings.customer_name}"
        else:
            settings.user_prompt = _build_user_prompt(settings.customer_name, settings.data_format)

    request_sent_time = datetime.now(timezone.utc).isoformat()
    response = _query_guest_with_llm(settings)
    response_received_time = datetime.now(timezone.utc).isoformat()

    logger.log(
        run_id=run_id,
        batch_uuid=settings.batch_uuid,
        friendly_name=settings.friendly_name,
        batch_type=batch_type,
        request_index=request_index,
        model_name=settings.model_name,
        vllm_version=settings.vllm_version,
        thinking_enabled=settings.thinking_enabled,
        system_prompt=settings.system_prompt,
        user_prompt=settings.user_prompt,
        expected_response_format=settings.expected_response_format,
        response=response,
        request_sent_time=request_sent_time,
        response_received_time=response_received_time,
    )

    elapsed = (
        datetime.fromisoformat(response_received_time)
        - datetime.fromisoformat(request_sent_time)
    ).total_seconds()

    return {
        "batch_type": batch_type,
        "request_index": request_index,
        "elapsed": round(elapsed, 2),
    }


# ── Batch runners ────────────────────────────────────────────────────────────

def run_sequential_batch(
    run_id: int,
    settings: TestSettings,
    logger: PerformanceTestLogger,
) -> list[dict[str, Any]]:
    """Run sequential requests back to back (single-guest mode)."""
    results: list[dict[str, Any]] = []
    for i in range(settings.sequential_batch_size):
        result = run_single_request("sequential", i + 1, run_id, settings, logger)
        results.append(result)
        print(f"  [sequential] Request {i + 1} completed in {result['elapsed']}s")
    return results


def run_concurrent_batch(
    run_id: int,
    settings: TestSettings,
    logger: PerformanceTestLogger,
) -> list[dict[str, Any]]:
    """Run concurrent requests simultaneously using threads (single-guest mode)."""
    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=settings.concurrent_batch_size) as executor:
        futures = {
            executor.submit(
                run_single_request, "concurrent", i + 1, run_id, settings, logger
            ): i + 1
            for i in range(settings.concurrent_batch_size)
        }
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            print(f"  [concurrent] Request {result['request_index']} completed in {result['elapsed']}s")
    return results


def run_single_request_with_guest(
    batch_type: str,
    request_index: int,
    run_id: int,
    settings: TestSettings,
    logger: PerformanceTestLogger,
    customer_name: str,
    user_prompt: str,
) -> dict[str, Any]:
    """Execute a single LLM query for a specific guest (used in multi-guest mode).

    Args:
        batch_type: Either ``"sequential"`` or ``"concurrent"``.
        request_index: 1-based index within the batch.
        run_id: The auto-incremented run identifier.
        settings: Configured test parameters.
        logger: Pluggable result logger.
        customer_name: The guest name for this specific request.
        user_prompt: Pre-built user prompt for this guest.
    """
    from openai import OpenAI

    client = OpenAI(
        base_url=settings.vllm_url,
        api_key="none",
    )

    model_name = settings.model_name or "Qwen/Qwen3.6-27B"

    # For tool calling mode, use the unified system prompt that describes tools
    system_content = settings.system_prompt
    if settings.use_tool_calling:
        system_content = SHARED_SYSTEM_PROMPT

    # Build the API request
    api_messages = [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_prompt},
    ]
    
    # Prepare the API call parameters
    api_params: Dict[str, Any] = {
        "model": model_name,
        "messages": api_messages,
        "temperature": 0,
        "max_tokens": 4096,
    }
    
    # Add tools if tool calling is enabled and tool definitions are provided
    if settings.use_tool_calling and settings.tool_definitions:
        api_params["tools"] = settings.tool_definitions

    request_sent_time = datetime.now(timezone.utc).isoformat()
    
    # If tool calling is enabled, use the tool calling loop
    if settings.use_tool_calling and settings.tool_definitions:
        response_text = _execute_tool_calling_loop(
            client, api_messages, model_name, settings.tool_definitions
        )
    else:
        response = client.chat.completions.create(**api_params)
        response_text = response.choices[0].message.content or "The LLM returned an empty response."
    
    response_received_time = datetime.now(timezone.utc).isoformat()

    logger.log(
        run_id=run_id,
        batch_uuid=settings.batch_uuid,
        friendly_name=settings.friendly_name,
        batch_type=batch_type,
        request_index=request_index,
        model_name=settings.model_name,
        vllm_version=settings.vllm_version,
        thinking_enabled=settings.thinking_enabled,
        system_prompt=settings.system_prompt,
        user_prompt=user_prompt,
        expected_response_format=settings.expected_response_format,
        response=response_text,
        request_sent_time=request_sent_time,
        response_received_time=response_received_time,
    )

    elapsed = (
        datetime.fromisoformat(response_received_time)
        - datetime.fromisoformat(request_sent_time)
    ).total_seconds()

    return {
        "batch_type": batch_type,
        "request_index": request_index,
        "elapsed": round(elapsed, 2),
        "customer_name": customer_name,
    }


def run_sequential_batch_multi_guest(
    run_id: int,
    settings: TestSettings,
    logger: PerformanceTestLogger,
    guest_names: List[str],
) -> List[Dict[str, Any]]:
    """Run sequential requests, each querying a different guest.

    Uses the first `sequential_batch_size` guests from the provided list.
    """
    results: list[dict[str, Any]] = []
    seq_count = settings.sequential_batch_size
    for i in range(seq_count):
        customer_name = guest_names[i] if i < len(guest_names) else guest_names[-1]
        user_prompt = _build_user_prompt(customer_name, settings.data_format)
        result = run_single_request_with_guest(
            "sequential", i + 1, run_id, settings, logger, customer_name, user_prompt
        )
        results.append(result)
        print(f"  [sequential] Request {i + 1} (guest: {customer_name}) completed in {result['elapsed']}s")
    return results


def run_concurrent_batch_multi_guest(
    run_id: int,
    settings: TestSettings,
    logger: PerformanceTestLogger,
    guest_names: List[str],
) -> List[Dict[str, Any]]:
    """Run concurrent requests, each querying a different guest.

    Uses guests starting at index `sequential_batch_size` (i.e., the guests
    assigned to the concurrent batch).
    """
    results: list[dict[str, Any]] = []
    conc_count = settings.concurrent_batch_size
    seq_count = settings.sequential_batch_size
    # Pre-build all user prompts for the concurrent guests (thread-safe since DB reads are independent)
    prompts: list[tuple[str, str]] = []
    for i in range(conc_count):
        guest_idx = seq_count + i
        customer_name = guest_names[guest_idx] if guest_idx < len(guest_names) else guest_names[-1]
        user_prompt = _build_user_prompt(customer_name, settings.data_format)
        prompts.append((customer_name, user_prompt))

    with ThreadPoolExecutor(max_workers=conc_count) as executor:
        futures = {
            executor.submit(
                run_single_request_with_guest,
                "concurrent", i + 1, run_id, settings, logger,
                prompts[i][0], prompts[i][1],
            ): i + 1
            for i in range(conc_count)
        }
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            print(f"  [concurrent] Request {result['request_index']} (guest: {result['customer_name']}) completed in {result['elapsed']}s")
    return results


# ── Public entry point ──────────────────────────────────────────────────────

def run_tests(settings: Optional[TestSettings] = None) -> dict[str, Any]:
    """
    Main entry point for running performance tests.
    Can be called from CLI or from the web API.

    The database schema is ensured before tests start, and a
    :class:`~PerformanceTesting.db.PerformanceTestLogger` is injected into
    the batch runners so the testing logic remains storage-agnostic.
    """
    if settings is None:
        settings = TestSettings()

    db_path = settings.database_path

    # Ensure database schema exists (decoupled init)
    ensure_database(db_path)

    # Fetch model info if not set by user
    if not settings.model_name:
        try:
            model_info = fetch_model_info(settings.models_endpoint)
            if not settings.model_name:
                settings.model_name = model_info.get("model_name", "unknown")
            if not settings.vllm_version:
                settings.vllm_version = model_info.get("vllm_version", "unknown")
            if not settings.thinking_enabled:
                settings.thinking_enabled = model_info.get("thinking_enabled", False)
        except Exception as e:
            print(f"Warning: Could not fetch model info: {e}")

    run_id = get_next_run_id(db_path)

    # Create the injected logger
    logger = PerformanceTestLogger(db_path=db_path)

    print("Performance Testing for query_guest_with_llm()")
    print(f"  Run ID: {run_id}")
    print(f"  Test Mode: {settings.test_mode}")
    print(f"  Customer: {settings.customer_name}")
    print(f"  Model: {settings.model_name}")
    print(f"  vLLM Version: {settings.vllm_version}")
    print(f"  Thinking Enabled: {settings.thinking_enabled}")
    print(f"  Data Format: {settings.data_format}")
    print(f"  Sequential: {settings.sequential_batch_size}, Concurrent: {settings.concurrent_batch_size}")
    print(f"  Database: {db_path}")

    # Run batches based on test mode
    if settings.test_mode == "multi" and settings.guest_names:
        guest_names = settings.guest_names
        print(f"  Multi-guest mode: {len(guest_names)} guests configured")
        print(f"  Sequential guests: {', '.join(guest_names[:settings.sequential_batch_size])}")
        print(f"  Concurrent guests: {', '.join(guest_names[settings.sequential_batch_size:settings.sequential_batch_size + settings.concurrent_batch_size])}")

        print(f"\n{'=' * 60}")
        print(f"Sequential Batch (Multi-Guest): {settings.sequential_batch_size} requests")
        print(f"{'=' * 60}")
        seq_results = run_sequential_batch_multi_guest(run_id, settings, logger, guest_names)

        print(f"\n{'=' * 60}")
        print(f"Concurrent Batch (Multi-Guest): {settings.concurrent_batch_size} requests")
        print(f"{'=' * 60}")
        conc_results = run_concurrent_batch_multi_guest(run_id, settings, logger, guest_names)
    else:
        # Default single-guest mode
        print(f"\n{'=' * 60}")
        print(f"Sequential Batch: {settings.sequential_batch_size} requests")
        print(f"{'=' * 60}")
        seq_results = run_sequential_batch(run_id, settings, logger)

        print(f"\n{'=' * 60}")
        print(f"Concurrent Batch: {settings.concurrent_batch_size} requests")
        print(f"{'=' * 60}")
        conc_results = run_concurrent_batch(run_id, settings, logger)

    print(f"\n{'=' * 60}")
    print("All tests completed.")
    print(f"{'=' * 60}")

    return {
        "run_id": run_id,
        "batch_uuid": settings.batch_uuid,
        "friendly_name": settings.friendly_name,
        "model_name": settings.model_name,
        "vllm_version": settings.vllm_version,
        "thinking_enabled": settings.thinking_enabled,
        "sequential_results": seq_results,
        "concurrent_results": conc_results,
        "total_requests": len(seq_results) + len(conc_results),
    }


# ── CLI entry point ─────────────────────────────────────────────────────────

def main() -> None:
    run_tests()


if __name__ == "__main__":
    main()