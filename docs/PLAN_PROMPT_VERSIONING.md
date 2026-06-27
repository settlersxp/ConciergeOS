# Plan: Versioned Prompt System for Guest Search

> **Status**: Planned — Awaiting Implementation
> **Created**: 2026-06-27
> **Last Updated**: 2026-06-27

---

## 1. Overview

Refactor the project to version all prompts used by the application. Each prompt is identified by a unique `prompt_id` and `version` integer, stored in the SQLite database, and managed from the frontend.

### Design Goals

1. **Versioned prompts**: Each prompt has `{prompt_id}:v{version}` — e.g., `guest-search:v3`
2. **Generic system**: Supports multiple prompt types (guest-search, reservation-query, summary-report, etc.)
3. **Database-backed**: Stored in SQLite for robustness and concurrency
4. **Frontend-managed**: Full CRUD UI for prompt management
5. **Single-user**: No ownership/collaboration features needed
6. **Rollback via selection**: Users select an older version from the list

---

## 2. Current State Analysis

The guest search prompt is **hardcoded** in `app/services/llm.py` (line 589):

```python
user_prompt = f"Please find all information about the guest named. The guest's name can have it's name translated into the following languages Arabic, Chinese, Devanagari, Japanese, Jorean, Latin or Nordic. It is unclear if is the user's first name or last name. Retry once with every translated language if needed. Also bring the information about its reservations. : {customer_name}"
```

The system prompt (`SHARED_SYSTEM_PROMPT`) is also hardcoded at module level in `app/services/llm.py` (lines 159-195).

The frontend `GuestSearch.tsx` only sends `customer_name` — no prompt selection or versioning.

---

## 3. Database Schema

### New Table: `prompt_versions`

```sql
CREATE TABLE prompt_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prompt_id TEXT NOT NULL,              -- e.g., "guest-search", "reservation-query"
    version INTEGER NOT NULL,             -- 1, 2, 3...
    name TEXT NOT NULL,                   -- Human-readable, e.g., "Guest Search v1"
    intention TEXT NOT NULL,              -- The intention/purpose of the prompt (system prompt base)
    restrictions TEXT NOT NULL,           -- Rules, constraints, and restrictions
    output_structure TEXT NOT NULL,       -- Expected output format and structure
    user_prompt_template TEXT NOT NULL,   -- Final user-facing template with placeholders
    combined_system_prompt TEXT GENERATED ALWAYS AS (
        -- Computed column: concatenation of intention + restrictions for LLM system message
        CASE 
            WHEN intention != '' AND restrictions != '' THEN intention || '\n\n' || restrictions
            WHEN intention != '' THEN intention
            WHEN restrictions != '' THEN restrictions
            ELSE ''
        END
    ),
    is_default BOOLEAN NOT NULL DEFAULT 0,
    metadata TEXT,                        -- JSON blob (author, changelog, tags)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(prompt_id, version)
);

-- Indexes for efficient lookups
CREATE INDEX idx_prompt_versions_lookup ON prompt_versions(prompt_id, version);
CREATE INDEX idx_prompt_versions_default ON prompt_versions(prompt_id, is_default);
```

### Prompt ID Convention

Use kebab-case identifiers:
- `guest-search` — Guest search prompt
- `reservation-query` — Reservation query prompt
- `summary-report` — Summary report prompt

### Prompt Structure

Each prompt is composed of 3 editable sections that are combined at runtime:

| Field | Purpose | LLM Role | Example |
|-------|---------|----------|---------|
| **Intention** | What the assistant should do | System prompt prefix | "You are a helpful hotel concierge assistant..." |
| **Restrictions** | Rules, constraints, formatting rules | System prompt suffix | "Always format dates as YYYY-MM-DD. Never guess..." |
| **Output Structure** | Expected response format | Appended to system prompt | "Use this structure: ### Guest #1..." |
| **User Prompt Template** | Dynamic user message | Sent as user message | "Find all information about: {customer_name}" |

