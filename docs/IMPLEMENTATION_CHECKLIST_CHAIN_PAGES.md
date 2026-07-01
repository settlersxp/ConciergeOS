# Implementation Checklist: Prompt Chain Pages

> **Created:** 2026-01-07
> **Purpose:** Single source of truth for implementation order, organized by dependency
> **Related:** [Design](./IMPLEMENTATION_PROMPT_CHAIN_PAGES.md) | [Spec](./IMPLEMENTATION_SPEC_CHAIN_PAGES.md)

---

## Execution Order Diagram

```
  Phase 1: Backend Models + Migration
       │
       ▼
  Phase 2: Backend Schemas + Placeholder Engine
       │
       ▼
  Phase 3: Backend Chain Execution + API Endpoint
       │
       ▼
  Phase 4: Frontend Types + API Client
       │
       ▼
  Phase 5: Frontend Components (ChainInputSection, ChainStepStatus, ChainOutputSection)
       │
       ▼
  Phase 6: Frontend Page + Routing + Seed Data + Navigation
```

**Critical path:** Phase 1 → 2 → 3 → 4 → 5 → 6 (each phase depends on the previous one being complete).

---

## Phase 1: Database Schema (No Dependencies)

These changes are independent — they only touch the ORM layer and the database. Everything else in the codebase continues working after this phase.

- [ ] **1.1** Add `alias` column to `PromptGroupItem` model (`backend/app/models.py`)
- [ ] **1.2** Add `is_input_step` column to `PromptGroupItem` model (`backend/app/models.py`)
- [ ] **1.3** Add `is_chain_page` column to `PromptGroup` model (`backend/app/models.py`)
- [ ] **1.4** Add `page_route` column to `PromptGroup` model (`backend/app/models.py`)
- [ ] **1.5** Create Alembic migration file (`backend/alembic/versions/xxx_add_chain_page_fields.py`)
- [ ] **1.6** Run `uv run alembic upgrade head` to apply migration
- [ ] **1.7** **Verify:** `SELECT alias, is_input_step, is_chain_page, page_route FROM "PromptGroupItem" LIMIT 1;` returns NULL/0 for existing rows

### Files to modify
| File | Action |
|------|--------|
| `backend/app/models.py` | Add 4 new columns |
| `backend/alembic/versions/xxx_add_chain_page_fields.py` | Create |

### Verification command
```bash
cd backend && uv run alembic upgrade head
```

---

## Phase 2: Pydantic Schemas + Placeholder Engine (Depends on Phase 1)

Schemas must be updated before any API can return the new fields. Placeholder engine must be updated before the chain executor can use `{step_N}`.

- [ ] **2.1** Update `PromptGroupItemSchema` — add `alias: str | None = None`, `is_input_step: bool = False`
- [ ] **2.2** Update `PromptGroupItemCreate` — add `alias: str | None = None`, `is_input_step: bool = False`
- [ ] **2.3** Update `PromptGroupSchema` — add `is_chain_page: bool = False`, `page_route: str | None = None`
- [ ] **2.4** Update `_group_to_schema()` in `prompt_groups.py` routes to include new fields
- [ ] **2.5** Update `create_group()` and `update_group()` routes to accept `alias` and `is_input_step` on items
- [ ] **2.6** Add `chain_results` and `aliases` parameters to `resolve_placeholders()` in `placeholders.py`
- [ ] **2.7** Add `{step_N}` and `{step_N.result}` regex resolution to `resolve_placeholders()`
- [ ] **2.8** Add `{alias}` regex resolution to `resolve_placeholders()`
- [ ] **2.9** **Verify:** Existing `POST /api/prompt-groups/{id}/execute` still works (backward compat)

### Files to modify
| File | Action |
|------|--------|
| `backend/app/schemas.py` | Extend 3 schemas |
| `backend/app/routes/prompt_groups.py` | Update 2 helper functions |
| `backend/app/services/placeholders.py` | Extend `resolve_placeholders()` |

### Verification command
```bash
cd backend && uv run alembic upgrade head
# Then test: existing chain execution still returns valid response
```

---

## Phase 3: Chain Execution Engine + New API Endpoint (Depends on Phase 2)

The chain executor now needs `page_mode`, `user_inputs`, and chain result tracking. The new `/execute-chain` endpoint depends on the updated executor.

- [ ] **3.1** Update `execute_chain()` in `prompt_chain.py`:
  - Add `page_mode: bool = False` parameter
  - Add `user_inputs: dict[int, dict[str, str]] | None = None` parameter
  - Build `aliases` map from items (`step_{N}` → N, plus user-defined aliases)
  - Track `chain_results: dict[int, str]` per step
  - Resolve `{step_N}` / `{alias}` in each step's user message using `chain_results`
  - Include `alias` field in `chain_steps` output
