# Versioned Prompt System — Implementation Plan

## Overview

A versioned prompt system where each prompt is identified by `{prompt_id}:v{version}`. Prompts are stored in a new `prompt_versions` SQLite table with 4 structured fields: `intention`, `restrictions`, `output_structure`, and `user_prompt_template`. The frontend provides full CRUD management via a new `PromptManagement` page and integrates prompt selection into `GuestSearch` and `PerformanceTesting` pages.

The system is generic — any feature can define its own `prompt_id` (e.g., `guest-search`, `reservation-query`, `summary-report`). Existing hardcoded prompts in `app/services/llm.py` are migrated into structured database entries on first startup via automatic seeding.

## Dependency Order

```
Backend (Model → Service → Routes → Schemas) → Frontend (Types → API Client → Components → Pages → Router)
```

**Architecture breakdown**:
```
Backend Foundation (Steps 1-6):
  1. PromptVersion model (app/models.py)
  2. PromptStore service (app/services/prompts.py)
  3. Prompt routes (app/routes/prompts.py)
  4. Pydantic schemas (app/schemas.py)
  5. Router registration (app/main.py, app/routes/__init__.py)
  6. LLM service integration (app/services/llm.py)

Frontend Integration (Steps 7-13):
  7. TypeScript types (frontend/src/types/prompt.ts)
  8. API client (frontend/src/services/promptsApi.ts)
  9. PromptSelector component (frontend/src/components/ui/PromptSelector.tsx)
  10. PromptManagement page (frontend/src/pages/PromptManagement.tsx)
  11. GuestSearch integration (frontend/src/pages/GuestSearch.tsx)
  12. API client updates (frontend/src/services/api.ts)
  13. PerformanceTesting + App.tsx integration

Migration & Polish (Steps 14-15):
  14. Seed default prompts (app/services/prompts.py)
  15. Navigation updates (frontend/src/components/Header.tsx)
```

## Tasks

### Phase 1: Backend — Database Model

#### 1.1 — Add `PromptVersion` model to `app/models.py`
**File**: `backend/app/models.py`
**Dependencies**: None (modifies existing file)
**Description**: Append `PromptVersion` class after `PerformanceTestResult`. Uses existing `Base`, `Mapped`, `mapped_column` imports.

**Implementation**:
```python
class PromptVersion(Base):
    __tablename__ = "prompt_versions"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    prompt_id: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    intention: Mapped[str] = mapped_column(Text, nullable=False)
    restrictions: Mapped[str] = mapped_column(Text, nullable=False)
    output_structure: Mapped[str] = mapped_column(Text, nullable=False)
    user_prompt_template: Mapped[str] = mapped_column(Text, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    metadata: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        UniqueConstraint("prompt_id", "version", name="uq_prompt_version"),
    )
```

---

### Phase 2: Backend — Pydantic Schemas

#### 2.1 — Add prompt schemas to `app/schemas.py`
**File**: `backend/app/schemas.py`
**Dependencies**: Phase 1 (PromptVersion model exists)
**Description**: After `GuestSearchResponse` (line ~131), add 6 new schema classes. Modify `GuestSearchRequest` to add `prompt_id` and `version` fields.

**Schemas added**:
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
    is_default: bool
    metadata: dict | None = None
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}

