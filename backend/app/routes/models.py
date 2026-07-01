#!/usr/bin/env python3
"""
FastAPI router for LLM model CRUD operations.

Provides REST endpoints:
  GET    /api/models                         — List all registered LLM models
  GET    /api/models/{model_id}              — Get a single model by ID
  POST   /api/models                         — Create a new LLM model
  PUT    /api/models/{model_id}              — Update an existing LLM model
  DELETE /api/models/{model_id}              — Delete an LLM model
  GET    /api/models/{model_id}/info         — Fetch live model info from the endpoint
"""

import logging
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/models", tags=["models"])


def _model_to_schema(m: Any) -> dict[str, Any]:
    """Convert an LLMModel ORM object to a dict suitable for JSONResponse."""
    return {
        "model_id": m.model_id,
        "name": m.name,
        "endpoint": m.endpoint,
        "models_endpoint": m.models_endpoint,
        "model_name": m.model_name,
        "model_type": m.model_type,
        "vllm_version": m.vllm_version,
        "thinking_enabled": bool(m.thinking_enabled),
        "created_at": m.created_at.isoformat() if m.created_at else None,
        "updated_at": m.updated_at.isoformat() if m.updated_at else None,
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("")
async def list_models(db: Session = Depends(get_db)):
    """List all registered LLM models."""
    from app.models import LLMModel

    models = db.query(LLMModel).order_by(LLMModel.name).all()
    result = [_model_to_schema(m) for m in models]
    logger.info(f"[LIST_MODELS] Returning {len(result)} model(s) from database")
    return result


@router.get("/{model_id}")
async def get_model(model_id: int, db: Session = Depends(get_db)):
    """Get a single LLM model by ID."""
    from app.models import LLMModel

    model = db.query(LLMModel).filter(LLMModel.model_id == model_id).first()
    if model is None:
        raise HTTPException(status_code=404, detail=f"Model '{model_id}' not found.")
    return _model_to_schema(model)


@router.post("")
async def create_model(body: dict, db: Session = Depends(get_db)):
    """Create a new LLM model.

    Expects JSON body with:
      name, endpoint, models_endpoint (optional), model_name,
      model_type (optional), vllm_version (optional), thinking_enabled (optional)
    """
    from app.models import LLMModel

    # Validate required fields
    required_fields = ["name", "endpoint", "model_name"]
    for field in required_fields:
        if field not in body or not body[field]:
            raise HTTPException(status_code=400, detail=f"Missing required field: {field}")

    # Check for duplicate name
    existing = db.query(LLMModel).filter(LLMModel.name == body["name"]).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Model with name '{body['name']}' already exists.")

    model = LLMModel(
        name=body["name"],
        endpoint=body["endpoint"],
        models_endpoint=body.get("models_endpoint", ""),
        model_name=body["model_name"],
        model_type=body.get("model_type"),
        vllm_version=body.get("vllm_version"),
        thinking_enabled=body.get("thinking_enabled", False),
    )
    db.add(model)
    db.commit()
    db.refresh(model)
    return _model_to_schema(model)


@router.put("/{model_id}")
async def update_model(model_id: int, body: dict, db: Session = Depends(get_db)):
    """Update an existing LLM model.

    All fields are optional — only provided fields will be updated.
    """
    from app.models import LLMModel

    model = db.query(LLMModel).filter(LLMModel.model_id == model_id).first()
    if model is None:
        raise HTTPException(status_code=404, detail=f"Model '{model_id}' not found.")

    # Check for duplicate name (excluding self)
    if "name" in body and body["name"]:
        existing = db.query(LLMModel).filter(
            LLMModel.name == body["name"],
            LLMModel.model_id != model_id,
        ).first()
        if existing:
            raise HTTPException(status_code=409, detail=f"Model with name '{body['name']}' already exists.")

    update_fields = {
        "name": body.get("name", model.name),
        "endpoint": body.get("endpoint", model.endpoint),
        "models_endpoint": body.get("models_endpoint", model.models_endpoint),
        "model_name": body.get("model_name", model.model_name),
        "model_type": body.get("model_type", model.model_type),
        "vllm_version": body.get("vllm_version", model.vllm_version),
        "thinking_enabled": body.get("thinking_enabled", model.thinking_enabled),
    }
    for key, value in update_fields.items():
        setattr(model, key, value)

    db.commit()
    db.refresh(model)
    return _model_to_schema(model)


@router.delete("/{model_id}")
async def delete_model(model_id: int, db: Session = Depends(get_db)):
    """Delete an LLM model.

    Prevents deletion if the model is still referenced by any prompt version.
    """
    from app.models import LLMModel, PromptVersion

    model = db.query(LLMModel).filter(LLMModel.model_id == model_id).first()
    if model is None:
        raise HTTPException(status_code=404, detail=f"Model '{model_id}' not found.")

    # Check for references from prompt versions
    ref_count = db.query(PromptVersion).filter(PromptVersion.model_id == model_id).count()
    if ref_count > 0:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Cannot delete model '{model.name}': it is referenced by "
                f"{ref_count} prompt version(s). Assign a different model to "
                "those prompts first, or delete them."
            ),
        )

    db.delete(model)
    db.commit()
    return {
        "ok": True,
        "model_id": model_id,
        "message": f"Model '{model.name}' deleted successfully.",
    }


