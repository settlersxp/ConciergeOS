# Implementation Plan

**Versioned Prompt System** — Refactor the project to version all prompts used by the application, with database-backed storage and frontend-managed CRUD.

This implementation introduces a versioned prompt system where each prompt is identified by `{prompt_id}:v{version}`. Prompts are stored in a new `prompt_versions` SQLite table with 4 structured fields: `intention`, `restrictions`, `output_structure`, and `user_prompt_template`. The frontend provides full CRUD management via a new `PromptManagement` page and integrates prompt selection into `GuestSearch` and `PerformanceTesting` pages.

The system is generic — any feature can define its own `prompt_id` (e.g., `guest-search`, `reservation-query`, `summary-report`). Existing hardcoded prompts in `app/services/llm.py` are migrated into structured database entries on first startup.

---

[Types]
**New TypeScript and Python types for versioned prompts with 4 structured fields.**

Python types are defined in Pydantic schemas (`app/schemas.py`) and SQLAlchemy model (`app/models.py`):

```python
# SQLAlchemy model (app/models.py)
class PromptVersion(Base):
    __tablename__ = "prompt_versions"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    prompt_id: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    intention: Mapped[str] = mapped_column(Text, nullable=False)          # New field
    restrictions: Mapped[str] = mapped_column(Text, nullable=False)       # New field
    output_structure: Mapped[str] = mapped_column(Text, nullable=False)   # New field
    user_prompt_template: Mapped[str] = mapped_column(Text, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    metadata: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        UniqueConstraint("prompt_id", "version", name="uq_prompt_version"),
    )
```

```python
# Pydantic schemas (app/schemas.py)
class PromptVersionSchema(BaseModel):
    id: int
    prompt_id: str
    version: int
    name: str
    intention: str
    restrictions: str
    output_structure: str
    user_prompt_template: str
    is_default: bool
    metadata: dict | None = None
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}

class CreatePromptRequest(BaseModel):
    name: str
    intention: str
    restrictions: str
    output_structure: str
    user_prompt_template: str
    metadata: dict | None = None

class UpdatePromptRequest(BaseModel):
    name: str | None = None
    intention: str | None = None
    restrictions: str | None = None
    output_structure: str | None = None
    user_prompt_template: str | None = None
    metadata: dict | None = None

class DuplicatePromptRequest(BaseModel):
    name: str | None = None

class SetDefaultRequest(BaseModel):
    version: int

class PromptSummarySchema(BaseModel):
    """Summary for listing prompt IDs."""
    prompt_id: str
    default_version: int
    version_count: int
    name: str
```

```typescript
// TypeScript types (frontend/src/types/prompt.ts)
export interface PromptVersion {
  id: number;
  prompt_id: string;
  version: number;
  name: string;
  intention: string;
  restrictions: string;
  output_structure: string;
  user_prompt_template: string;
  is_default: boolean;
  metadata: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface PromptSummary {
  prompt_id: string;
  default_version: number;
  version_count: number;
  name: string;
}

export interface CreatePromptRequest {
  name: string;
  intention: string;
  restrictions: string;
  output_structure: string;
  user_prompt_template: string;
  metadata?: Record<string, unknown>;
}

export interface UpdatePromptRequest {
  name?: string;
  intention?: string;
  restrictions?: string;
  output_structure?: string;
  user_prompt_template?: string;
  metadata?: Record<string, unknown>;
}

export interface DuplicatePromptRequest {
  name?: string;
}
```

---

[Files]
**7 new files created, 10 existing files modified across backend and frontend.**

### New Files (7)

| File | Purpose |
|------|---------|
| `app/services/prompts.py` | `PromptStore` class — database-backed CRUD for prompt versions |
| `app/routes/prompts.py` | FastAPI router with 9 REST endpoints for prompt CRUD |
| `frontend/src/types/prompt.ts` | TypeScript interfaces for all prompt-related types |
| `frontend/src/services/promptsApi.ts` | API client with methods for all 9 prompt endpoints |
| `frontend/src/components/ui/PromptSelector.tsx` | Reusable dropdown component using `<Select>` and `<FormField>` |
| `frontend/src/pages/PromptManagement.tsx` | Full-page CRUD UI with 3 text areas (intention, restrictions, output_structure) + user prompt template |
| `docs/PLAN_PROMPT_VERSIONING.md` | Architectural plan document (already exists) |