class PromptSummarySchema(BaseModel):
    """Summary for listing prompt IDs."""
    prompt_id: str
    default_version: int
    version_count: int
    name: str

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
```

**Modification to `GuestSearchRequest`**:
```python
# Add these fields:
prompt_id: str = "guest-search"
version: int | None = None
```

---

### Phase 3: Backend — PromptStore Service

#### 3.1 — Create `app/services/prompts.py`
**File**: `backend/app/services/prompts.py` (NEW)
**Dependencies**: Phase 1 (model), Phase 2 (schemas)
**Description**: Implement `PromptStore` class — database-backed CRUD for prompt versions. Uses singleton pattern with `SessionLocal()` for database access.

**Key methods**:

| Method | Signature | Purpose |
|--------|-----------|---------|
| `create_prompt` | `(self, prompt_id, name, intention, restrictions, output_structure, user_prompt_template, metadata) -> PromptVersion` | Create v1 of a new prompt, auto-set as default |
| `get_prompt` | `(self, prompt_id, version=None) -> PromptVersion` | Get specific version or default if version is None |
| `list_prompts` | `(self, prompt_id) -> list[PromptVersion]` | List all versions ordered by version number |
| `list_all_prompts` | `(self) -> list[PromptSummarySchema]` | Summary of all prompt IDs |
| `update_prompt` | `(self, prompt_id, version, **kwargs) -> PromptVersion` | Update fields; update `updated_at` timestamp |
| `delete_prompt` | `(self, prompt_id, version) -> bool` | Delete version; if default, set next-lower as default |
| `duplicate_prompt` | `(self, prompt_id, version, name) -> PromptVersion` | Copy version content to version+1 |
| `set_default` | `(self, prompt_id, version) -> PromptVersion` | Unset all defaults for prompt_id, set specified as default |
| `get_default_prompt` | `(self, prompt_id) -> PromptVersion` | Get the default version |
| `seed_default_prompts` | `(self) -> None` | On startup: if empty, seed from `app/services/llm.py` hardcoded prompts |

**Design decisions**:
- Singleton pattern: created once at module level, reused across requests
- Thread-safe: uses SQLAlchemy's existing session isolation
- Auto-increments version: `next_version = max(v.version for v in versions) + 1`
- Default cascade: when deleting a default version, the next-lower version becomes default
- Migration seed: `seed_default_prompts()` splits the current `SHARED_SYSTEM_PROMPT` and user prompt from `llm.py` into the 4 structured fields

---

### Phase 4: Backend — API Routes

#### 4.1 — Create `app/routes/prompts.py`
**File**: `backend/app/routes/prompts.py` (NEW)
**Dependencies**: Phase 3 (PromptStore service)
**Description**: Implement 9 FastAPI route handlers. Each handler creates a `PromptStore()`, calls the appropriate method, returns JSONResponse. Register with `router = APIRouter()`.

**Endpoints**:

| Route | Method | Purpose |
|-------|--------|---------|
| `/api/prompts` | GET | List summary of all prompt IDs |
| `/api/prompts/{prompt_id}` | GET | List all versions for a prompt |
| `/api/prompts/{prompt_id}/default` | GET | Get default version |
| `/api/prompts/{prompt_id}/{version}` | GET | Get specific version |
| `/api/prompts/{prompt_id}` | POST | Create new version (auto-increments) |
| `/api/prompts/{prompt_id}/{version}` | PUT | Update existing version |
| `/api/prompts/{prompt_id}/{version}` | DELETE | Delete version |
| `/api/prompts/{prompt_id}/{version}/duplicate` | POST | Duplicate as next version |
| `/api/prompts/{prompt_id}/{version}/set-default` | PATCH | Set as default |

**Handler signatures**:
```python
@router.get("/api/prompts")
async def list_all_prompts(store: PromptStore = Depends(PromptStore)) -> list[dict]: ...

@router.get("/api/prompts/{prompt_id}")
async def list_versions(prompt_id: str, store: PromptStore = Depends(PromptStore)) -> list[dict]: ...

@router.get("/api/prompts/{prompt_id}/default")
async def get_default(prompt_id: str, store: PromptStore = Depends(PromptStore)) -> dict: ...

@router.get("/api/prompts/{prompt_id}/{version}")
async def get_version(prompt_id: str, version: int, store: PromptStore = Depends(PromptStore)) -> dict: ...

@router.post("/api/prompts/{prompt_id}")
async def create_version(prompt_id: str, body: CreatePromptRequest, store: PromptStore = Depends(PromptStore)) -> dict: ...

@router.put("/api/prompts/{prompt_id}/{version}")
async def update_version(prompt_id: str, version: int, body: UpdatePromptRequest, store: PromptStore = Depends(PromptStore)) -> dict: ...

@router.delete("/api/prompts/{prompt_id}/{version}")
async def delete_version(prompt_id: str, version: int, store: PromptStore = Depends(PromptStore)) -> dict: ...