@router.post("/fetch-info")
async def fetch_info_by_url(body: dict):
    """Fetch live model info from a raw endpoint URL.

    Accepts a JSON body with:
      models_endpoint (optional) — the full /v1/models URL, or a base URL (e.g. /v1)
      endpoint (required if models_endpoint missing) — base URL, appends /v1/models

    If the provided URL does not end with "/v1/models", "/v1/models" is appended automatically.
    This lets users discover model info before saving a model to the database.
    """
    raw = (body.get("models_endpoint") or body.get("endpoint") or "").strip().rstrip("/")
    if not raw:
        raise HTTPException(
            status_code=400,
            detail="Either 'models_endpoint' or 'endpoint' must be provided in the request body.",
        )

    # Normalize to /v1/models endpoint:
    #   - If already ending with /v1/models -> use as-is
    #   - If ending with /v1 -> append /models
    #   - Otherwise -> append /v1/models
    if raw.endswith("/v1/models"):
        models_url = raw
    elif raw.endswith("/v1"):
        models_url = f"{raw}/models"
    else:
        models_url = f"{raw}/v1/models"

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(models_url)
        resp.raise_for_status()
        data = resp.json()

    # Parse the response — OpenAI-compatible format:
    # {"id": "model-id", "object": "model", ...}  or  {"data": [{"id": "..."}, ...]}
    if "data" in data and isinstance(data["data"], list) and data["data"]:
        first = data["data"][0]
        mname = first.get("id", "")
    else:
        mname = data.get("id", "")

    # Try to extract vLLM version from response headers
    vllm_version = None
    for header_name in ("x-vllm-version", "x-vllm-version-id"):
        val = resp.headers.get(header_name)
        if val:
            vllm_version = val
            break

    return {
        "ok": True,
        "model_name": mname,
        "vllm_version": vllm_version,
        "thinking_enabled": False,
    }


@router.get("/{model_id}/info")
async def fetch_model_info(model_id: int, db: Session = Depends(get_db)):
    """Fetch live model info from the LLM endpoint.

    Hits the {models_endpoint} (or /v1/models) on the model's base URL
    to discover what the model actually reports.  This lets users verify
    the model name and vLLM version before saving.
    """
    from app.models import LLMModel

    model = db.query(LLMModel).filter(LLMModel.model_id == model_id).first()
    if model is None:
        raise HTTPException(status_code=404, detail=f"Model '{model_id}' not found.")

    # Determine the models endpoint
    models_url = model.models_endpoint.strip().rstrip("/")
    if not models_url:
        base = model.endpoint.strip().rstrip("/")
        models_url = f"{base}/v1/models"

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(models_url)
        resp.raise_for_status()
        data = resp.json()

    # Parse the response — OpenAI-compatible format:
    # {"id": "model-id", "object": "model", ...}  or  {"data": [{"id": "..."}, ...]}
    if "data" in data and isinstance(data["data"], list) and data["data"]:
        first = data["data"][0]
        mname = first.get("id", model.model_name)
    else:
        mname = data.get("id", model.model_name)

    # Try to extract vLLM version from response headers
    vllm_version = None
    for header_name in ("x-vllm-version", "x-vllm-version-id"):
        val = resp.headers.get(header_name)
        if val:
            vllm_version = val
            break

    return {
        "ok": True,
        "model_name": mname,
        "vllm_version": vllm_version,
        "thinking_enabled": False,
    }