### Modified Files (10)

| File | Specific Changes |
|------|------------------|
| `app/models.py` | Add `PromptVersion` class after `PerformanceTestResult` (line ~107) |
| `app/schemas.py` | Add 6 new schema classes after `GuestSearchResponse` (after line 130); modify `GuestSearchRequest` to add `prompt_id` and `version` fields |
| `app/services/llm.py` | Modify `query_guest_with_llm()` signature to accept `prompt_id` and `version`; replace hardcoded prompt resolution with `PromptStore` lookup |
| `app/routes/guest_search.py` | Import new schemas; pass `prompt_id`/`version` from request body to `query_guest_with_llm()` |
| `app/main.py` | Add import for `prompts_router`; call `app.include_router(prompts_router)` |
| `app/routes/__init__.py` | Add `prompts_router` to exports |
| `frontend/src/types/index.ts` | Add `prompt_id?: string` and `prompt_version?: number` to `PerformanceTestRequest` |
| `frontend/src/services/api.ts` | Modify `guestSearchApi.search()` to accept optional `{ prompt_id, version }`; add `promptsApi` methods |
| `frontend/src/pages/GuestSearch.tsx` | Add `PromptSelector` component; pass `prompt_id`/`version` to search API |
| `frontend/src/pages/PerformanceTesting.tsx` | Add prompt ID + version selectors; load prompt content from store when selection changes; pass `prompt_id`/`prompt_version` to test payload |
| `frontend/src/App.tsx` | Add import for `PromptManagement`; add `<Route path="/prompts" .../>` |

---

[Functions]
**New functions in PromptStore and API routes; modifications to existing functions.**

### New Functions in `app/services/prompts.py`

| Function | Signature | Purpose |
|----------|-----------|---------|
| `PromptStore.__init__` | `(self, db_session_factory)` | Initialize with `sessionmaker` |
| `PromptStore.create_prompt` | `(self, prompt_id, name, intention, restrictions, output_structure, user_prompt_template, metadata) -> PromptVersion` | Create v1 of a new prompt, auto-set as default |
| `PromptStore.get_prompt` | `(self, prompt_id, version=None) -> PromptVersion` | Get specific version or default if version is None |
| `PromptStore.list_prompts` | `(self, prompt_id) -> list[PromptVersion]` | List all versions ordered by version number |
| `PromptStore.list_all_prompts` | `(self) -> list[PromptSummarySchema]` | Summary of all prompt IDs |
| `PromptStore.update_prompt` | `(self, prompt_id, version, **kwargs) -> PromptVersion` | Update fields; update `updated_at` timestamp |
| `PromptStore.delete_prompt` | `(self, prompt_id, version) -> bool` | Delete version; if default, set next-lower as default |
| `PromptStore.duplicate_prompt` | `(self, prompt_id, version, name) -> PromptVersion` | Copy version content to version+1 |
| `PromptStore.set_default` | `(self, prompt_id, version) -> PromptVersion` | Unset all defaults for prompt_id, set specified as default |
| `PromptStore.get_default_prompt` | `(self, prompt_id) -> PromptVersion` | Get the default version |
| `PromptStore.seed_default_prompts` | `(self) -> None` | On startup: if empty, seed from `app/services/llm.py` hardcoded prompts |

### New Functions in `app/routes/prompts.py`