The `combined_system_prompt` is computed from Intention + Restrictions + Output Structure and used as the system message in LLM calls.

---

## 4. Backend Implementation

### 4.1 New Files

#### `app/services/prompts.py` — Prompt Store

```python
# Key classes and functions:

class PromptStore:
    """Database-backed prompt version store."""
    
    def __init__(self, db_session_factory): ...
    
    def create_prompt(
        self,
        prompt_id: str,
        name: str,
        system_prompt: str,
        user_prompt_template: str,
        metadata: dict = None
    ) -> PromptVersion:
        """Create first version (v1) of a new prompt. Auto-sets as default."""
        ...
    
    def get_prompt(
        self,
        prompt_id: str,
        version: int = None
    ) -> PromptVersion:
        """Get a specific version, or the default if version is None."""
        ...
    
    def list_prompts(self, prompt_id: str) -> list[PromptVersion]:
        """List all versions for a prompt ID, ordered by version number."""
        ...
    
    def update_prompt(
        self,
        prompt_id: str,
        version: int,
        name: str = None,
        system_prompt: str = None,
        user_prompt_template: str = None,
        metadata: dict = None
    ) -> PromptVersion:
        """Update an existing prompt version."""
        ...
    
    def delete_prompt(self, prompt_id: str, version: int) -> bool:
        """Delete a version. If it was default, set next-lower as default."""
        ...
    
    def duplicate_prompt(
        self,
        prompt_id: str,
        version: int
    ) -> PromptVersion:
        """Duplicate a version, creating version+1 with copied content."""
        ...
    
    def set_default(self, prompt_id: str, version: int) -> PromptVersion:
        """Set a specific version as the default for this prompt_id."""
        ...
    
    def get_default_prompt(self, prompt_id: str) -> PromptVersion:
        """Get the default version for a prompt ID."""
        ...
    
    def seed_default_prompts(self) -> None:
        """On startup: if no prompts exist, seed from current hardcoded prompts."""
        ...
```

#### `app/routes/prompts.py` — API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/prompts` | List all prompt IDs (summary) |
| GET | `/api/prompts/{prompt_id}` | List all versions for a prompt ID |
| GET | `/api/prompts/{prompt_id}/default` | Get the default version (resolved) |
| GET | `/api/prompts/{prompt_id}/{version}` | Get specific version |
| POST | `/api/prompts/{prompt_id}` | Create new version (auto-increments) |
| PUT | `/api/prompts/{prompt_id}/{version}` | Update existing version |
| DELETE | `/api/prompts/{prompt_id}/{version}` | Delete a version |
| POST | `/api/prompts/{prompt_id}/{version}/duplicate` | Duplicate (creates next version) |
| PATCH | `/api/prompts/{prompt_id}/{version}/set-default` | Set as default |

Register in `app/main.py`:
```python
from app.routes.prompts import router as prompts_router
app.include_router(prompts_router)
```

### 4.2 Modified Files

#### `app/models.py` — Add SQLAlchemy Model

```python
class PromptVersion(Base):
    __tablename__ = "prompt_versions"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    prompt_id: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    user_prompt_template: Mapped[str] = mapped_column(Text, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    metadata: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        UniqueConstraint("prompt_id", "version", name="uq_prompt_version"),
    )
```

#### `app/schemas.py` — Add Schemas

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
    name: str | None = None  # Override name for duplicated version

class SetDefaultRequest(BaseModel):
    version: int

class GuestSearchRequest(BaseModel):
    customer_name: str
    prompt_id: str = "guest-search"    # NEW: optional, defaults to guest-search
    version: int | None = None          # NEW: optional, uses default if None