@router.post("/api/prompts/{prompt_id}/{version}/duplicate")
async def duplicate_version(prompt_id: str, version: int, body: DuplicatePromptRequest, store: PromptStore = Depends(PromptStore)) -> dict: ...

@router.patch("/api/prompts/{prompt_id}/{version}/set-default")
async def set_default_version(prompt_id: str, version: int, store: PromptStore = Depends(PromptStore)) -> dict: ...
```

---

### Phase 5: Backend — Router Registration & LLM Integration

#### 5.1 — Wire up routes in `app/main.py` and `app/routes/__init__.py`
**Files**: `backend/app/main.py`, `backend/app/routes/__init__.py`
**Dependencies**: Phase 4 (routes file exists)
**Description**: Add import and include for `prompts_router`.

```python
# In app/main.py:
from app.routes.prompts import router as prompts_router
app.include_router(prompts_router)

# In app/routes/__init__.py:
from .prompts import router as prompts_router
__all__ = [..., "prompts_router"]
```

#### 5.2 — Modify `app/services/llm.py`
**File**: `backend/app/services/llm.py`
**Dependencies**: Phase 3 (PromptStore), Phase 5.1 (routes registered)
**Description**: Update `query_guest_with_llm()` to accept `prompt_id` (default `"guest-search"`) and `version` (default `None`). Resolve from `PromptStore`. Build system prompt from the 3 structured fields (`intention + restrictions + output_structure`).

**Changes**:
```python
# Old signature:
async def query_guest_with_llm(query: str, ...):

# New signature:
async def query_guest_with_llm(query: str, prompt_id: str = "guest-search", version: int | None = None, ...):
    store = PromptStore()
    prompt = store.get_prompt(prompt_id, version)
    system_prompt = f"{prompt.intention}\n\n{prompt.restrictions}\n\n{prompt.output_structure}"
    # ... rest of function using system_prompt
```

---

### Phase 6: Frontend — TypeScript Types

#### 6.1 — Create `frontend/src/types/prompt.ts`
**File**: `frontend/src/types/prompt.ts` (NEW)
**Dependencies**: None
**Description**: Copy all TypeScript interfaces for prompt-related types.

```typescript
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

### Phase 7: Frontend — API Client

#### 7.1 — Create `frontend/src/services/promptsApi.ts`
**File**: `frontend/src/services/promptsApi.ts` (NEW)
**Dependencies**: Phase 6 (types defined)
**Description**: Implement all 9 API methods using existing `request` helper pattern from `api.ts`.

```typescript
import { request } from './api';
import type { PromptVersion, PromptSummary, CreatePromptRequest, UpdatePromptRequest, DuplicatePromptRequest } from '../types/prompt';

export const promptsApi = {
  listAll: () => request<PromptSummary[]>('/api/prompts'),
  listVersions: (promptId: string) => request<PromptVersion[]>(`/api/prompts/${promptId}`),
  getDefault: (promptId: string) => request<PromptVersion>(`/api/prompts/${promptId}/default`),
  getVersion: (promptId: string, version: number) => request<PromptVersion>(`/api/prompts/${promptId}/${version}`),
  create: (promptId: string, body: CreatePromptRequest) => request<PromptVersion>(`/api/prompts/${promptId}`, { method: 'POST', body }),
  update: (promptId: string, version: number, body: UpdatePromptRequest) => request<PromptVersion>(`/api/prompts/${promptId}/${version}`, { method: 'PUT', body }),
  delete: (promptId: string, version: number) => request<void>(`/api/prompts/${promptId}/${version}`, { method: 'DELETE' }),
  duplicate: (promptId: string, version: number, body: DuplicatePromptRequest) => request<PromptVersion>(`/api/prompts/${promptId}/${version}/duplicate`, { method: 'POST', body }),
  setDefault: (promptId: string, version: number) => request<PromptVersion>(`/api/prompts/${promptId}/${version}/set-default`, { method: 'PATCH' }),
};
```

---

### Phase 8: Frontend — PromptSelector Component

