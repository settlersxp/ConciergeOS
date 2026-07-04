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
from app.schemas import CreateModelRequest, DeleteModelResponse, LLMModelSchema, UpdateModelRequest
from app.utils.endpoints import normalize_models_endpoint

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/models", tags=["models"])


async def _fetch_remote_model_info(models_url: str) -> dict[str, Any]:
    """Fetch model info from an upstream vLLM endpoint.

    Returns a dict with keys: ok, model_name, vllm_version, thinking_enabled.
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(models_url)
        resp.raise_for_status()
        data = resp.json()

    # Parse — OpenAI-compatible: {"data": [{"id": "..."}]} or {"id": "..."}
    mname = data.get("id", "")
    if "data" in data and isinstance(data["data"], list) and data["data"]:
        mname = data["data"][0].get("id", mname)

    # Extract vLLM version from response headers
    vllm_version = None
    for header_name in ("x-vllm-version", "x-vllm-version-id"):
        if val := resp.headers.get(header_name):
            vllm_version = val
            break

    return {
        "ok": True,
        "model_name": mname,
        "vllm_version": vllm_version,
        "thinking_enabled": False,
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("", response_model=list[LLMModelSchema])
async def list_models(db: Session = Depends(get_db)):
    """List all registered LLM models."""
    from app.models import LLMModel

    models = db.query(LLMModel).order_by(LLMModel.name).all()
    result = [LLMModelSchema.model_validate(m) for m in models]
    logger.info(f"[LIST_MODELS] Returning {len(result)} model(s) from database")
    return result


@router.get("/{model_id}", response_model=LLMModelSchema)
async def get_model(model_id: int, db: Session = Depends(get_db)):
    """Get a single LLM model by ID."""
    from app.models import LLMModel

    model = db.query(LLMModel).filter(LLMModel.model_id == model_id).first()
    if model is None:
        raise HTTPException(status_code=404, detail=f"Model '{model_id}' not found.")
    return LLMModelSchema.model_validate(model)


@router.post("", response_model=LLMModelSchema, status_code=201)
async def create_model(body: CreateModelRequest, db: Session = Depends(get_db)):
    """Create a new LLM model.

    Expects JSON body with:
      name, endpoint, models_endpoint (optional), model_name,
      model_type (optional), vllm_version (optional), thinking_enabled (optional)
    """
    from app.models import LLMModel

    # Check for duplicate name (FastAPI validates required fields automatically)
    existing = db.query(LLMModel).filter(LLMModel.name == body.name).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Model with name '{body.name}' already exists.")

    model = LLMModel(
        name=body.name,
        endpoint=body.endpoint,
        models_endpoint=body.models_endpoint or "",
        model_name=body.model_name,
        model_type=body.model_type or "general",
        vllm_version=body.vllm_version,
        thinking_enabled=body.thinking_enabled or False,
    )
    db.add(model)
    db.commit()
    db.refresh(model)
    return LLMModelSchema.model_validate(model)


@router.put("/{model_id}", response_model=LLMModelSchema)
async def update_model(model_id: int, body: UpdateModelRequest, db: Session = Depends(get_db)):
    """Update an existing LLM model.

    All fields are optional — only provided fields will be updated.
    """
    from app.models import LLMModel

    model = db.query(LLMModel).filter(LLMModel.model_id == model_id).first()
    if model is None:
        raise HTTPException(status_code=404, detail=f"Model '{model_id}' not found.")

    # Check for duplicate name (excluding self)
    if body.name is not None:
        existing = db.query(LLMModel).filter(
            LLMModel.name == body.name,
            LLMModel.model_id != model_id,
        ).first()
        if existing:
            raise HTTPException(status_code=409, detail=f"Model with name '{body.name}' already exists.")

    update_data = body.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(model, key, value)

    db.commit()
    db.refresh(model)
    return LLMModelSchema.model_validate(model)


@router.delete("/{model_id}", response_model=DeleteModelResponse)
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
    return DeleteModelResponse(
        ok=True,
        model_id=model_id,
        message=f"Model '{model.name}' deleted successfully.",
    )


@router.post("/fetch-info")
async def fetch_info_by_url(body: dict):
    """Fetch live model info from a raw endpoint URL.

    Accepts a JSON body with:
      models_endpoint (optional) — the full /v1/models URL, or a base URL (e.g. /v1)
      endpoint (required if models_endpoint missing) — base URL, appends /v1/models
    """
    raw = body.get("models_endpoint") or body.get("endpoint") or ""
    if not raw.strip():
        raise HTTPException(
            status_code=400,
            detail="Either 'models_endpoint' or 'endpoint' must be provided in the request body.",
        )

    models_url = normalize_models_endpoint(raw)
    return await _fetch_remote_model_info(models_url)


@router.get("/{model_id}/info")
async def fetch_model_info(model_id: int, db: Session = Depends(get_db)):
    """Fetch live model info from the LLM endpoint.

    Hits the {models_endpoint} (or /v1/models) on the model's base URL
    to discover what the model actually reports.
    """
    from app.models import LLMModel

    model = db.query(LLMModel).filter(LLMModel.model_id == model_id).first()
    if model is None:
        raise HTTPException(status_code=404, detail=f"Model '{model_id}' not found.")

    models_url = normalize_models_endpoint(model.models_endpoint or model.endpoint)
    return await _fetch_remote_model_info(models_url)