```

#### `app/services/llm.py` — Prompt Resolution

Update `query_guest_with_llm()` signature:

```python
def query_guest_with_llm(
    customer_name: str,
    prompt_id: str = "guest-search",
    version: int = None
) -> tuple[str, bool]:
    """
    Query the LLM using a versioned prompt.
    
    If prompt_id is provided, resolves the prompt template from the store.
    Falls back to hardcoded behavior if no prompt is found.
    
    The system prompt is composed from: intention + restrictions + output_structure
    The user message is composed from: user_prompt_template.format(customer_name=...)
    """
    from app.services.prompts import PromptStore
    
    store = PromptStore()
    
    if prompt_id:
        prompt_version = store.get_prompt(prompt_id, version)
        # Build system prompt from structured fields
        parts = []
        if prompt_version.intention:
            parts.append(prompt_version.intention)
        if prompt_version.restrictions:
            parts.append(prompt_version.restrictions)
        if prompt_version.output_structure:
            parts.append(prompt_version.output_structure)
        system_prompt = "\n\n".join(parts) if parts else SHARED_SYSTEM_PROMPT
        user_prompt = prompt_version.user_prompt_template.replace(
            "{customer_name}", customer_name
        )
    else:
        # Legacy fallback
        system_prompt = SHARED_SYSTEM_PROMPT
        user_prompt = f"Please find all information about the guest named... : {customer_name}"
    
    # ... rest of existing implementation
```

#### `app/routes/guest_search.py` — Accept Prompt Params

```python
@router.post("/api/guest-search")
async def api_guest_search(body: GuestSearchRequest) -> GuestSearchResponse:
    llm_response, was_cached = query_guest_with_llm(
        body.customer_name,
        prompt_id=body.prompt_id,
        version=body.version
    )
    return GuestSearchResponse(
        query=body.customer_name,
        llm_response=llm_response,
        cached=was_cached,
    )
```

---

## 5. Frontend Implementation

> **Design Principle**: All frontend components must reuse existing global styles and reusable UI components from `frontend/src/components/ui/`. This ensures visual consistency across the application.

### Existing Reusable Components (from `frontend/src/components/ui/`)

| Component | Export | Usage |
|-----------|--------|-------|
| `Card` | `./Card` | Container with title/description support |
| `Button` | `./Button` | Primary/secondary variants with loading state |
| `Input` | `./Input` | Styled text input with FormField wrapper |
| `Textarea` | `./Textarea` | Styled textarea with FormField wrapper |
| `Select` | `./Select` | Styled dropdown select |
| `FormField` | `./FormField` | Label + error + helper text wrapper |
| `PageHeader` | `./PageHeader` | Page title + description header |
| `Badge` | `./Badge` | Status badges |
| `Toast` | `./Toast` | Inline notifications |
| `RoomCard` | `./RoomCard` | Room display card (not relevant here) |

All new components should:
- Use the same Tailwind CSS color tokens (`primary-*`, `secondary-*`, `surface-*`)
- Support dark mode via `dark:` prefixes
- Wrap form inputs in `<FormField>` for consistent labeling
- Use `<Card>` for section containers
- Import from `../../components/ui` using the existing barrel export pattern

### 5.1 New Files

#### `frontend/src/types/prompt.ts`

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

#### `frontend/src/services/promptsApi.ts`

```typescript
import type {
  PromptVersion,
  PromptSummary,
  CreatePromptRequest,
  UpdatePromptRequest,
  DuplicatePromptRequest,
} from '../types/prompt';

/** Generic fetch helper that parses JSON responses */
async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const resp = await fetch(url, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!resp.ok) {
    const body = await resp.text().catch(() => '');
    throw new Error(resp.statusText + (body ? `: ${body}` : ''));
  }
  const text = await resp.text();
  return text ? (JSON.parse(text) as T) : ({} as T);
}