#### 8.1 — Create `frontend/src/components/ui/PromptSelector.tsx`
**File**: `frontend/src/components/ui/PromptSelector.tsx` (NEW)
**Dependencies**: Phase 7 (promptsApi)
**Reused Components**: `Select`, `FormField` from existing ui components
**Description**: Reusable dropdown component. Props: `promptId`, `value: { prompt_id, version? }`, `onChange`, `label`. Internally fetches versions from `promptsApi.listVersions(promptId)` and renders a `<Select>` with `<FormField>`.

**Props**:
```typescript
interface PromptSelectorProps {
  promptId: string;
  value?: { prompt_id: string; version?: number };
  onChange: (value: { prompt_id: string; version?: number }) => void;
  label: string;
}
```

#### 8.2 — Export PromptSelector from ui index
**File**: `frontend/src/components/ui/index.ts`
**Dependencies**: Phase 8.1 (PromptSelector created)
**Description**: Add export line:
```typescript
export { default as PromptSelector } from "./PromptSelector";
```

---

### Phase 9: Frontend — PromptManagement Page

#### 9.1 — Create `frontend/src/pages/PromptManagement.tsx`
**File**: `frontend/src/pages/PromptManagement.tsx` (NEW)
**Dependencies**: Phase 8 (PromptSelector), Phase 7 (promptsApi), Phase 6 (types)
**Reused Components**: `PageHeader`, `Card`, `Select`, `Textarea`, `FormField`, `Button`, `Badge`
**Description**: Full-page CRUD UI with 3 text areas (intention, restrictions, output_structure) + user prompt template.

**State**: `selectedPromptId`, `versions[]`, `editingVersion`, `editForm { name, intention, restrictions, output_structure, user_prompt_template }`

**Layout**:
```
┌───────────────────────────────────────────────────┐
│  PageHeader "Prompt Management"                   │
├───────────────────────────────────────────────────┤
│  ┌─ Prompt Selector ────────────────────────────┐ │
│  │  [Dropdown: select prompt ID + version]      │ │
│  └─────────────────────────────────────────────┘ │
├───────────────────────────────────────────────────┤
│  ┌─ Editor ─────────────────────────────────────┐ │
│  │  [Name input]                                │ │
│  │  [Textarea: intention]                       │ │
│  │  [Textarea: restrictions]                    │ │
│  │  [Textarea: output_structure]                │ │
│  │  [Textarea: user_prompt_template]            │ │
│  │  [Preview panel combining system prompt]     │ │
│  │  [Save / Duplicate / Delete buttons]         │ │
│  └─────────────────────────────────────────────┘ │
├───────────────────────────────────────────────────┤
│  ┌─ Actions ────────────────────────────────────┐ │
│  │  [Create New Prompt button]                  │ │
│  └─────────────────────────────────────────────┘ │
└───────────────────────────────────────────────────┘
```

---

### Phase 10: Frontend — Integration Pages

#### 10.1 — Modify `frontend/src/pages/GuestSearch.tsx`
**File**: `frontend/src/pages/GuestSearch.tsx`
**Dependencies**: Phase 9 (PromptSelector), Phase 7 (promptsApi)
**Description**: Add `PromptSelector` import and state. Pass `prompt_id`/`version` to `guestSearchApi.search()`.

#### 10.2 — Modify `frontend/src/services/api.ts`
**File**: `frontend/src/services/api.ts`
**Dependencies**: Phase 10.1 (needs API methods)
**Description**: 
- Update `guestSearchApi.search()` to accept optional `{ prompt_id, version }` options
- Add `promptsApi` object with all 9 methods (alternatively can keep in separate file and re-export)

#### 10.3 — Modify `frontend/src/pages/PerformanceTesting.tsx`
**File**: `frontend/src/pages/PerformanceTesting.tsx`
**Dependencies**: Phase 9 (PromptSelector), Phase 6 (types)
**Description**: Add prompt ID + version selectors. Load prompt content from store when selection changes. Pass `prompt_id`/`prompt_version` to test payload.

**Changes to `PerformanceTestRequest` type**:
```typescript
// In frontend/src/types/index.ts:
export interface PerformanceTestRequest {
  // ... existing fields
  prompt_id?: string;
  prompt_version?: number;
}
```