- [ ] **3.2** Add `ChainExecutionRequest` Pydantic model to `schemas.py`
- [ ] **3.3** Add `POST /api/prompt-groups/{group_id}/execute-chain` endpoint to `prompt_groups.py`
- [ ] **3.4** **Verify:** `POST /api/prompt-groups/{id}/execute-chain` with `{"inputs": {"1": {"customer_name": "test"}}}` returns chain result with per-step details

### Files to modify
| File | Action |
|------|--------|
| `backend/app/services/prompt_chain.py` | Major refactor: chain results tracking |
| `backend/app/schemas.py` | Add `ChainExecutionRequest` |
| `backend/app/routes/prompt_groups.py` | Add new endpoint |

### Verification command
```bash
# Test new endpoint with curl
curl -X POST http://localhost:8000/api/prompt-groups/1/execute-chain \
  -H "Content-Type: application/json" \
  -d '{"inputs": {"1": {"customer_name": "test"}}, "initial_input": ""}'
```

---

## Phase 4: Frontend Types + API Client (Depends on Phase 3)

Frontend types must match the backend schema. API client must exist before components can call it.

- [ ] **4.1** Update `PromptGroupItem` TS interface — add `alias?: string`, `is_input_step?: boolean`
- [ ] **4.2** Update `PromptGroupItemCreate` TS interface — add `alias?: string`, `is_input_step?: boolean`
- [ ] **4.3** Update `PromptGroup` TS interface — add `is_chain_page?: boolean`, `page_route?: string | null`
- [ ] **4.4** Add `ChainExecutionRequest` TS interface
- [ ] **4.5** Add `ChainStepResult` TS interface
- [ ] **4.6** Add `ChainExecutionResult` TS interface
- [ ] **4.7** Add `executeChain()` function to `promptGroupsApi.ts`
- [ ] **4.8** Export `executeChain` from `promptGroupsApi`
- [ ] **4.9** **Verify:** TypeScript compiles without errors (`npx tsc --noEmit`)

### Files to modify
| File | Action |
|------|--------|
| `frontend/src/types/prompt.ts` | Extend 3 interfaces, add 3 new ones |
| `frontend/src/services/promptGroupsApi.ts` | Add `executeChain` function |

### Verification command
```bash
cd frontend && npx tsc --noEmit
```

---

## Phase 5: Frontend Components (Depends on Phase 4)

Components depend on types and API client being available.

### 5A: ChainInputSection (most complex)

- [ ] **5A.1** Create `frontend/src/components/ui/ChainInputSection.tsx`
- [ ] **5A.2** Implement `inferInputFields()` utility — parse template for `{placeholder}` patterns
- [ ] **5A.3** Implement `inferFieldType()` utility — text / date / select detection
- [ ] **5A.4** Migrate media state from GuestSearch:
  - [ ] Image upload + camera capture handlers
  - [ ] Voice recording handlers (MediaRecorder API)
  - [ ] Image extraction handler (calls `/api/guest-search/extract-name`)
  - [ ] Audio extraction handler (calls `/api/guest-search/extract-name`)
  - [ ] RegionSelector integration for image crop
- [ ] **5A.5** Render template-derived input fields (text, select, date)
- [ ] **5A.6** Render media input buttons (Upload Photo, Take Photo, Speak Name, Clear)
- [ ] **5A.7** Render "Extract Name" button that populates `{customer_name}`
- [ ] **5A.8** Call `onRun(inputs)` with `Record<number, Record<string, string>>` format
- [ ] **5A.9** **Verify:** Component renders with a sample PromptGroupItem, all inputs visible

### 5B: ChainStepStatus

- [ ] **5B.1** Create `frontend/src/components/ui/ChainStepStatus.tsx`
- [ ] **5B.2** Display prompt_id + version + alias (if set)
- [ ] **5B.3** Display status indicator (success/running/failed) with color
- [ ] **5B.4** Display cached indicator
- [ ] **5B.5** Display error message if failed
- [ ] **5B.6** Collapsible/expandable detail view
- [ ] **5B.7** **Verify:** Shows correctly for a mock step result

### 5C: ChainOutputSection

- [ ] **5C.1** Create `frontend/src/components/ui/ChainOutputSection.tsx`
- [ ] **5C.2** Render final output as text (markdown rendering optional)
- [ ] **5C.3** Copy to clipboard button
- [ ] **5C.4** Re-run chain button (calls `onRerun`)
- [ ] **5C.5** **Verify:** Renders chain result correctly