export const promptsApi = {
  listAll: (): Promise<PromptSummary[]> =>
    request<PromptSummary[]>('/api/prompts'),

  listVersions: (promptId: string): Promise<PromptVersion[]> =>
    request<PromptVersion[]>(`/api/prompts/${promptId}`),

  getDefault: (promptId: string): Promise<PromptVersion> =>
    request<PromptVersion>(`/api/prompts/${promptId}/default`),

  getByVersion: (promptId: string, version: number): Promise<PromptVersion> =>
    request<PromptVersion>(`/api/prompts/${promptId}/${version}`),

  create: (promptId: string, data: CreatePromptRequest): Promise<PromptVersion> =>
    request<PromptVersion>(`/api/prompts/${promptId}`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  update: (
    promptId: string,
    version: number,
    data: UpdatePromptRequest,
  ): Promise<PromptVersion> =>
    request<PromptVersion>(`/api/prompts/${promptId}/${version}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  delete: (promptId: string, version: number): Promise<Record<string, unknown>> =>
    request<Record<string, unknown>>(`/api/prompts/${promptId}/${version}`, {
      method: 'DELETE',
    }),

  duplicate: (
    promptId: string,
    version: number,
    data?: DuplicatePromptRequest,
  ): Promise<PromptVersion> =>
    request<PromptVersion>(`/api/prompts/${promptId}/${version}/duplicate`, {
      method: 'POST',
      body: data ? JSON.stringify(data) : undefined,
    }),

  setDefault: (
    promptId: string,
    version: number,
  ): Promise<PromptVersion> =>
    request<PromptVersion>(`/api/prompts/${promptId}/${version}/set-default`, {
      method: 'PATCH',
    }),
};
```

#### `frontend/src/components/ui/PromptSelector.tsx`

Dropdown component for selecting prompt versions. Reuses the existing `<Select>` and `<FormField>` components for consistent styling.

```typescript
import { useEffect, useState } from "react";
import { Select, FormField } from "../../components/ui";
import { promptsApi } from "../../services/promptsApi";
import type { PromptVersion } from "../../types/prompt";

interface PromptSelectorProps {
  promptId: string;
  value?: { prompt_id: string; version?: number };
  onChange: (value: { prompt_id: string; version?: number }) => void;
  label?: string;
}

export default function PromptSelector({
  promptId,
  value,
  onChange,
  label = "Prompt",
}: PromptSelectorProps) {
  const [versions, setVersions] = useState<PromptVersion[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    promptsApi
      .listVersions(promptId)
      .then(setVersions)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [promptId]);

  const selectedVersion = value?.version;
  const defaultValueText = versions.find((v) => v.is_default)?.version;

  return (
    <FormField htmlFor={`promptSelector-${promptId}`} label={label}>
      <Select
        id={`promptSelector-${promptId}`}
        value={selectedVersion ?? ""}
        onChange={(e) => {
          const v = e.target.value;
          onChange({ prompt_id: promptId, version: v ? Number(v) : undefined });
        }}
        disabled={loading}
      >
        {versions.length === 0 ? (
          <option value="">No prompts available</option>
        ) : (
          versions.map((p) => (
            <option key={p.id} value={p.version}>
              v{p.version} — {p.name}
              {p.is_default ? " (default)" : ""}
            </option>
          ))
        )}
      </Select>
    </FormField>
  );
}
```

#### `frontend/src/pages/PromptManagement.tsx`

Full-page prompt manager. Uses `<Card>`, `<Button>`, `<Textarea>`, `<FormField>`, `<Badge>`, and `<PageHeader>` from `frontend/src/components/ui`.

```
┌───────────────────────────────────────────────────────────┐
│  Prompt Management                                        │
│  Manage versioned prompts used across the application.    │
├───────────────────────────────────────────────────────────┤
│  Prompt ID: [guest-search    ▼]  [+ Create New Version]  │
├───────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────┐  │
│  │ Name           │ Version │ Default  │ Actions        │  │
│  ├─────────────────────────────────────────────────────┤  │
│  │ Guest Search   │ v1      │ ★ Default│ [Edit] [Dup]  │  │
│  │ Guest Search   │ v2      │          │ [Edit] [Dup]  │  │
│  │ Guest Search   │ v3      │ ★ Default│ [Edit] [Dup]  │  │
│  └─────────────────────────────────────────────────────┘  │
│                                                           │
│  ── Edit: Guest Search v3 ──────────────────────────────  │
│                                                           │
│  Display Name                                             │
│  ┌─────────────────────────────────────────────────────┐  │
│  │ Guest Search v3                                     │  │
│  └─────────────────────────────────────────────────────┘  │
│                                                           │
│  Intention (System Prompt — Purpose)                     │
│  ┌─────────────────────────────────────────────────────┐  │
│  │ You are a helpful hotel concierge assistant...     │  │
│  │ You have access to database query tools...         │  │
│  └─────────────────────────────────────────────────────┘  │
│                                                           │
│  Restrictions (Rules & Constraints)                      │
│  ┌─────────────────────────────────────────────────────┐  │
│  │ Always format dates as YYYY-MM-DD...               │  │
│  │ Never guess at data...                             │  │
│  │ If information is not found, say so clearly...     │  │
│  └─────────────────────────────────────────────────────┘  │
│                                                           │
│  Output Structure (Expected Response Format)             │
│  ┌─────────────────────────────────────────────────────┐  │
│  │ ### Guest [Number] (ID: [ID])                       │  │
│  │ * **Full Name:** [First] [Last]                    │  │
│  │ * **Date of Birth:** [YYYY-MM-DD]                  │  │
│  │ ...                                                  │  │
│  └─────────────────────────────────────────────────────┘  │
│                                                           │
│  User Prompt Template (Dynamic Message)                  │
│  ┌─────────────────────────────────────────────────────┐  │
│  │ Please find all information about: {customer_name} │  │
│  └─────────────────────────────────────────────────────┘  │
│                                                           │
│  Preview (combined system prompt + resolved user msg)     │
│  ┌─────────────────────────────────────────────────────┐  │
│  │ System: You are a helpful hotel concierge...       │  │
│  │        Always format dates...                      │  │
│  │        ### Guest [Number]...                       │  │
│  │ User: Please find all information about: John      │  │
│  └─────────────────────────────────────────────────────┘  │
│                                                           │
│  [Save Changes] [Cancel] [Set as Default] [Delete]       │
└───────────────────────────────────────────────────────────┘
```

### 5.2 Modified Frontend Files

#### `frontend/src/pages/GuestSearch.tsx`

Add `PromptSelector` to the page, reusing existing `<Card>`, `<FormField>`, `<Input>`, `<Button>` components:

```typescript
import { useState } from "react";
import { guestSearchApi } from "../services/api";
import { promptsApi } from "../services/promptsApi";
import type { GuestSearchResponse, PromptVersion } from "../types";
import { PageHeader, Card, FormField, Input, Button, Toast } from "../components/ui";
import PromptSelector from "../components/ui/PromptSelector";

export default function GuestSearch() {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<GuestSearchResponse | null>(null);
  const [toast, setToast] = useState<{ message: string; type: "success" | "error" | "info" } | null>(null);
  const [selectedPrompt, setSelectedPrompt] = useState<{ prompt_id: string; version?: number }>({
    prompt_id: "guest-search",
  });

  const handleSearch = async () => {
    if (!query.trim()) {
      setToast({ message: "Please enter a customer name", type: "error" });
      return;
    }
    setLoading(true);
    setResult(null);
    try {
      const data = await guestSearchApi.search(query, {
        prompt_id: selectedPrompt.prompt_id,
        version: selectedPrompt.version,
      });
      setResult(data);
    } catch (e: unknown) {
      setToast({ message: e instanceof Error ? e.message : "Search failed", type: "error" });
    } finally {
      setLoading(false);
    }
  };

  // ... rest unchanged
}
```

#### `frontend/src/services/api.ts`

```typescript
export const guestSearchApi = {
  search: (customerName: string, options?: { prompt_id?: string; version?: number }) =>
    request<GuestSearchResponse>('/api/guest-search', {
      method: 'POST',
      body: JSON.stringify({
        customer_name: customerName,
        prompt_id: options?.prompt_id ?? 'guest-search',
        version: options?.version,
      }),
    }),
};
```

#### `frontend/src/pages/PerformanceTesting.tsx`

Add a prompt selector dropdown for selecting the prompt to use during performance tests. Reuses existing `<Card>`, `<FormField>`, `<Select>` components:

Replace the current `PromptSettingsCard` usage with a hybrid that supports both prompt selection and inline editing:

```typescript
import PromptSelector from "../components/ui/PromptSelector";

// In component state:
const [selectedTestPrompt, setSelectedTestPrompt] = useState<{ prompt_id: string; version?: number }>({
  prompt_id: "guest-search",
});
const [overridePrompts, setOverridePrompts] = useState(false);

// In render, replace <PromptSettingsCard>:
<div className="mb-4">
  <FormField label="Test Prompt">
    <Select
      value={selectedTestPrompt.prompt_id}
      onChange={(e) => {
        const pid = e.target.value;
        setSelectedTestPrompt({ prompt_id: pid });
        setOverridePrompts(false);
        // Load default prompt content
        promptsApi.getDefault(pid).then((p) => {
          setSystemPrompt(p.system_prompt);
          setUserPrompt(p.user_prompt_template);
        }).catch(() => {});
      }}
    >
      <option value="guest-search">guest-search</option>
      {/* Dynamically loaded from /api/prompts */}
    </Select>
  </FormField>
  <FormField label="Prompt Version">
    <Select
      value={selectedTestPrompt.version ?? ""}
      onChange={(e) => {
        const v = e.target.value ? Number(e.target.value) : undefined;
        setSelectedTestPrompt({ ...selectedTestPrompt, version: v });
      }}
    >
      {/* Dynamically loaded based on selected prompt_id */}
    </Select>
  </FormField>
  <label className="flex items-center gap-2 text-sm text-primary-600">
    <input
      type="checkbox"
      checked={overridePrompts}
      onChange={(e) => setOverridePrompts(e.target.checked)}
    />
    Override prompt content
  </label>
</div>

// When override is enabled, show the existing PromptSettingsCard fields
{overridePrompts && (
  <PromptSettingsCard
    systemPrompt={systemPrompt}
    userPrompt={userPrompt}
    onSystemPromptChange={setSystemPrompt}
    onUserPromptChange={setUserPrompt}
  />
)}
```

Update the payload sent to `performanceApi.runTest()`:

```typescript
const payload: PerformanceTestRequest = {
  customer_name: customerName,
  // ... other fields ...
  system_prompt: overridePrompts ? systemPrompt : "",  // Empty = use stored prompt
  user_prompt: overridePrompts ? userPrompt : "",
  prompt_id: selectedTestPrompt.prompt_id,
  prompt_version: selectedTestPrompt.version,
};
```

#### `frontend/src/types/index.ts`

Add to existing types file (or use separate `prompt.ts`):

```typescript
export interface PerformanceTestRequest {
  // ... existing fields ...
  prompt_id?: string;
  prompt_version?: number;
}
```

#### `frontend/src/App.tsx`

Add route for PromptManagement page:

```typescript
import PromptManagement from './pages/PromptManagement';

// In router:
<Route path="/prompts" element={<PromptManagement />} />
```

---

## 6. Seed Data

On application startup, `PromptStore.seed_default_prompts()` checks if any prompts exist. If the database is empty, it seeds:

```python
# Default guest-search prompt from current hardcoded value
{
    "prompt_id": "guest-search",
    "version": 1,
    "name": "Guest Search v1",
    "system_prompt": SHARED_SYSTEM_PROMPT,  # From llm.py
    "user_prompt_template": "Please find all information about the guest named. ... : {customer_name}",
    "is_default": True,
}
```

---

## 7. Implementation Order

### Phase 1: Backend Foundation
1. Add `PromptVersion` model to `app/models.py` with 4 prompt fields (intention, restrictions, output_structure, user_prompt_template)
2. Create `app/services/prompts.py` with full CRUD operations
3. Create `app/routes/prompts.py` with all endpoints
4. Add prompt schemas to `app/schemas.py`
5. Modify `app/services/llm.py` — support prompt resolution from structured fields
6. Modify `app/routes/guest_search.py` — accept prompt_id/version

### Phase 2: Frontend Prompt Management
7. Create `frontend/src/types/prompt.ts` with 4 prompt fields
8. Create `frontend/src/services/promptsApi.ts`
9. Create `frontend/src/components/ui/PromptSelector.tsx`
10. Create `frontend/src/pages/PromptManagement.tsx` with 3 text areas (intention, restrictions, output_structure) + user prompt template
11. Modify `frontend/src/pages/GuestSearch.tsx` — add prompt selector
12. Modify `frontend/src/pages/PerformanceTesting.tsx` — add prompt selection dropdown
13. Add route in `frontend/src/App.tsx`

### Phase 3: Migration & Polish
14. Implement seed default prompts on startup (split existing hardcoded prompt into 3 sections)
15. Update app navigation to include Prompt Management link

---

## 8. Files Summary

### New Files (7)
| File | Purpose |
|------|---------|
| `app/services/prompts.py` | Prompt store with database CRUD |
| `app/routes/prompts.py` | REST API endpoints |
| `frontend/src/types/prompt.ts` | TypeScript interfaces |
| `frontend/src/services/promptsApi.ts` | Frontend API client |
| `frontend/src/components/ui/PromptSelector.tsx` | Prompt version dropdown |
| `frontend/src/pages/PromptManagement.tsx` | Full-page prompt manager (3 text areas) |
| `docs/PLAN_PROMPT_VERSIONING.md` | This file |

### Modified Files (8)
| File | Changes |
|------|---------|
| `app/models.py` | Add `PromptVersion` SQLAlchemy model with 4 prompt fields |
| `app/schemas.py` | Add prompt schemas with 4 prompt fields, update `GuestSearchRequest` |
| `app/services/llm.py` | Add prompt resolution from structured fields to `query_guest_with_llm` |
| `app/routes/guest_search.py` | Accept `prompt_id`/`version` in request |
| `app/main.py` | Include prompts router |
| `frontend/src/types/index.ts` | Add `prompt_id`/`prompt_version` to `PerformanceTestRequest` |
| `frontend/src/services/api.ts` | Add prompt params to search, add prompt API methods |
| `frontend/src/pages/GuestSearch.tsx` | Add prompt selector |
| `frontend/src/pages/PerformanceTesting.tsx` | Add prompt selection dropdown |
| `frontend/src/App.tsx` | Add PromptManagement route |

---

## 9. Open Questions (Resolved)

| Question | Decision |
|----------|----------|
| Storage mechanism | SQLite database |
| Generic vs single-purpose | Generic (supports multiple prompt types) |
| Access control | Single-user editing |
| Rollback mechanism | Select an older version from the dropdown |

---

## 10. Testing Checklist

### Backend
- [ ] Prompt creation with auto-version increment
- [ ] Prompt listing by prompt_id
- [ ] Default version resolution when version is None
- [ ] Version update persists correctly
- [ ] Delete lowest version sets next as default
- [ ] Duplicate creates version+1 with copied content
- [ ] Set default updates is_default flags
- [ ] Seed default prompts on empty database (split into 4 fields)
- [ ] Backward compatible: legacy calls still work
- [ ] System prompt combines intention + restrictions + output_structure correctly
- [ ] Prompt resolution in llm.py uses correct template

### Frontend
- [ ] Prompt selector loads available versions
- [ ] Creating new prompt increments version
- [ ] Editing a prompt saves all 4 fields
- [ ] Deleting a prompt removes it from list
- [ ] Duplicate creates new version
- [ ] GuestSearch sends selected prompt_id + version
- [ ] PromptManagement page shows 3 text areas + user prompt template
- [ ] Preview shows combined system prompt with resolved variables
- [ ] Set default updates default indicator
- [ ] PerformanceTesting page loads prompt from selection

---

*End of plan document.*