#### 10.4 — Modify `frontend/src/App.tsx`
**File**: `frontend/src/App.tsx`
**Dependencies**: Phase 9.1 (PromptManagement page exists)
**Description**: Import and add route for PromptManagement.

```typescript
import PromptManagement from './pages/PromptManagement';
// ... in Routes:
<Route path="/prompts" element={<PromptManagement />} />
```

---

### Phase 11: Migration & Polish

#### 11.1 — Implement `seed_default_prompts()`
**File**: `backend/app/services/prompts.py`
**Dependencies**: Phase 5.2 (llm.py modified)
**Description**: Back in `PromptStore`. Split `SHARED_SYSTEM_PROMPT` and the hardcoded user prompt from `llm.py` into the 4 structured fields. Called automatically if table is empty on startup.

```python
def seed_default_prompts(self) -> None:
    """Seed database with default prompts if prompt_versions table is empty."""
    existing = self.list_all_prompts()
    if existing:
        return  # Already seeded
    
    # Parse hardcoded prompts from llm.py and create structured entries
    self.create_prompt(
        prompt_id="guest-search",
        name="Guest Search Default",
        intention=...  # extracted from SHARED_SYSTEM_PROMPT
        restrictions=...  # extracted from SHARED_SYSTEM_PROMPT
        output_structure=...  # extracted from SHARED_SYSTEM_PROMPT
        user_prompt_template=...  # extracted from llm.py user prompt
    )
```

#### 11.2 — Update app navigation
**File**: `frontend/src/components/Header.tsx`
**Dependencies**: Phase 10.4 (route exists)
**Description**: Add "Prompt Management" link to navigation header.

---

## Execution Order Summary

| Order | Task | Depends On |
|-------|------|------------|
| 1 | 1.1 PromptVersion model | — |
| 2 | 2.1 Pydantic schemas | 1.1 |
| 3 | 3.1 PromptStore service | 1.1, 2.1 |
| 4 | 4.1 API routes | 3.1 |
| 5 | 5.1 Router registration | 4.1 |
| 6 | 5.2 LLM integration | 3.1, 5.1 |
| 7 | 6.1 TypeScript types | — |
| 8 | 7.1 promptsApi client | 6.1 |
| 9 | 8.1 PromptSelector component | 7.1 |
| 10 | 8.2 Export from ui/index | 8.1 |
| 11 | 9.1 PromptManagement page | 8.1, 7.1, 6.1 |
| 12 | 10.1 GuestSearch integration | 9.1, 7.1 |
| 13 | 10.2 API client updates | 10.1 |
| 14 | 10.3 PerformanceTesting integration | 9.1, 6.1 |
| 15 | 10.4 App.tsx route | 9.1 |
| 16 | 11.1 Seed default prompts | 5.2 |
| 17 | 11.2 Navigation update | 10.4 |

**Parallelizable tasks**:
- Phase 6-8 (Frontend types/API/components) can proceed in parallel with Phase 1-6 (Backend)
- Task 11.2 can be done anytime after 10.4

## Reused Components

| Component | Source | Used In |
|-----------|--------|---------|
| `Card` | `components/ui/Card.tsx` | PromptManagement page, PromptSelector |
| `Select` | `components/ui/Select.tsx` | PromptSelector, PromptManagement |
| `Textarea` | `components/ui/Textarea.tsx` | PromptManagement editor |
| `FormField` | `components/ui/FormField.tsx` | PromptSelector, PromptManagement |
| `Button` | `components/ui/Button.tsx` | PromptManagement actions |
| `Badge` | `components/ui/Badge.tsx` | PromptManagement default indicator |
| `PageHeader` | `components/ui/PageHeader.tsx` | PromptManagement page |
| `request` | `services/api.ts` | promptsApi client |

## API Reference

### Prompt REST Endpoints