### Files to create
| File | Purpose |
|------|---------|
| `frontend/src/components/ui/ChainInputSection.tsx` | Input fields + media handling |
| `frontend/src/components/ui/ChainStepStatus.tsx` | Step status bar |
| `frontend/src/components/ui/ChainOutputSection.tsx` | Final output renderer |

### Update files
| File | Purpose |
|------|---------|
| `frontend/src/components/ui/index.ts` | Re-export new components |

---

## Phase 6: Page, Routing, Seed Data, Navigation (Depends on Phase 5)

This is the final integration phase. Everything depends on components existing.

- [ ] **6.1** Create `frontend/src/pages/PromptChainPage.tsx`
  - Load groups via `promptGroupsApi.list()`
  - Find group by `page_route` match with URL param
  - Render `ChainInputSection` for first item
  - Render `ChainStepStatus` for intermediate steps
  - Render `ChainOutputSection` for last step
  - Handle loading / not-found states
- [ ] **6.2** Add wildcard route in `frontend/src/App.tsx`:
  ```tsx
  <Route path="/prompt-chains/:route" element={<PromptChainPage />} />
  ```
- [ ] **6.3** Create `backend/Generator/seed_chain_pages.py`
  - Create "Guest Intelligence" PromptGroup with `is_chain_page=true`, `page_route="/guest-intel"`
  - Add 2 items: guest-search (position 1) and guest-extract (position 2)
  - Mark position 1 as `is_input_step=true`, set aliases "search" and "extraction"
- [ ] **6.4** Run seed: `cd backend && uv run python Generator/seed_chain_pages.py`
- [ ] **6.5** Add navigation link in `frontend/src/components/Header.tsx`:
  ```tsx
  { label: "Guest Intelligence", href: "/prompt-chains/guest-intel" }
  ```
- [ ] **6.6** **Verify:** Navigate to `/prompt-chains/guest-intel` → see chain page with input fields
- [ ] **6.7** **Verify:** Enter a name, click Search → see chain execute and results render
- [ ] **6.8** **Optional:** Redirect old `/guest-search` to new chain page

### Files to create
| File | Purpose |
|------|---------|
| `frontend/src/pages/PromptChainPage.tsx` | Main chain page |
| `backend/Generator/seed_chain_pages.py` | Seed data |

### Files to modify
| File | Action |
|------|--------|
| `frontend/src/App.tsx` | Add wildcard route |
| `frontend/src/components/Header.tsx` | Add nav link |

---

## Dependency Graph (Summary)

```
Phase 1: Database Schema
  └─ No dependencies — start here
       │
       ▼
Phase 2: Schemas + Placeholder Engine
  └─ Depends on: Phase 1 (new columns must exist in DB)
       │
       ▼
Phase 3: Chain Executor + API Endpoint
  └─ Depends on: Phase 2 (placeholder engine + schemas)
       │
       ▼
Phase 4: Frontend Types + API Client
  └─ Depends on: Phase 3 (API shape is now known)
       │
       ▼
Phase 5: Frontend Components
  └─ Depends on: Phase 4 (types + API client)
       │
       ▼
Phase 6: Page + Routing + Seed + Nav
  └─ Depends on: Phase 5 (components)
```

---

## Quick Reference: 15 Files Total

| # | File | Action | Phase |
|---|------|--------|-------|
| 1 | `backend/app/models.py` | Modify | 1 |
| 2 | `backend/alembic/versions/xxx_add_chain_page_fields.py` | Create | 1 |
| 3 | `backend/app/schemas.py` | Modify | 2, 3 |
| 4 | `backend/app/routes/prompt_groups.py` | Modify | 2, 3 |
| 5 | `backend/app/services/placeholders.py` | Modify | 2 |
| 6 | `backend/app/services/prompt_chain.py` | Modify | 3 |
| 7 | `frontend/src/types/prompt.ts` | Modify | 4 |
| 8 | `frontend/src/services/promptGroupsApi.ts` | Modify | 4 |
| 9 | `frontend/src/components/ui/ChainInputSection.tsx` | Create | 5 |
| 10 | `frontend/src/components/ui/ChainStepStatus.tsx` | Create | 5 |
| 11 | `frontend/src/components/ui/ChainOutputSection.tsx` | Create | 5 |
| 12 | `frontend/src/components/ui/index.ts` | Modify | 5 |
| 13 | `frontend/src/pages/PromptChainPage.tsx` | Create | 6 |
| 14 | `frontend/src/App.tsx` | Modify | 6 |
| 15 | `frontend/src/components/Header.tsx` | Modify | 6 |
| 16 | `backend/Generator/seed_chain_pages.py` | Create | 6 |

**Grand total: 16 files (4 modified, 7 created, 5 modified across multiple phases)**