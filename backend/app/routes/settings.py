#!/usr/bin/env python3
"""Settings management routes."""

from typing import Any

from dataclasses import asdict

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.config import config_manager, TestSettings

router = APIRouter()


@router.get("/api/settings")
async def api_get_settings() -> JSONResponse:
    """Get current global configuration settings."""
    return JSONResponse(content={"test_settings": asdict(config_manager.test_settings)})


@router.post("/api/settings")
async def api_update_settings(body: dict[str, Any]) -> JSONResponse:
    """Update global configuration settings."""
    try:
        ts_data = body.get("test_settings", {})
        if ts_data:
            new_ts = TestSettings(**ts_data)
            config_manager.test_settings = new_ts
        config_manager.save()
        return JSONResponse(content={"message": "Settings updated successfully"})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.get("/api/settings/models-info")
async def api_get_models_info() -> JSONResponse:
    """Proxy request to the configured vLLM models endpoint."""
    models_endpoint = config_manager.test_settings.models_endpoint
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(models_endpoint)
            resp.raise_for_status()
            return JSONResponse(content=resp.json())
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
