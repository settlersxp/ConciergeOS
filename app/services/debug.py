#!/usr/bin/env python3
"""
Debug endpoints for administrative / development operations.

These endpoints are prefixed with /debug and are not intended for
production use.
"""

from fastapi import APIRouter

from app.schemas import ShiftRequest, ShiftResponse
from Generator.shift_reservations import shift_reservations as _shift_reservations
from app.services.tool_calling import TOOL_DEFINITIONS, TOOL_EXECUTORS
from app.services.llm import get_llm_config, get_available_models, LLMModelInfo

debug_router = APIRouter(prefix="/debug", tags=["debug"])


@debug_router.get("/tool-calling-info")
def get_tool_calling_info():
    """Return information about available tools and LLM configuration for debugging."""
    client, model_name = get_llm_config()
    models = get_available_models()
    
    return {
        "configured_model": model_name,
        "available_models": [m.id for m in models],
        "available_tools": list(TOOL_EXECUTORS.keys()),
        "tool_definitions_count": len(TOOL_DEFINITIONS),
        "tool_details": [
            {
                "name": t["name"],
                "description": t.get("description", ""),
                "parameters": t.get("parameters", {}),
            }
            for t in TOOL_DEFINITIONS
        ],
    }


@debug_router.post("/test-tool-call")
def test_tool_call_endpoint(tool_name: str, params: dict):
    """Test a specific tool call directly to verify database connectivity."""
    if tool_name not in TOOL_EXECUTORS:
        return {
            "error": f"Tool '{tool_name}' not found. Available tools: {list(TOOL_EXECUTORS.keys())}"
        }
    
    try:
        result = TOOL_EXECUTORS[tool_name](params)
        return {
            "tool": tool_name,
            "params": params,
            "result": result,
            "success": True,
        }
    except Exception as e:
        return {
            "tool": tool_name,
            "params": params,
            "error": str(e),
            "success": False,
        }


@debug_router.post("/test-llm-completion")
def test_llm_completion_endpoint(user_message: str):
    """Test the LLM completion endpoint directly with tool calling."""
    from app.services.tool_calling import call_llm_with_db_tools
    
    try:
        result = call_llm_with_db_tools(user_message)
        return {
            "user_message": user_message,
            "response": result,
            "success": True,
        }
    except Exception as e:
        return {
            "user_message": user_message,
            "error": str(e),
            "success": False,
        }


@debug_router.post("/shift-reservations", response_model=ShiftResponse)
def shift_reservations_endpoint(body: ShiftRequest = ShiftRequest()) -> ShiftResponse:
    """
    Shift all reservation check_in and check_out dates by a given number
    of days (default: 1).

    Request body (optional):
        {"days": 3}   – shift forward by 3 days
        {"days": -2}  – shift backward by 2 days
    """
    result = _shift_reservations(body.days)
    return ShiftResponse.model_validate(result)