| Function | Route | Purpose |
|----------|-------|---------|
| `list_all_prompts` | `GET /api/prompts` | List summary of all prompt IDs |
| `list_versions` | `GET /api/prompts/{prompt_id}` | List all versions for a prompt |
| `get_default` | `GET /api/prompts/{prompt_id}/default` | Get default version |
| `get_version` | `GET /api/prompts/{prompt_id}/{version}` | Get specific version |
| `create_version` | `POST /api/prompts/{prompt_id}` | Create new version (auto-increments) |
| `update_version` | `PUT /api/prompts/{prompt_id}/{version}` | Update existing version |
| `delete_version` | `DELETE /api/prompts/{prompt_id}/{version}` | Delete version |
| `duplicate_version` | `POST /api/prompts/{prompt_id}/{version}/duplicate` | Duplicate as next version |
| `set_default_version` | `PATCH /api/prompts/{prompt_id}/{version}/set-default` | Set as default |

### Modified Functions

| Function | File | Changes |
|----------|------|---------|
| `query_guest_with_llm` | `app/services/llm.py` | Accept `prompt_id` (default `"guest-search"`) and `version` (default `None`). Resolve from `PromptStore`. Build system prompt from `intention + restrictions + output_structure`. |
| `api_guest_search` | `app/routes/guest_search.py` | Extract `prompt_id` and `version` from request body; pass to `query_guest_with_llm()` |
| `handleRun` | `frontend/src/pages/PerformanceTesting.tsx` | Include `prompt_id` and `prompt_version` in `PerformanceTestRequest` payload |

---

[Classes]
**One new service class, one new route router, and frontend component classes.**

### `PromptStore` (`app/services/prompts.py`)

Database-backed CRUD service. Uses the existing `SessionLocal` from `app.db`.

Key design decisions:
- Singleton pattern: created once at module level, reused across requests
- Thread-safe: uses SQLAlchemy's existing session isolation
- Auto-increments version: `next_version = max(v.version for v in versions) + 1`
- Default cascade: when deleting a default version, the next-lower version becomes default
- Migration seed: `seed_default_prompts()` splits the current `SHARED_SYSTEM_PROMPT` and user prompt from `llm.py` into the 4 structured fields

### `PromptManagement` (`frontend/src/pages/PromptManagement.tsx`)

Full-page React component. Uses existing UI components:
- `<PageHeader>` for page title
- `<Card>` for section containers
- `<Select>` for prompt ID dropdown
- `<Textarea>` for the 3 prompt sections + user prompt template
- `<FormField>` for labels around all inputs
- `<Button>` for actions
- `<Badge>` for default indicator

State: `selectedPromptId`, `versions[]`, `editingVersion`, `editForm { name, intention, restrictions, output_structure, user_prompt_template }`

### `PromptSelector` (`frontend/src/components/ui/PromptSelector.tsx`)

Reusable dropdown component. Props: `promptId`, `value: { prompt_id, version? }`, `onChange`, `label`. Internally fetches versions from `promptsApi.listVersions(promptId)` and renders a `<Select>` with `<FormField>`.

---

[Dependencies]
**No new external packages. Uses existing SQLAlchemy, FastAPI, React, TypeScript.**

All changes use the existing dependency tree:
- Backend: `sqlalchemy` (ORM), `pydantic` (schemas), `fastapi` (routing)
- Frontend: `react`, `react-router-dom`, TypeScript

The `prompt_versions` table uses SQLite's built-in capabilities. No migrations framework is needed — the `PromptStore.create_all_tables()` method (called during `seed_default_prompts()`) handles table creation via SQLAlchemy's `Base.metadata.create_all(engine)`.

---

[Testing]
**Backend tests use `pytest` with `httpx` async test client. Frontend tests use existing Vite + TypeScript setup.**

### Backend Test Requirements (`tests/test_prompts.py`)

```
- Create prompt v1, verify auto-increment and is_default=True
- Create prompt v2, verify version increment, is_default=False
- Get prompt by ID without version → returns default
- Get prompt by ID with version → returns specific version
- Update prompt fields, verify persistence
- Delete default version → next-lower becomes default
- Delete non-default version → removed, defaults unchanged
- Duplicate prompt → creates version+1 with copied content
- Set default → updates is_default flags correctly
- Seed default prompts on empty database → creates guest-search:v1
- Backward compatibility: query_guest_with_llm() works without prompt_id
- System prompt correctly combines intention + restrictions + output_structure
```

