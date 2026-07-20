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
from app.services.response_cache import cache_stats, http_cache_stats, cache_clear, http_cache_clear

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
    """Test the LLM completion endpoint directly with tool calling.
    
    Uses response_cache wrapper for diagnostic logging. To enable:
    - Edit response_cache.py and set log_level="DEBUG" for verbose output
    - Set log_level="INFO" for summary diagnostics only
    """
    from app.services.response_cache import call_llm_with_db_tools
    
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


# ── Cache Management Endpoints ─────────────────────────────────────────────────


@debug_router.get("/cache-stats")
def get_cache_stats():
    """Return statistics for both LLM and HTTP response caches."""
    return {
        "llm_cache": cache_stats(),
        "http_cache": http_cache_stats(),
    }


@debug_router.post("/cache/clear-llm")
def clear_llm_cache():
    """Clear the LLM response cache."""
    count = cache_clear()
    return {"cleared": count, "cache": "llm"}


@debug_router.post("/cache/clear-http")
def clear_http_cache():
    """Clear the HTTP response cache."""
    count = http_cache_clear()
    return {"cleared": count, "cache": "http"}


@debug_router.post("/cache/clear-all")
def clear_all_caches():
    """Clear both LLM and HTTP response caches."""
    llm_count = cache_clear()
    http_count = http_cache_clear()
    return {
        "llm_cleared": llm_count,
        "http_cleared": http_count,
        "caches": "all",
    }


@debug_router.delete("/cache/http")
def delete_http_cache_entry(key: str):
    """
    Delete a specific HTTP cache entry by cache key.

    Query param: key=sha256hex...
    """
    from app.services.response_cache import _get_http_cache
    deleted = _get_http_cache().delete(key)
    return {"deleted": deleted, "key": key, "cache": "http"}


@debug_router.post("/cache/http/cleanup-expired")
def cleanup_expired_http_cache():
    """Remove all expired HTTP cache entries."""
    from app.services.response_cache import http_cache_cleanup_expired
    count = http_cache_cleanup_expired()
    return {"cleaned": count, "cache": "http"}


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