| Method | Endpoint | Request Body | Response |
|--------|----------|--------------|----------|
| GET | `/api/prompts` | — | `PromptSummary[]` |
| GET | `/api/prompts/{prompt_id}` | — | `PromptVersion[]` |
| GET | `/api/prompts/{prompt_id}/default` | — | `PromptVersion` |
| GET | `/api/prompts/{prompt_id}/{version}` | — | `PromptVersion` |
| POST | `/api/prompts/{prompt_id}` | `CreatePromptRequest` | `PromptVersion` |
| PUT | `/api/prompts/{prompt_id}/{version}` | `UpdatePromptRequest` | `PromptVersion` |
| DELETE | `/api/prompts/{prompt_id}/{version}` | — | `void` |
| POST | `/api/prompts/{prompt_id}/{version}/duplicate` | `DuplicatePromptRequest` | `PromptVersion` |
| PATCH | `/api/prompts/{prompt_id}/{version}/set-default` | — | `PromptVersion` |

## Testing Requirements

### Backend Tests (`tests/test_prompts.py`)

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

## Differences from Plan

This section documents all differences between this implementation plan document and the **actual implemented codebase**.

### Backend — Database Model

#### 1.1 — `PromptVersion` model: column name `metadata` → `meta_json`
**Plan**: Column named `metadata` with Python type `Mapped[str | None]` and Pydantic field `metadata: dict | None = None`
**Actual**: Column named `meta_json` (to avoid SQLAlchemy/Pydantic conflict with Python's built-in `metadata`). The Pydantic schema exposes `metadata` as a computed property via `model_config = {"from_attributes": True}`, but the raw DB column is `meta_json` and stores JSON-encoded strings

#### 1.1 — Table name case
**Plan**: `__tablename__ = "prompt_versions"` (lowercase)
**Actual**: `__tablename__ = "PromptVersions"` (PascalCase, consistent with other tables in the project like `PromptGroups`, `PerformanceTestResults`)

---

### Backend — Schemas

#### 2.1 — `PromptVersionSchema` datetime format
**Plan**: `created_at: datetime` and `updated_at: datetime` (Python datetime objects)
**Actual**: `created_at: str` and `updated_at: str` (ISO 8601 string representation, serialized by FastAPI)

#### 2.1 — `GuestSearchRequest` additional field
**Plan**: Added `prompt_id: str = "guest-search"` and `version: int | None = None`
**Actual**: Also includes `runtime_variables: Dict[str, str] = Field(default_factory=dict, description="Runtime variables for {table.field} placeholders in the user_prompt")` — placeholder resolution support added beyond the plan

#### 2.1 — `PerformanceTestRequest` field naming
**Plan**: `prompt_id?: string` and `prompt_version?: number` in TypeScript; Python `prompt_id` and `version`
**Actual**: Python uses `prompt_id: str | None` and `prompt_version: int | None` (both nullable, both named `prompt_version` consistently across backend and frontend)

---

### Backend — PromptStore Service

#### 3.1 — `create_prompt` parameter: `metadata` → `metadata_dict`
**Plan**: Method signature included `metadata: dict | None = None`
**Actual**: Parameter renamed to `metadata_dict: dict | None = None` to avoid naming conflict, and the value is JSON-encoded via `json.dumps(metadata_dict)` before storing in `meta_json` column

#### 3.1 — `resolve_prompt()` method added
**Plan**: No `resolve_prompt()` method specified
**Actual**: Added `resolve_prompt(prompt_id, version) -> tuple[str, str]` that returns `(system_prompt, user_prompt_template)` and integrates with `app.services.placeholders.resolve_placeholders()` for runtime `{table.field}` placeholder substitution

#### 3.1 — Timestamp timezone
**Plan**: `default=datetime.utcnow` (naive UTC timestamps)
**Actual**: Uses `datetime.now(timezone.utc)` for timezone-aware timestamps throughout the service

#### 3.1 — Seed content structure
**Plan**: Seed splits `SHARED_SYSTEM_PROMPT` into intention, restrictions, output_structure fields
**Actual**: Seeds with `intention=SHARED_SYSTEM_PROMPT` and empty `restrictions=""` and `output_structure=""`. The `meta_json` includes migration metadata with `author`, `migrated_from`, and `changelog` fields

---

### Backend — LLM Integration

#### 5.2 — `query_guest_with_llm` function signature
**Plan**: `async def query_guest_with_llm(query: str, prompt_id: str = "guest-search", version: int | None = None, ...)`
**Actual**: `def query_guest_with_llm(customer_name: str, prompt_id: str = "guest-search", version: int | None = None, runtime_variables: dict | None = None, ...)` — uses positional `customer_name` instead of `query`, and includes `runtime_variables` for placeholder resolution

#### 5.2 — Fallback behavior
**Plan**: Direct prompt resolution from PromptStore
**Actual**: Includes try/except fallback — if prompt not found, falls back to hardcoded `SHARED_SYSTEM_PROMPT` and legacy user prompt template

#### 5.2 — Placeholder resolution
**Plan**: No mention of placeholder resolution
**Actual**: Integrates with `app.services.placeholders.resolve_all_placeholders()` to resolve `{table.field}` patterns (e.g., `customers.first_name`, `customers.last_name`, `customers.name`) from `customer_name` at query time

---

### Frontend — TypeScript Types

#### 6.1 — Additional types added
**Plan**: Only versioned prompt types (`PromptVersion`, `PromptSummary`, `CreatePromptRequest`, `UpdatePromptRequest`, `DuplicatePromptRequest`)
**Actual**: Also includes prompt group types: `PromptGroupItem`, `PromptGroup`, `PromptGroupSchedule`, `PromptGroupResult` — for batch prompt group operations beyond versioning

---

### Frontend — API Client

#### 7.1 — Function-style exports vs object pattern
**Plan**: Single `promptsApi` object with all methods
**Actual**: Both — individual named function exports (`listAllPrompts`, `listVersions`, etc.) **and** a re-exported `promptsApi` object for backward compatibility

#### 7.1 — Additional methods added
**Plan**: 9 CRUD methods only
**Actual**: Also includes:
- `aiImprove(section, currentText, conversation, model)` — AI-powered prompt improvement via chat
- `listPlaceholders()` — fetch available `{table.field}` placeholders
- `previewPrompt(promptId, version)` — POST endpoint for previewing resolved prompts
- `getFieldSchema()` — fetch database field schema for runtime variable discovery
- `getPrompt()` — alias for `getVersion()`

#### 7.1 — Custom `request` helper
**Plan**: Use existing `request` helper from `api.ts`
**Actual**: Defines its own local `request<T>()` helper with custom error handling (reads response body on error)

---

### Frontend — Integration

#### 10.2 — `guestSearchApi` modification
**Plan**: Update `guestSearchApi.search()` to accept optional `{ prompt_id, version }`
**Actual**: The `GuestSearchRequest` schema handles this on the backend; the frontend passes these through the request body. The `api.ts` modifications follow the existing pattern rather than restructuring the search method

---

### Additional Features Beyond Plan

The following features were implemented but not specified in the original plan:

| Feature | Description |
|---------|-------------|
| **Placeholder Resolution** | `{table.field}` runtime variable substitution in user prompt templates, with `{customers.first_name}`, `{customers.last_name}`, `{customers.name}` auto-derived from `customer_name` |
| **AI Prompt Improvement** | `aiImprove()` endpoint and chat interface for improving prompt sections via LLM |
| **Placeholder Palette** | `listPlaceholders()` and `getFieldSchema()` endpoints for discovering available `{table.field}` patterns |
| **Prompt Preview** | `/api/prompts/{prompt_id}/{version}/preview` POST endpoint for previewing resolved prompts |
| **Prompt Groups** | Full prompt group infrastructure (`PromptGroupItem`, `PromptGroup`, `PromptGroupSchedule`, `PromptGroupResult`) for batch operations |
| **Response Caching** | `response_cache_middleware.py` integration with `call_llm_with_db_tools_with_cache_flag()` for caching LLM responses with checksums |
| **Runtime Variables** | `runtime_variables` field in both `GuestSearchRequest` and `PerformanceTestRequest` for dynamic placeholder resolution |
| **Error Handling Fallback** | `query_guest_with_llm` falls back to hardcoded prompts if no database prompt is found |

---

*All core functionality from the original plan was implemented. The differences above are enhancements, naming conventions, and additional features added during implementation.*