### Frontend Test Requirements

```
- PromptSelector renders and loads versions on mount
- Selecting a version triggers onChange with correct payload
- PromptManagement create form validates required fields
- PromptManagement edit form persists changes on save
- PromptManagement delete removes from list
- GuestSearch sends prompt_id + version with search request
- PerformanceTesting loads prompt content when selector changes
- Preview in PromptManagement combines system prompt sections correctly
```

---

[Implementation Order]
**15 numbered steps in 3 phases, ordered to minimize conflicts and ensure successful integration.**

### Phase 1: Backend Foundation (Steps 1-6)

1. **Add `PromptVersion` model to `app/models.py`** — Append after `PerformanceTestResult`. Uses existing `Base`, `Mapped`, `mapped_column` imports. No other model changes needed.

2. **Create `app/services/prompts.py`** — New file. Implement `PromptStore` with all CRUD methods. Use `SessionLocal()` for database access. The `seed_default_prompts()` method is left with stub implementation for Step 14.

3. **Create `app/routes/prompts.py`** — New file. Implement 9 FastAPI route handlers. Each handler creates a `PromptStore()`, calls the appropriate method, returns JSONResponse. Register with `router = APIRouter()`.

4. **Add schemas to `app/schemas.py`** — After `GuestSearchResponse` (line ~131), add `PromptVersionSchema`, `PromptSummarySchema`, `CreatePromptRequest`, `UpdatePromptRequest`, `DuplicatePromptRequest`, `SetDefaultRequest`. Modify `GuestSearchRequest` to add `prompt_id: str = "guest-search"` and `version: int | None = None`.

5. **Wire up routes in `app/main.py` and `app/routes/__init__.py`** — Add `from app.routes.prompts import router as prompts_router` to both files. Add `app.include_router(prompts_router)` after existing includes.

6. **Modify `app/services/llm.py`** — Update `query_guest_with_llm()` to accept `prompt_id` and `version` parameters. Replace hardcoded prompt construction with `PromptStore` lookup. Build system prompt from the 3 structured fields.

### Phase 2: Frontend Integration (Steps 7-13)

7. **Create `frontend/src/types/prompt.ts`** — New file. Copy all TypeScript interfaces from the plan.

8. **Create `frontend/src/services/promptsApi.ts`** — New file. Implement all 9 API methods using existing `request` helper pattern from `api.ts`.

9. **Create `frontend/src/components/ui/PromptSelector.tsx`** — New file. Reuses `<Select>`, `<FormField>` from `../../components/ui`. Export from `frontend/src/components/ui/index.ts`.

10. **Create `frontend/src/pages/PromptManagement.tsx`** — New file. Full CRUD page with 3 text areas + preview. Uses `<Card>`, `<Button>`, `<Textarea>`, `<FormField>`, `<Badge>`, `<PageHeader>`.

11. **Modify `frontend/src/pages/GuestSearch.tsx`** — Add `PromptSelector` import and state. Pass `prompt_id`/`version` to `guestSearchApi.search()`.

12. **Modify `frontend/src/services/api.ts`** — Update `guestSearchApi.search()` to accept options. Add `promptsApi` object with all 9 methods.

13. **Modify `frontend/src/pages/PerformanceTesting.tsx` and `frontend/src/App.tsx`** — Add prompt selectors to PerformanceTesting. Add PromptManagement route to App.tsx.

### Phase 3: Migration & Polish (Steps 14-15)

14. **Implement `seed_default_prompts()`** — Back in `app/services/prompts.py`. Split `SHARED_SYSTEM_PROMPT` and the hardcoded user prompt from `llm.py` into the 4 structured fields. Called automatically if table is empty.

15. **Update app navigation** — Add "Prompt Management" link to `frontend/src/components/Header.tsx`.

---

*This plan is complete. Execute the steps in order to implement the versioned prompt system.*