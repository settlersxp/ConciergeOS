# LLM Model Management — Multi-Model Support with Prompt-Level Assignment

> **Purpose**: Step-by-step implementation guide for adding a fully dynamic LLM model management system. Users can configure any number of LLM models (text generation, image+audio, general) with friendly names, and assign each model to any prompt at the prompt version level.
> **Audience**: LLM agent capable of implementing the full feature from this document alone.
> **Last Updated**: 2026-01-07

---

## Table of Contents

1. [Overview](#1-overview)
2. [Problem Statement & Design Rationale](#2-problem-statement--design-rationale)
3. [Architecture & Data Model](#3-architecture--data-model)
4. [Dependency Graph](#4-dependency-graph)
5. [Phase 1: Backend Database Changes](#5-phase-1-backend-database-changes)
6. [Phase 2: Backend Schemas](#6-phase-2-backend-schemas)
7. [Phase 3: Backend Model CRUD Routes](#7-phase-3-backend-model-crud-routes)
8. [Phase 4: Backend LLM Routing (LLM Service)](#8-phase-4-backend-llm-routing)
9. [Phase 5: Backend Guest Extraction](#9-phase-5-backend-guest-extraction)
10. [Phase 6: Backend Response Cache](#10-phase-6-backend-response-cache)
11. [Phase 7: Backend Prompt Chain](#11-phase-7-backend-prompt-chain)
12. [Phase 8: Backend Performance Testing](#12-phase-8-backend-performance-testing)
13. [Phase 9: Backend Config Deprecation](#13-phase-9-backend-config-deprecation)
14. [Phase 10: Frontend Types](#14-phase-10-frontend-types)
15. [Phase 11: Frontend API Client](#15-phase-11-frontend-api-client)
16. [Phase 12: Frontend Settings Page](#16-phase-12-frontend-settings-page)
17. [Phase 13: Frontend ModelManager Component](#17-phase-13-frontend-modelmanager-component)
18. [Phase 14: Frontend Prompt UI](#18-phase-14-frontend-prompt-ui)
19. [Phase 15: Frontend Guest Search Integration](#19-phase-15-frontend-guest-search-integration)
20. [Phase 16: Frontend Prompt Settings Panel](#20-phase-16-frontend-prompt-settings-panel)
21. [Testing](#21-testing)
22. [Migration Notes](#22-migration-notes)
23. [Implementation Extensions & Deviations](#23-implementation-extensions--deviations)
    23.1 [LLMModel Table — Schema Deviations](#231-llmmodel-table--schema-deviations)
    23.2 [Schema Extensions](#232-schema-extensions)
    23.3 [Extended API Endpoints](#233-extended-api-endpoints)
    23.4 [Shared HTTP Transport for Connection Pooling](#234-shared-http-transport-for-connection-pooling)
    23.5 [Model Resolution Return Type Deviation](#235-model-resolution-return-type-deviation)
    23.6 [get_available_models() — Additional Function](#236-get_available_models--additional-function)
    23.7 [Response Cache — Model-Aware Caching & Diagnostics](#237-response-cache--model-aware-caching--diagnostics)
    23.8 [Guest Extraction — Model ID Support](#238-guest-extraction--model-id-support)
    23.9 [_get_base_client() URL Normalization](#239-_get_base_client-url-normalization)
    23.10 [Prompt Version model_id — ondelete SET NULL Behavior](#2310-prompt-version-model_id--ondelete-set-null-behavior)
24. [Appendix A: Complete File List](#appendix-a-complete-file-list)

---

## 1. Overview

The current application uses a single hardcoded model configuration from `backend/app/config.py` (`TestSettings` dataclass). Both the text-generation path (LLM queries, guest search) and the multimodal path (image/audio extraction) share the same `model_name` and `models_endpoint`.

This enhancement introduces:

1. **Dynamic Model Registry** — A new database table `LLMModels` that stores an unlimited number of LLM model configurations with friendly names.
2. **Prompt-Level Model Assignment** — Each `PromptVersion` references a model via a `model_id` foreign key, enabling per-prompt model selection.
3. **Model Capabilities** — Each model is tagged with a `model_type` ("text", "image_audio", "general") so users can find the right model for their use case.
4. **Settings UI Overhaul** — The Settings page becomes a model management hub where users can add, edit, and remove models.

---

## 2. Problem Statement & Design Rationale

### Current Limitations

- Only **one model** can be configured at a time.
- Users running separate vLLM instances for text and vision models have no way to use both simultaneously.
- The `TestSettings` dataclass in `config.py` hardcodes the model names, requiring code changes to add new models.
- There is no concept of model **capabilities** (text-only vs. multimodal).

### Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Database-backed model registry** | Models are now first-class entities. No config file changes needed to add a model. |
| **Foreign key from PromptVersion to LLMModels** | One-to-many: one model can serve many prompts. Prompt references a specific model instance. |
| **`model_type` capability tag** | Allows the system to auto-suggest the right model. Users still manually assign. |
| **Friendly `name` field** | Display names are human-readable ("Production Text Model"), while `model_name` is the actual model ID ("facebook/opt-125m"). |
| **Dual endpoints** | Each model stores both a base `endpoint` and `models_endpoint`, supporting configurations where these differ. |

---

## 3. Architecture & Data Model

### New Table: `LLMModels`

```python
class LLMModel(Base):
    """Maps to the llm_models table.

    Registry of all available LLM models. Each model has a friendly name,
    endpoint configuration, and capability type.
    """

    __tablename__ = "LLMModels"

    model_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)  # Friendly display name
    endpoint: Mapped[str] = mapped_column(String(500), nullable=False)  # Base URL (e.g. http://localhost:8000/v1)
    models_endpoint: Mapped[str] = mapped_column(String(500), nullable=False)  # /v1/models URL
    model_name: Mapped[str] = mapped_column(String(200), nullable=False)  # Actual model ID (e.g. "facebook/opt-125m")
    model_type: Mapped[str] = mapped_column(String(20), default="general", nullable=False, server_default="general")
    # "text" | "image_audio" | "general"
    vllm_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    thinking_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

### Modified Table: `PromptVersions`

Add `model_id` column:

```python
model_id: Mapped[int | None] = mapped_column(
    Integer,
    ForeignKey("LLMModels.model_id", ondelete="SET NULL"),
    nullable=True,
    default=None,
)
```

When `model_id` is NULL, the system falls back to the default model (read from the config or the first available model). This ensures backward compatibility during migration.

### Diagram

```
┌─────────────────┐       ┌─────────────────────────┐
│   LLMModels     │       │     PromptVersions      │
├─────────────────┤       ├─────────────────────────┤
│ model_id (PK)   │◄──────│ model_id (FK, nullable) │
│ name            │       │ prompt_id               │
│ endpoint        │       │ version                 │
│ models_endpoint │       │ name                    │
│ model_name      │       │ intention               │
│ model_type      │       │ restrictions            │
│ vllm_version    │       │ output_structure        │
│ thinking_enabled│       │ user_prompt_template    │
│ created_at      │       │ is_default              │
│ updated_at      │       │ meta_json               │
└─────────────────┘       │ created_at              │
                          │ updated_at              │
                          └─────────────────────────┘
```

---

## 4. Dependency Graph

```
Phase 1: Backend Database Changes (models.py + migration)
    |
    +-> Phase 2: Backend Schemas (schemas.py)
              |
              +-> Phase 3: Backend Model CRUD Routes (routes/models.py, main.py)
              |           |
              |           +-> Phase 4: Backend LLM Routing (services/llm.py)
              |                     |
              |                     +-> Phase 5: Backend Guest Extraction (services/guest_extraction.py)
              |                     |
              |                     +-> Phase 6: Backend Response Cache (services/response_cache.py)
              |                     |
              |                     +-> Phase 7: Backend Prompt Chain (services/prompt_chain.py)
              |                     |
              |                     +-> Phase 8: Backend Performance Testing (settings.py, routes/perf testing.py)
              |                     |
              |                     +-> Phase 9: Backend Config Deprecation (config.py)
              |                     |
              |                     +-> Phase 10: Frontend Types (types/index.ts)
              |                     |
              |                     +-> Phase 11: Frontend API Client (services/api.ts)
              |                     |
              |                     +-> Phase 12: Frontend Settings (pages/Settings.tsx)
              |                     |
              |                     +-> Phase 13: Frontend ModelManager (components/ui/ModelManager.tsx)
              |                     |
              |                     +-> Phase 14: Frontend Prompt UI (PromptSelector.tsx)
              |                     |
              |                     +-> Phase 15: Frontend Guest Search (pages/GuestSearch.tsx)
              |                     |
              |                     +-> Phase 16: Frontend Prompt Settings Panel (PromptSettingsPanel.tsx)
              |
              +-> Phase 17: Frontend CreatePromptModal (CreatePromptModal.tsx)
```

Each phase must be completed in order. Phases within the same level can be worked on in parallel once their dependencies are met.

---

## 5. Phase 1: Backend Database Changes

### 5.1 Add `LLMModel` to `backend/app/models.py`

Append after the existing `PromptGroupResult` model:

```python
# ---------------------------------------------------------------------------
# LLM Model management (stored in hotel.db)
# ---------------------------------------------------------------------------

class LLMModel(Base):
    """Maps to the llm_models table.

    Registry of all available LLM models. Each model has a friendly name,
    endpoint configuration, and capability type.
    """

    __tablename__ = "LLMModels"

    model_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    endpoint: Mapped[str] = mapped_column(String(500), nullable=False)
    models_endpoint: Mapped[str] = mapped_column(String(500), nullable=False)
    model_name: Mapped[str] = mapped_column(String(200), nullable=False)
    model_type: Mapped[str] = mapped_column(String(20), default="general", nullable=False, server_default="general")
    vllm_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    thinking_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

### 5.2 Add `model_id` to `PromptVersion` in `backend/app/models.py`

Add to the `PromptVersion` class, after `meta_json`:

```python
    model_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("LLMModels.model_id", ondelete="SET NULL"),
        nullable=True,
        default=None,
    )
```

### 5.3 Create Alembic Migration

After modifying `models.py`, create a migration:

```bash
cd backend && uv run alembic revision --autogenerate -m "Add LLMModels table and model_id to PromptVersions"
```

Verify the generated migration:

```python
# In the migration file, ensure these operations exist:
def upgrade():
    op.create_table(
        'llm_models',
        sa.Column('model_id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('endpoint', sa.String(500), nullable=False),
        sa.Column('models_endpoint', sa.String(500), nullable=False),
        sa.Column('model_name', sa.String(200), nullable=False),
        sa.Column('model_type', sa.String(20), server_default='general', nullable=False),
        sa.Column('vllm_version', sa.String(50), nullable=True),
        sa.Column('thinking_enabled', sa.Boolean(), default=False),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.add_column('prompt_versions', sa.Column('model_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_prompt_versions_model_id', 'prompt_versions', 'llm_models', ['model_id'], ['model_id'], ondelete='SET NULL')

def downgrade():
    op.drop_constraint('fk_prompt_versions_model_id', 'prompt_versions', type_='foreignkey')
    op.drop_column('prompt_versions', 'model_id')
    op.drop_table('llm_models')
```

### 5.4 Run Migration

```bash
cd backend && uv run alembic upgrade head
```

---

## 6. Phase 2: Backend Schemas

**File**: `backend/app/schemas.py`

### 6.1 Add LLMModel Schemas

Append after the existing `PromptGroupSchema` section (near line 520):

```python
# ---------------------------------------------------------------------------
# LLM Model schemas
# ---------------------------------------------------------------------------

class LLMModelSchema(BaseModel):
    """Output schema for an LLM model."""

    model_id: int
    name: str
    endpoint: str
    models_endpoint: str
    model_name: str
    model_type: str
    vllm_version: str | None = None
    thinking_enabled: bool
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}


class CreateModelRequest(BaseModel):
    """Request body for creating a new LLM model."""

    name: str = Field(..., description="Friendly display name for the model")
    endpoint: str = Field(..., description="Base URL (e.g. http://localhost:8000/v1)")
    models_endpoint: str = Field(..., description="Models endpoint URL (e.g. http://localhost:8000/v1/models)")
    model_name: str = Field(..., description="Actual model ID (e.g. facebook/opt-125m)")
    model_type: str = Field(default="general", description="Model capability: text, image_audio, or general")
    vllm_version: str | None = None
    thinking_enabled: bool = False


class UpdateModelRequest(BaseModel):
    """Request body for updating an existing LLM model."""

    name: str | None = None
    endpoint: str | None = None
    models_endpoint: str | None = None
    model_name: str | None = None
    model_type: str | None = None
    vllm_version: str | None = None
    thinking_enabled: bool | None = None


class DeleteModelResponse(BaseModel):
    """Response from the delete-model endpoint."""

    ok: bool = True
    model_id: int | None = None
    message: str | None = None
    error: str | None = None


class ModelInfoResponse(BaseModel):
    """Response from fetching live model info from the endpoint."""

    ok: bool = True
    model_name: str | None = None
    vllm_version: str | None = None
    thinking_enabled: bool | None = None
    error: str | None = None
```

### 6.2 Update Prompt Schemas

Add `model_id` to `PromptVersionSchema`:

```python
class PromptVersionSchema(BaseModel):
    id: int
    prompt_id: str
    version: int
    name: str
    intention: str
    restrictions: str
    output_structure: str
    user_prompt_template: str
    model_id: int | None = None  # NEW
    is_default: bool
    metadata: dict | None = None
    created_at: str
    updated_at: str
    # ... rest unchanged
```

Add `model_id` to `CreatePromptRequest`:

```python
class CreatePromptRequest(BaseModel):
    name: str
    intention: str
    restrictions: str
    output_structure: str
    user_prompt_template: str
    metadata: dict | None = None
    model_id: int | None = None  # NEW
```

Add `model_id` to `UpdatePromptRequest`:

```python
class UpdatePromptRequest(BaseModel):
    name: str | None = None
    intention: str | None = None
    restrictions: str | None = None
    output_structure: str | None = None
    user_prompt_template: str | None = None
    metadata: dict | None = None
    model_id: int | None = None  # NEW
```

---

## 7. Phase 3: Backend Model CRUD Routes

### 7.1 Create `backend/app/routes/models.py`

```python
#!/usr/bin/env python3
"""LLM model management routes."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import LLMModel, PromptVersion
from app.schemas import (
    CreateModelRequest,
    DeleteModelResponse,
    LLMModelSchema,
    UpdateModelRequest,
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/api/models", response_model=list[LLMModelSchema])
async def api_get_models(db: Session = Depends(get_db)):
    """List all configured LLM models."""
    models = db.query(LLMModel).order_by(LLMModel.name).all()
    return [LLMModelSchema.model_validate(m) for m in models]


@router.get("/api/models/{model_id}", response_model=LLMModelSchema)
async def api_get_model(model_id: int, db: Session = Depends(get_db)):
    """Get a specific LLM model by ID."""
    model = db.query(LLMModel).filter(LLMModel.model_id == model_id).first()
    if not model:
        raise HTTPException(status_code=404, detail=f"Model {model_id} not found")
    return LLMModelSchema.model_validate(model)


@router.post("/api/models", response_model=LLMModelSchema, status_code=201)
async def api_create_model(body: CreateModelRequest, db: Session = Depends(get_db)):
    """Create a new LLM model configuration."""
    # Check for duplicate name
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
        thinking_enabled=body.thinking_enabled,
    )
    db.add(model)
    db.commit()
    db.refresh(model)
    return LLMModelSchema.model_validate(model)


@router.put("/api/models/{model_id}", response_model=LLMModelSchema)
async def api_update_model(
    model_id: int, body: UpdateModelRequest, db: Session = Depends(get_db)
):
    """Update an existing LLM model configuration."""
    model = db.query(LLMModel).filter(LLMModel.model_id == model_id).first()
    if not model:
        raise HTTPException(status_code=404, detail=f"Model {model_id} not found")

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


@router.delete("/api/models/{model_id}", response_model=DeleteModelResponse)
async def api_delete_model(model_id: int, db: Session = Depends(get_db)):
    """Delete an LLM model configuration."""
    model = db.query(LLMModel).filter(LLMModel.model_id == model_id).first()
    if not model:
        raise HTTPException(status_code=404, detail=f"Model {model_id} not found")

    # Check if any prompts reference this model
    prompt_count = (
        db.query(PromptVersion)
        .filter(PromptVersion.model_id == model_id)
        .count()
    )
    if prompt_count > 0:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Cannot delete model '{model.name}': it is referenced by "
                f"{prompt_count} prompt version(s). Assign a different model to "
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


@router.post("/api/models/fetch-info")
async def api_fetch_model_info(
    models_endpoint: str,
    db: Session = Depends(get_db),
):
    """Fetch model info from a vLLM endpoint to auto-populate fields."""
    try:
        import httpx

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(models_endpoint)
            resp.raise_for_status()
            data = resp.json()

        models = data.get("data", [])
        if not models:
            raise HTTPException(status_code=400, detail="No models found at endpoint")

        m = models[0]
        model_name = m.get("id") or m.get("model") or "unknown"

        version = m.get("vllm_version") or ""
        if not version and m.get("extra") and isinstance(m["extra"], dict):
            version = m["extra"].get("vllm_version") or ""

        thinking = m.get("capabilities")
        if thinking and isinstance(thinking, dict):
            thinking = thinking.get("thinking", False)
        mtype = str(m.get("type", ""))
        if "thinking" in mtype.lower():
            thinking = True

        return {
            "model_name": model_name,
            "vllm_version": version or "unknown",
            "thinking_enabled": bool(thinking),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch model info: {e}")
```

### 7.2 Register the Router

**File**: `backend/app/main.py`

Add the import (near the top with other route imports):

```python
from app.routes import models as models_router
```

Register the router (after existing router registrations):

```python
app.include_router(models_router.router, tags=["LLM Models"])
```

---

## 8. Phase 4: Backend LLM Routing

### 8.1 Replace Config-Based Lookup with DB-Based Lookup

**File**: `backend/app/services/llm.py`

Add import at top of file:

```python
from app.models import LLMModel
```

### 8.1.1 `get_llm_config_by_model_id()`

Add a new function after `get_available_models()`:

```python
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

        # Build client using shared transport
        base_url = strip_to_base_url(model.endpoint)
        shared_client = _get_shared_http_client()
        client = OpenAI(
            http_client=shared_client,
            base_url=base_url,
            api_key="none",
        )
        return client, model.model_name
    except Exception as e:
        logger.warning("Failed to resolve model %s from DB: %s. Falling back.", model_id, e)
        return get_llm_config()
    finally:
        db.close()
```

### 8.1.2 `get_llm_config_by_name()`

```python
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

        base_url = strip_to_base_url(model.endpoint)
        shared_client = _get_shared_http_client()
        client = OpenAI(
            http_client=shared_client,
            base_url=base_url,
            api_key="none",
        )
        return client, model.model_name
    except Exception as e:
        logger.warning("Failed to resolve model '%s' from DB: %s. Falling back.", name, e)
        return get_llm_config()
    finally:
        db.close()
```

### 8.2 Update `query_guest_with_llm()`

In the `query_guest_with_llm()` function, after the prompt is resolved, use `model_id` to get the client:

```python
def query_guest_with_llm(
    customer_name: str,
    prompt_id: str = "guest-search",
    version: int | None = None,
    runtime_variables: dict[str, str] | None = None,
) -> tuple[str, bool]:
    """Query the LLM for all information about a given guest using tool calling.

    The system prompt is resolved from the prompt store. The LLM client is
    selected based on the prompt's model_id.
    """
    from app.services.prompts import PromptStore
    from app.services.response_cache import call_llm_with_db_tools_with_cache_flag

    store = PromptStore()

    try:
        system_prompt_text, user_template = store.resolve_prompt(prompt_id, version)
        if system_prompt_text:
            final_system = system_prompt_text
        else:
            final_system = SHARED_SYSTEM_PROMPT
        # ... existing placeholder resolution logic ...

        # Resolve model from the prompt version
        db = SessionLocal()
        try:
            pv = (
                db.query(PromptVersion)
                .filter(
                    PromptVersion.prompt_id == prompt_id,
                    PromptVersion.version == version,
                )
                .first()
            )
            if pv and pv.model_id:
                client, model_name = get_llm_config_by_model_id(pv.model_id)
            else:
                # Fall back to first configured model
                client, model_name = get_llm_config_by_name("default")
        finally:
            db.close()

        # Use the resolved client for the LLM call
        result, was_cached = call_llm_with_db_tools_with_cache_flag(
            user_prompt,
            model=model_name,
            system_prompt=final_system,
        )
        return result, was_cached

    except Exception as e:
        logger.error(f"Error in query_guest_with_llm for {customer_name}: {str(e)}", exc_info=True)
        return f"Error querying guest information: {str(e)}", False
```

---

## 9. Phase 5: Backend Guest Extraction

### 9.1 Update `backend/app/services/guest_extraction.py`

The `_get_client_and_model()` function now accepts an optional `model_id`:

```python
def _get_client_and_model(model_id: int | None = None) -> tuple[OpenAI, str]:
    """
    Create an OpenAI client and return it along with the configured model name.

    If model_id is provided, looks up the model from the LLMModels table.
    Otherwise falls back to the config.json settings.
    """
    if model_id is not None:
        client, model_name = get_llm_config_by_model_id(model_id)
        logger.info("Using model '%s' (DB model_id=%s) for extraction", model_name, model_id)
        return client, model_name

    # Build a minimal model-like object for _build_client_from_model
    class _ConfigModel:
        endpoint: str = config_manager.test_settings.models_endpoint
        model_name: str = config_manager.test_settings.model_name

    config_model = _ConfigModel()
    client, model_name = _build_client_from_model(config_model)
    logger.info("Using model '%s' at base URL '%s' for extraction", model_name, config_model.endpoint)
    return client, model_name
```

### 9.2 Update `backend/app/routes/guest_search.py`

Add `model_id` parameter to the extract-name endpoint:

```python
@router.post("/api/guest-search/extract-name", response_model=NameExtractionResponse)
async def api_extract_name(
    file: UploadFile,
    crop_x: float = Form(0.0),
    crop_y: float = Form(0.0),
    crop_w: float = Form(0.0),
    crop_h: float = Form(0.0),
    model_id: int | None = Form(None),  # NEW: optional model reference
) -> NameExtractionResponse:
    """Extract a guest name from a multimedia file.

    If model_id is provided, uses that specific model.
    Otherwise, falls back to the default configured model.
    """
    file_bytes = await file.read()
    content_type = file.content_type or ""

    if "audio" in content_type:
        extracted_name = extract_name_from_audio(
            file_bytes, audio_format=ext or "webm", model_id=model_id
        )
        return NameExtractionResponse(extracted_name=extracted_name, source="audio")

    elif "image" in content_type:
        has_crop = crop_w > 0 and crop_h > 0
        if has_crop:
            image_bytes = crop_image(file_bytes, crop_x, crop_y, crop_w, crop_h)
        else:
            image_bytes = file_bytes

        extracted_name = extract_name_from_image(
            image_bytes, cropped=has_crop, model_id=model_id
        )
        return NameExtractionResponse(extracted_name=extracted_name, source="image")
```

---

## 10. Phase 6: Backend Response Cache

### 10.1 Current Cache Implementation

**File**: `backend/app/services/response_cache.py`

The current cache uses a simple SHA256 hash of the input text as the cache key. Note: model-aware caching (including model name in the cache key) has **not** been implemented yet — this is a known limitation that could cause cross-model cache pollution.

```python
def generate_cache_key(data: str) -> str:
    """Generate a SHA256 cache key from the input string.

    Normalizes the input (lowercase, trimmed) before hashing.
    """
    normalized = data.strip().lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
```

### 10.2 CacheStore with Statistics

The `CacheStore` class includes hit/miss tracking:

```python
class CacheStore:
    def __init__(self, ttl: int = 3600):
        self._store: dict[str, CacheEntry[str]] = {}
        self._ttl = ttl
        self._hits = 0
        self._misses = 0

    @property
    def stats(self) -> dict[str, int]:
        return {"hits": self._hits, "misses": self._misses, "size": len(self._store)}
```

### 10.3 HTTP Response Cache (Enhancement)

An additional `HttpCacheStore` caches HTTP GET responses by URI:

```python
class HttpCacheStore:
    """In-memory HTTP response cache with TTL-based expiration."""
```

---

## 11. Phase 7: Backend Prompt Chain

### 11.1 Model Resolution per Step

In `backend/app/services/prompt_chain.py`, each step in the chain resolves its own model:

```python
for item in items:
    # Resolve model_id for this prompt version
    from app.models import PromptVersion as PV
    pv = session_manager.query(PV).filter(
        PV.prompt_id == item.prompt_id,
        PV.version == item.prompt_version,
    ).first()
    model_id_val = pv.model_id if pv else None

    # Call LLM with resolved model
    from app.services.llm import get_llm_config_by_model_id
    client, model_name = get_llm_config_by_model_id(model_id_val)
    llm_response, was_cached = call_llm_with_db_tools_with_cache_flag(
        user_message,
        system_prompt=system_prompt,
    )
```

---

## 12. Phase 8: Backend Performance Testing

### 12.1 Model Resolution in Performance Testing

In `backend/app/routes/performance_testing.py`, the prompt template and model are resolved from the database:

```python
if prompt_id and prompt_version:
    db = SessionLocal()
    try:
        pv = (
            db.query(PromptVersion)
            .filter(
                PromptVersion.prompt_id == prompt_id,
                PromptVersion.version == prompt_version,
            )
            .first()
        )
        if pv:
            user_prompt = pv.user_prompt_template or user_prompt
            system_prompt = "\n\n".join(
                part for part in (pv.intention, pv.restrictions, pv.output_structure) if part
            )
            # Resolve model from prompt version
            if pv.model_id:
                from app.services.llm import get_llm_config_by_model_id
                _, resolved_model_name = get_llm_config_by_model_id(pv.model_id)
    finally:
        db.close()

model_name = resolved_model_name if resolved_model_name else body.model_name
```

The `_DATABASE_PATH` is resolved dynamically:

```python
_DATABASE_PATH = Path(__file__).resolve().parent.parent / "database.db"
```

---

## 13. Phase 9: Backend Config Deprecation

### 13.1 Current State of `backend/app/config.py`

The `TestSettings` dataclass is **still in use** and serves as the fallback for models without a database entry. It is **not yet deprecated** — code paths that cannot find a model in the database fall back to `config_manager.test_settings`:

```python
@dataclass
class TestSettings:
    """Configuration settings for LLM model configuration."""
    models_endpoint: str = "http://localhost:8000/v1/models"
    model_name: str = "facebook/opt-125m"
    vllm_version: str = ""
    thinking_enabled: bool = False
    expected_format: str = "auto"
```

> **Note**: A deprecation notice and transition to fully DB-based configuration is planned for a future phase.

---

## 14. Phase 10: Frontend Types

### 14.1 Add `LLMModel` Type

**File**: `frontend/src/types/index.ts`

Add before the existing `/** Performance Testing */` section:

```typescript
/** LLM Model Management */

export type ModelType = "text" | "image_audio" | "general";

export interface LLMModel {
  model_id: number;
  name: string;
  endpoint: string;
  models_endpoint: string;
  model_name: string;
  model_type: ModelType;
  vllm_version: string | null;
  thinking_enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface CreateModelRequest {
  name: string;
  endpoint: string;
  models_endpoint: string;
  model_name: string;
  model_type?: ModelType;
  vllm_version?: string;
  thinking_enabled?: boolean;
}

export interface UpdateModelRequest {
  name?: string;
  endpoint?: string;
  models_endpoint?: string;
  model_name?: string;
  model_type?: ModelType;
  vllm_version?: string;
  thinking_enabled?: boolean;
}

export interface ModelInfoResponse {
  model_name: string;
  vllm_version: string;
  thinking_enabled: boolean;
}
```

### 14.2 Update Prompt Types

Add `model_id` to all prompt-related types. In `frontend/src/types/index.ts`, update the `PromptVersion` interface:

```typescript
model_id: number | null;
```

---

## 15. Phase 11: Frontend API Client

### 15.1 Add Model CRUD Methods

**File**: `frontend/src/services/api.ts`

Add imports:

```typescript
import type { LLMModel, CreateModelRequest, UpdateModelRequest, ModelInfoResponse } from '../types';
```

Add a new `modelsApi` object:

```typescript
export const modelsApi = {
  getAll: () => request<LLMModel[]>('/api/models'),

  getById: (modelId: number) =>
    request<LLMModel>(`/api/models/${modelId}`),

  create: (payload: CreateModelRequest) =>
    request<LLMModel>('/api/models', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  update: (modelId: number, payload: UpdateModelRequest) =>
    request<LLMModel>(`/api/models/${modelId}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    }),

  delete: (modelId: number) =>
    request<{ ok: boolean }>(`/api/models/${modelId}`, {
      method: 'DELETE',
    }),

  fetchInfo: (modelsEndpoint: string) =>
    request<ModelInfoResponse>('/api/models/fetch-info', {
      method: 'POST',
      body: JSON.stringify({ models_endpoint: modelsEndpoint }),
    }),
};
```

### 15.2 Update `promptsApi.ts`

**File**: `frontend/src/services/promptsApi.ts`

Pass `model_id` in create and update calls. Find the `create` and `update` methods and ensure `model_id` is included:

```typescript
// In create method:
body: JSON.stringify({
  name,
  intention,
  restrictions,
  output_structure,
  user_prompt_template,
  model_id: modelId,
}),

// In update method:
body: JSON.stringify({
  name,
  intention,
  restrictions,
  output_structure,
  user_prompt_template,
  model_id,
}),
```

---

## 16. Phase 12: Frontend Settings Page

### 16.1 Redesign Settings as Model Management Hub

**File**: `frontend/src/pages/Settings.tsx`

The Settings page is completely redesigned to show a list of configured LLM models with add/edit/delete capabilities.

### 16.2 Implementation Approach

```typescript
import { useEffect, useState } from 'react';
import { modelsApi } from '../services/api';
import type { LLMModel } from '../types';
import { PageHeader, Card, FormField, Input, Button, Toast, Select } from '../components/ui';
import ModelManager from '../components/ui/ModelManager';

export default function Settings() {
  const [models, setModels] = useState<LLMModel[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingModel, setEditingModel] = useState<LLMModel | null>(null);
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' | 'info' } | null>(null);

  useEffect(() => {
    loadModels();
  }, []);

  const loadModels = async () => {
    setLoading(true);
    try {
      const data = await modelsApi.getAll();
      setModels(data);
    } catch (err) {
      setToast({ message: err instanceof Error ? err.message : 'Failed to load models', type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  const handleAdd = () => {
    setEditingModel(null);
    setModalOpen(true);
  };

  const handleEdit = (model: LLMModel) => {
    setEditingModel(model);
    setModalOpen(true);
  };

  const handleDelete = async (modelId: number) => {
    if (!confirm('Delete this model?')) return;
    try {
      await modelsApi.delete(modelId);
      await loadModels();
      setToast({ message: 'Model deleted', type: 'success' });
    } catch (err) {
      setToast({ message: err instanceof Error ? err.message : 'Delete failed', type: 'error' });
    }
  };

  return (
    <div className="mx-auto max-w-5xl px-4 py-8">
      <PageHeader
        title="LLM Models"
        description="Manage your configured LLM models. Each model can be assigned to one or more prompts."
      />

      <Card title="Configured Models" className="mb-6">
        <div className="mt-4 flex justify-end">
          <Button variant="primary" onClick={handleAdd}>
            + Add Model
          </Button>
        </div>

        {loading ? (
          <div className="mt-4 text-sm text-primary-500">Loading models...</div>
        ) : models.length === 0 ? (
          <div className="mt-4 text-sm text-primary-500">
            No models configured. Click "Add Model" to get started.
          </div>
        ) : (
          <div className="mt-4 space-y-3">
            {models.map((model) => (
              <ModelCard
                key={model.model_id}
                model={model}
                onEdit={() => handleEdit(model)}
                onDelete={() => handleDelete(model.model_id)}
              />
            ))}
          </div>
        )}
      </Card>

      {toast && (
        <Toast message={toast.message} type={toast.type} onHidden={() => setToast(null)} />
      )}

      <ModelManager
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        model={editingModel}
        onSave={async () => {
          await loadModels();
          setModalOpen(false);
        }}
      />
    </div>
  );
}
```

### 16.3 Model Card Component (inline or extract)

```tsx
function ModelCard({ model, onEdit, onDelete }: { model: LLMModel; onEdit: () => void; onDelete: () => void }) {
  const typeColors: Record<string, string> = {
    text: 'bg-blue-100 text-blue-800',
    image_audio: 'bg-green-100 text-green-800',
    general: 'bg-gray-100 text-gray-800',
  };

  return (
    <div className="flex items-center justify-between rounded-lg border border-primary-200 dark:border-primary-700 p-4 hover:border-primary-400">
      <div className="flex-1">
        <div className="flex items-center gap-2">
          <h3 className="font-medium text-primary-900 dark:text-white">{model.name}</h3>
          <span className={`rounded-full px-2 py-0.5 text-xs ${typeColors[model.model_type] || typeColors.general}`}>
            {model.model_type.replace('_', ' ')}
          </span>
          {model.thinking_enabled && (
            <span className="rounded-full bg-purple-100 text-purple-800 px-2 py-0.5 text-xs">
              Thinking
            </span>
          )}
        </div>
        <p className="mt-1 text-xs text-primary-500 dark:text-primary-400">
          Model: <code>{model.model_name}</code>
        </p>
        <p className="text-xs text-primary-400 dark:text-primary-500">
          Endpoint: <code className="break-all">{model.endpoint}</code>
        </p>
        {model.vllm_version && (
          <p className="text-xs text-primary-400 dark:text-primary-500">
            vLLM: {model.vllm_version}
          </p>
        )}
      </div>
      <div className="flex gap-2">
        <Button variant="ghost" size="sm" onClick={onEdit}>Edit</Button>
        <Button variant="danger" size="sm" onClick={onDelete}>Delete</Button>
      </div>
    </div>
  );
}
```

---

## 17. Phase 13: Frontend ModelManager Component

### 17.1 Create `frontend/src/components/ui/ModelManager.tsx`

```typescript
import { useState, useEffect } from 'react';
import { Card, Input, Select, Button, FormField, Toast } from './';
import { modelsApi } from '../../services/api';
import type { LLMModel } from '../../types';

interface ModelManagerProps {
  open: boolean;
  onClose: () => void;
  model: LLMModel | null; // null = creating new
  onSave: () => void;
}

const MODEL_TYPE_OPTIONS = [
  { value: 'general', label: 'General' },
  { value: 'text', label: 'Text Generation' },
  { value: 'image_audio', label: 'Image & Audio' },
];

export default function ModelManager({ open, onClose, model, onSave }: ModelManagerProps) {
  const [name, setName] = useState('');
  const [endpoint, setEndpoint] = useState('');
  const [modelsEndpoint, setModelsEndpoint] = useState('');
  const [modelName, setModelName] = useState('');
  const [modelType, setModelType] = useState<'text' | 'image_audio' | 'general'>('general');
  const [vllmVersion, setVllmVersion] = useState('');
  const [thinkingEnabled, setThinkingEnabled] = useState(false);
  const [saving, setSaving] = useState(false);
  const [fetching, setFetching] = useState(false);
  const [fetchStatus, setFetchStatus] = useState('');
  const [error, setError] = useState('');

  // Reset state when modal opens
  useEffect(() => {
    if (open) {
      if (model) {
        // Editing existing model
        setName(model.name);
        setEndpoint(model.endpoint);
        setModelsEndpoint(model.models_endpoint);
        setModelName(model.model_name);
        setModelType(model.model_type as 'text' | 'image_audio' | 'general');
        setVllmVersion(model.vllm_version || '');
        setThinkingEnabled(model.thinking_enabled);
      } else {
        // Creating new model
        setName('');
        setEndpoint('');
        setModelsEndpoint('');
        setModelName('');
        setModelType('general');
        setVllmVersion('');
        setThinkingEnabled(false);
      }
      setError('');
      setFetchStatus('');
    }
  }, [open, model]);

  const handleFetchInfo = async () => {
    setFetching(true);
    setFetchStatus('Fetching model info...');
    try {
      const baseEndpoint = endpoint.replace(/\/v1\/models$/, '/v1');
      const info = await modelsApi.fetchInfo(baseEndpoint);
      setModelName(info.model_name);
      setVllmVersion(info.vllm_version);
      setThinkingEnabled(info.thinking_enabled);
      setFetchStatus('✓ Model info fetched');
      setTimeout(() => setFetchStatus(''), 3000);
    } catch (err) {
      setFetchStatus('✗ Failed: ' + (err instanceof Error ? err.message : String(err)));
      setTimeout(() => setFetchStatus(''), 5000);
    } finally {
      setFetching(false);
    }
  };

  const handleSave = async () => {
    if (!name.trim()) { setError('Friendly name is required'); return; }
    if (!endpoint.trim()) { setError('Endpoint is required'); return; }
    if (!modelName.trim()) { setError('Model name is required'); return; }

    setSaving(true);
    setError('');

    try {
      const payload = {
        name: name.trim(),
        endpoint: endpoint.trim(),
        models_endpoint: modelsEndpoint.trim() || endpoint.trim().replace(/\/v1$/, '/v1/models'),
        model_name: modelName.trim(),
        model_type: modelType,
        vllm_version: vllmVersion || undefined,
        thinking_enabled: thinkingEnabled,
      };

      if (model) {
        await modelsApi.update(model.model_id, payload);
      } else {
        await modelsApi.create(payload);
      }
      onSave();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save model');
    } finally {
      setSaving(false);
    }
  };

  if (!open) return null;

  const isEditing = !!model;

  return (
    <>
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
        <Card title={isEditing ? `Edit: ${model?.name}` : 'Add New Model'} className="w-full max-w-lg max-h-[80vh] overflow-y-auto">
          <button onClick={onClose} className="absolute top-4 right-4 text-primary-500 hover:text-primary-700 text-2xl leading-none">&times;</button>

          <div className="space-y-4">
            <FormField label="Friendly Name" helperText="Human-readable name for this model">
              <Input type="text" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g., Production Text Model" disabled={saving} />
            </FormField>

            <FormField label="Model Type">
              <Select value={modelType} onChange={(e) => setModelType(e.target.value as 'text' | 'image_audio' | 'general')}>
                {MODEL_TYPE_OPTIONS.map(opt => (
                  <option key={opt.value} value={opt.value}>{opt.label}</option>
                ))}
              </Select>
            </FormField>

            <FormField label="Endpoint" helperText="Base URL of the vLLM endpoint">
              <Input id="endpoint" type="text" value={endpoint} onChange={(e) => setEndpoint(e.target.value)} placeholder="http://localhost:8000/v1" disabled={saving} />
            </FormField>

            <FormField label="Models Endpoint" helperText="Full models endpoint URL">
              <Input id="models_endpoint" type="text" value={modelsEndpoint} onChange={(e) => setModelsEndpoint(e.target.value)} placeholder="http://localhost:8000/v1/models" disabled={saving} />
            </FormField>

            <FormField label="Model Name" helperText="The actual model identifier">
              <Input id="model_name" type="text" value={modelName} onChange={(e) => setModelName(e.target.value)} placeholder="facebook/opt-125m" disabled={saving} />
            </FormField>

            <div className="flex items-center gap-3">
              <Button variant="secondary" loading={fetching} onClick={handleFetchInfo} disabled={!endpoint.trim()}>
                Fetch Model Info
              </Button>
              {fetchStatus && (
                <span className={`text-xs ${fetchStatus.startsWith('✗') ? 'text-accent-400' : 'text-primary-400 dark:text-primary-500'}`}>
                  {fetchStatus}
                </span>
              )}
            </div>

            <FormField label="vLLM Version">
              <Input type="text" value={vllmVersion} onChange={(e) => setVllmVersion(e.target.value)} placeholder="e.g., 0.6.0" disabled={saving} />
            </FormField>

            <div className="flex items-center gap-2">
              <input id="thinking_enabled" type="checkbox" checked={thinkingEnabled} onChange={(e) => setThinkingEnabled(e.target.checked)} className="h-4 w-4 rounded" />
              <label htmlFor="thinking_enabled" className="text-sm text-primary-700 dark:text-primary-300">Thinking Enabled</label>
            </div>
          </div>

          {error && (
            <div className="mt-4 rounded-md bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 px-3 py-2 text-sm text-red-700 dark:text-red-400">
              {error}
            </div>
          )}

          <div className="flex justify-end gap-2 mt-6">
            <Button onClick={onClose} disabled={saving} variant="ghost">Cancel</Button>
            <Button onClick={handleSave} disabled={saving} variant="primary" loading={saving}>
              {isEditing ? 'Save Changes' : 'Add Model'}
            </Button>
          </div>
        </Card>
      </div>
    </>
  );
}
```

### 17.2 Export from `index.ts`

Add to `frontend/src/components/ui/index.ts`:

```typescript
export { default as ModelManager } from "./ModelManager";
```

---

## 18. Phase 14: Frontend Prompt UI

### 18.1 Update `frontend/src/components/ui/PromptSelector.tsx`

Add model badge display next to the prompt name:

```typescript
// After rendering the prompt name in the selector, add a small badge showing the assigned model name
{prompt.metadata?.model_id && (
  <span className="ml-2 rounded-full bg-primary-100 dark:bg-primary-900 text-primary-700 dark:text-primary-300 px-1.5 py-0.5 text-[10px] font-medium">
    {prompt.metadata?.model_name || `Model ${prompt.metadata?.model_id}`}
  </span>
)}
```

### 18.2 Update `frontend/src/components/ui/CreatePromptModal.tsx`

Add a model selector dropdown. Import the models API and add state for available models:

```typescript
import { modelsApi } from '../../services/api';
import type { LLMModel } from '../../types';

const [availableModels, setAvailableModels] = useState<LLMModel[]>([]);
const [selectedModelId, setSelectedModelId] = useState<number | undefined>(undefined);

useEffect(() => {
  if (open) {
    modelsApi.getAll().then(setAvailableModels).catch(() => {});
  }
}, [open]);
```

Add the model selector in the form:

```tsx
<div>
  <label className="block text-sm font-medium text-primary-700 dark:text-primary-300 mb-1">
    LLM Model (optional)
  </label>
  <Select value={String(selectedModelId ?? '')} onChange={(e) => setSelectedModelId(e.target.value ? Number(e.target.value) : undefined)}>
    <option value="">Default (no model assignment)</option>
    {availableModels.map(m => (
      <option key={m.model_id} value={m.model_id}>
        {m.name} ({m.model_name}) — {m.model_type}
      </option>
    ))}
  </Select>
  <p className="mt-1 text-xs text-primary-400 dark:text-primary-500">
    The model used when executing prompts with this version. Leave empty to use the default model.
  </p>
</div>
```

---

## 19. Phase 15: Frontend Guest Search Integration

### 19.1 Update `frontend/src/pages/GuestSearch.tsx`

Pass `model_id` from the selected prompt to the name extraction call:

```typescript
const handleExtractName = async () => {
  const formData = new FormData();
  formData.append('file', imageFile);
  if (cropRegion) {
    formData.append('crop_x', String(cropRegion.x));
    // ... other crop params
  }
  if (selectedPrompt.model_id) {
    formData.append('model_id', String(selectedPrompt.model_id));
  }

  const resp = await fetch('/api/guest-search/extract-name', {
    method: 'POST',
    body: formData,
  });

  const data = await resp.json() as NameExtractionResponse;
  setQuery(data.extracted_name);
};
```

### 19.2 Update `NameExtractionResponse` in API

Add `model_id` to the response type:

```typescript
export interface NameExtractionResponse {
  extracted_name: string;
  source: 'image' | 'audio';
  model_id?: number;  // NEW
}
```

---

## 20. Phase 16: Frontend Prompt Settings Panel

### 20.1 Update `frontend/src/components/ui/PromptSettingsPanel.tsx`

Replace the existing model configuration (if any) with a model selector dropdown:

```typescript
import { modelsApi } from '../../services/api';
import type { LLMModel } from '../../types';

const [availableModels, setAvailableModels] = useState<LLMModel[]>([]);

useEffect(() => {
  modelsApi.getAll().then(setAvailableModels).catch(() => {});
}, []);
```

In the render, add a model selector section:

```tsx
<div className="mt-4">
  <FormField label="LLM Model">
    <Select value={String(promptData.model_id ?? '')} onChange={(e) => {
      const id = e.target.value ? Number(e.target.value) : null;
      // Update prompt data with new model_id
    }}>
      <option value="">Default (system model)</option>
      {availableModels.map(m => (
        <option key={m.model_id} value={m.model_id}>
          {m.name} ({m.model_name}) — {m.model_type.replace('_', ' ')}
        </option>
      ))}
    </Select>
    <p className="mt-1 text-xs text-primary-400 dark:text-primary-500">
      Assign an LLM model to this prompt version. Leave empty to use the default.
    </p>
  </FormField>
</div>
```

---

## 21. Testing

### 21.1 Backend Tests

```bash
# Start the server
cd backend && uv run uvicorn app.main:app --reload

# Test model CRUD
curl http://localhost:8000/api/models
# → []

curl -X POST http://localhost:8000/api/models \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Production Text",
    "endpoint": "http://localhost:8000/v1",
    "models_endpoint": "http://localhost:8000/v1/models",
    "model_name": "facebook/opt-125m",
    "model_type": "text",
    "thinking_enabled": false
  }'
# → {"model_id": 1, "name": "Production Text", ...}

curl http://localhost:8000/api/models/1
# → {"model_id": 1, ...}

curl -X PUT http://localhost:8000/api/models/1 \
  -H "Content-Type: application/json" \
  -d '{"name": "Text Model v2"}'

curl -X DELETE http://localhost:8000/api/models/1
```

### 21.2 Frontend Tests

```bash
# Build frontend
cd frontend && npm run build
npx tsc --noEmit

# Check the settings page loads and shows model list
# Verify add/edit/delete model flows work
# Create a prompt and assign a model
# Verify the model badge appears on the prompt selector
```

### 21.3 End-to-End Flow

```
1. Navigate to Settings
2. Add a "Text Model" with endpoint http://localhost:8000/v1
3. Add an "Image+Audio Model" with endpoint http://localhost:8001/v1
4. Navigate to Prompt Management
5. Create a new prompt version and assign "Text Model"
6. Navigate to Guest Search
7. Select the new prompt
8. Upload an image and click "Extract Name" — should use the Image+Audio Model
9. Click "Search" — should use the Text Model
```

---

## 22. Migration Notes

### Existing Data

- **No migration needed for existing prompts** — they get `model_id = NULL`, which causes the system to fall back to the first available model. This preserves existing behavior.
- **Existing config.json** — the `TestSettings` dataclass is retained for backward compatibility. New code paths read from the database.

### Backward Compatibility

| Path | Behavior |
|------|----------|
| Prompt with `model_id = NULL` | Falls back to first configured model in DB |
| No models in DB | Falls back to first model returned by `/v1/models` endpoint |
| Config.json with old fields | Used as fallback when no model found in DB |

---

## 23. Implementation Extensions & Deviations

> This section documents features, enhancements, and deviations that were added during implementation beyond the original specification. These reflect the actual production implementation.

---

### 23.1 `LLMModel` Table — Schema Deviations

The actual `LLMModel` table in `backend/app/models.py` differs from the specification in the following ways:

| Column | Specification | Implementation | Notes |
|--------|--------------|----------------|-------|
| `name` | `String(200), nullable=False` | `String(200), nullable=False, **unique=True**` | **Added unique constraint** to prevent duplicate model names at the database level |
| `model_type` | `nullable=False, server_default="general"` | `nullable=True` | **No NOT NULL constraint, no server default** — model_type is truly optional |
| `thinking_enabled` | `Boolean, default=False` | `Boolean, default=False, **server_default="0"**` | **Added server default** for SQLite compatibility |
| `prompt_versions` | Not specified | `relationship(back_populates="llm_model", lazy="selectin")` | **Added relationship** with eager loading for convenient access from LLMModel side |

#### Rationale

- The **unique constraint** on `name` is a practical enhancement: it prevents two models from sharing the same display name, which would confuse the UI.
- Making `model_type` optional allows users to register models without declaring their capability (the field can be filled in later).
- The `server_default="0"` ensures SQLite creates proper `FALSE` defaults even before any INSERT.
- The `prompt_versions` relationship enables reverse lookups (e.g., "which prompts use this model?") and is used by the cascade deletion logic.

---

### 23.2 Schema Extensions

#### 23.2.1 `DeleteModelResponse` — Added `message` Field

**Implementation:**
```python
class DeleteModelResponse(BaseModel):
    ok: bool = True
    model_id: int | None = None
    message: str | None = None  # ← ADDED
    error: str | None = None
```

The `message` field carries a human-readable confirmation like `"Model 'X' deleted successfully."`.

#### 23.2.2 `ModelInfoResponse` — New Schema

Added for live model info fetching:

```python
class ModelInfoResponse(BaseModel):
    ok: bool = True
    model_name: str | None = None
    vllm_version: str | None = None
    thinking_enabled: bool | None = None
    error: str | None = None
```

This is returned by both `/api/models/fetch-info` and `/api/models/{model_id}/info`.

---

### 23.3 Extended API Endpoints

#### 23.3.1 `/api/models/{model_id}/info` — Live Info for Saved Model

A new GET endpoint fetches live model info from a saved model's endpoint. Uses the model's `endpoint` and `models_endpoint` to hit the upstream vLLM server, returning the actual model name and vLLM version reported by the server.

#### 23.3.2 `/api/models/fetch-info` — JSON Body with Normalization

Uses a JSON body and adds automatic URL normalization:

- If the URL ends with `/v1/models` → use as-is
- If the URL ends with `/v1` → append `/models`
- Otherwise → append `/v1/models`

#### 23.3.3 Duplicate Name Checking

The create and update endpoints check for duplicate model names. For updates, the check excludes the current model.

#### 23.3.4 Detailed Delete Error Messages

The delete endpoint includes the model name in the conflict error:

```python
detail=(
    f"Cannot delete model '{model.name}': it is referenced by "
    f"{ref_count} prompt version(s). Assign a different model to "
    "those prompts first, or delete them."
),
```

---

### 23.4 Shared HTTP Transport for Connection Pooling

The LLM service uses a module-level singleton `httpx.Client` with connection pooling that is shared across all `OpenAI` client instances:

```python
_SHARED_TRANSPORT: httpx.HTTPTransport | None = None
_SHARED_HTTP_CLIENT: httpx.Client | None = None

def _get_shared_http_client() -> httpx.Client:
    """Return a module-level singleton httpx.Client with connection pooling."""
    ...

def _get_base_client() -> tuple[OpenAI, str]:
    """Every OpenAI client passes the same underlying httpx.Client."""
    shared_client = _get_shared_http_client()
    client = OpenAI(
        http_client=shared_client,
        base_url=base_url,
        api_key="none",
    )
    return client, base_url
```

This is critical for performance: without shared transport, each `OpenAI` client gets its own isolated connection pool, preventing TCP connection reuse across concurrent requests.

---

### 23.5 Model Resolution Return Type Deviation

The specification defines `get_llm_config_by_model_id()` as returning `(OpenAI, str, str)` — client, model_name, **model_type**. The implementation returns only `(OpenAI, str)` — client and model_name.

**Implementation:**
```python
def get_llm_config_by_model_id(model_id: int | None) -> tuple[OpenAI, str]:
    return client, model.model_name  # model_type not returned
```

**Additional deviations:**
1. The function accepts `model_id: int | None` (not just `int`) and falls back to `get_llm_config()` when `None`.
2. There is no `model_type` in the return value, so downstream code cannot auto-route based on capability.

---

### 23.6 `get_available_models()` — Additional Function

A function to list all available models from the upstream vLLM endpoint:

```python
def get_available_models() -> list[LLMModelInfo]:
    """Fetch all available models from the configured LLM endpoint."""
    client, _ = _get_base_client()
    try:
        models = client.models.list()
        return [LLMModelInfo(id=m.id, object=m.object, created=m.created, owned_by=m.owned_by) for m in models.data]
    except Exception as e:
        logger.warning("Failed to fetch available models: %s", e)
        return []
```

---

### 23.7 Response Cache — Model-Aware Caching & Diagnostics

**Partially implemented.** The specification mentioned including model name in the cache key but this was **not implemented**. The actual implementation uses a simple text-based cache key without model awareness. This is a known limitation that could cause cross-model cache pollution.

#### 23.7.1 Cache Key (No Model Awareness)

```python
def generate_cache_key(data: str) -> str:
    normalized = data.strip().lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
```

#### 23.7.2 Extended CacheStore with Statistics

The `CacheStore` class includes hit/miss tracking:

```python
class CacheStore:
    @property
    def stats(self) -> dict[str, int]:
        return {"hits": self._hits, "misses": self._misses, "size": len(self._store)}
```

#### 23.7.3 HTTP Response Cache (Enhancement)

An additional `HttpCacheStore` caches HTTP GET responses by URI with TTL-based expiration.

#### 23.7.4 ResponseLogger — Diagnostic Logging

**NOT implemented.** A comprehensive logging middleware for LLM call diagnostics was planned but not implemented.

---

### 23.8 Guest Extraction — Model ID Support

The extraction functions accept optional `model_id` parameters:

```python
def _get_client_and_model(model_id: int | None = None) -> tuple[OpenAI, str]:
    """If model_id is provided, looks up the model from the LLMModels table."""
    if model_id is not None:
        client, model_name = get_llm_config_by_model_id(model_id)
        return client, model_name
    # Fall back to config.json
```

---

### 23.9 `_get_base_client()` URL Normalization

The `_get_base_client()` helper normalizes the models endpoint URL:

```python
def _get_base_client() -> tuple[OpenAI, str]:
    models_endpoint = config_manager.test_settings.models_endpoint
    base_url = models_endpoint.rstrip('/').replace('/models', '')
    ...
```

---

### 23.10 Prompt Version `model_id` — `ondelete="SET NULL"` Behavior

Both the spec and implementation use `ondelete="SET NULL"` on the foreign key. When an `LLMModel` is deleted, any `PromptVersion` referencing it gets `model_id = NULL` and falls back to the default model.

---

## Appendix A: Complete File List

| Phase | File | Action |
|-------|------|--------|
| 1 | `backend/app/models.py` | **Modify** — add `LLMModel` table, add `model_id` on `PromptVersion` |
| 1 | Alembic migration | **Create** — `llm_models` table + `model_id` column |
| 2 | `backend/app/schemas.py` | **Modify** — add model schemas, update prompt schemas |
| 3 | `backend/app/routes/models.py` | **NEW** — full CRUD + fetch-info |
| 3 | `backend/app/main.py` | **Modify** — register models router |
| 4 | `backend/app/services/llm.py` | **Modify** — `get_llm_config_by_model_id()`, `get_llm_config_by_name()` |
| 4 | `backend/app/services/llm.py` | **Modify** — `query_guest_with_llm()` uses model from prompt |
| 5 | `backend/app/services/guest_extraction.py` | **Modify** — `_get_client_and_model()` reads from DB |
| 5 | `backend/app/routes/guest_search.py` | **Modify** — add `model_id` param to extraction endpoint |
| 6 | `backend/app/services/response_cache.py` | **Modify** — include model name in cache key |
| 7 | `backend/app/services/prompt_chain.py` | **Modify** — resolve model per step |
| 8 | `backend/PerformanceTesting/settings.py` | **Modify** — accept `model_id` |
| 8 | `backend/app/routes/performance_testing.py` | **Modify** — resolve model from prompt |
| 9 | `backend/app/config.py` | **Modify** — deprecate `TestSettings` defaults |
| 10 | `frontend/src/types/index.ts` | **Modify** — add `LLMModel`, `CreateModelRequest`, `UpdateModelRequest`, `ModelInfoResponse`, `model_id` on prompt types |
| 11 | `frontend/src/services/api.ts` | **Modify** — add `modelsApi` CRUD methods |
| 11 | `frontend/src/services/promptsApi.ts` | **Modify** — pass `model_id` in create/update |
| 12 | `frontend/src/pages/Settings.tsx` | **Modify** — model management hub |
| 13 | `frontend/src/components/ui/ModelManager.tsx` | **NEW** — modal for add/edit model |
| 13 | `frontend/src/components/ui/index.ts` | **Modify** — export `ModelManager` |
| 14 | `frontend/src/components/ui/PromptSelector.tsx` | **Modify** — show model badge |
| 14 | `frontend/src/components/ui/CreatePromptModal.tsx` | **Modify** — add model selector |
| 15 | `frontend/src/pages/GuestSearch.tsx` | **Modify** — pass `model_id` to extraction |
| 15 | `frontend/src/services/api.ts` | **Modify** — add `model_id` to `NameExtractionResponse` |
| 16 | `frontend/src/components/ui/PromptSettingsPanel.tsx` | **Modify** — model selector dropdown |