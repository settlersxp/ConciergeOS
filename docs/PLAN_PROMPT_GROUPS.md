# Prompt Groups Feature — Requirements & Implementation Plan

## Overview

A new page (`/prompt-groups`) allowing users to create ordered groups of existing prompt+version pairs that serve as building blocks for multi-step prompt chains. Each group can be executed immediately (sequential chain) or scheduled for future execution, with results saved to files for report generation.

---

## Requirements

### R1 — Prompt Group CRUD

Users can create, read, update, and delete **prompt groups**. Each group contains:
- A `name` (string)
- An ordered list of **prompt + version** pairs (building blocks)

**Acceptance Criteria:**
- User can create a group with a name and at least one prompt+version entry
- User can reorder entries within a group (drag or up/down buttons)
- User can add/remove entries from a group
- User can delete a group (with confirmation)
- Groups persist in the database

### R2 — Prompt Chain Execution ("Recalculate Now")

Clicking **"Recalculate Now"** executes the group's prompts sequentially: Prompt 1 → Prompt 2 → ... → Prompt N. Each prompt's output feeds into the next prompt as context. The page populates with intermediate + final results.

**Acceptance Criteria:**
- Prompts resolve from the existing `PromptStore` using `prompt_id` + `version`
- Execution uses the existing LLM infrastructure (`get_llm_config()`, same client/model as other pages)
- Results are displayed on the page (one section per prompt in the chain)
- Final result is saved to a JSON file under `data/prompt_group_results/`
- Execution status shown via `StatusBanner` (running → success/error)

### R3 — Scheduled Execution ("Schedule Reschedule")

Clicking **"Schedule Reschedule"** opens a datetime picker. The selected time triggers a background cron job that executes the prompt chain and saves the outcome to a file.

**Acceptance Criteria:**
- User can pick a future date/time for execution
- The scheduler persists the job (survives process restart via JSON file)
- On the scheduled time, the chain executes and results are saved to `data/prompt_group_results/{groupId}_{timestamp}.json`
- User can view past execution history (timestamp, status)

### R4 — Dedicated UI Page

A new route `/prompt-groups` with its own nav link in the header. The page reuses existing UI components wherever possible.

**Acceptance Criteria:**
- Route registered in `App.tsx`
- Nav link added to `Header.tsx`
- Page uses: `PageHeader`, `Card`, `Button`, `PromptSelector`, `Toast`, `Badge`, `StatusBanner`, `Input`, `Textarea`
- Group list view shows all groups with their prompt chain summary
- Group detail view shows the full chain, execution buttons, and results

---

## Data Model

### Database Tables (CamelCase naming per project convention)

#### `PromptGroup`
| Column       | Type         | Constraints            |
|--------------|--------------|------------------------|
| group_id     | INTEGER      | PRIMARY KEY            |
| name         | TEXT         | NOT NULL               |
| description  | TEXT         | NULLABLE               |
| created_at   | DATETIME     | DEFAULT NOW            |
| updated_at   | DATETIME     | DEFAULT NOW            |

#### `PromptGroupItem`
| Column         | Type     | Constraints                    |
|----------------|----------|--------------------------------|
| item_id        | INTEGER  | PRIMARY KEY                    |
| group_id       | INTEGER  | FK → PromptGroup.group_id      |
| position       | INTEGER  | NOT NULL (order in chain)      |
| prompt_id      | TEXT     | NOT NULL                       |
| prompt_version | INTEGER  | NOT NULL                       |

#### `PromptGroupSchedule`
| Column        | Type     | Constraints                       |
|---------------|----------|-----------------------------------|
| schedule_id   | INTEGER  | PRIMARY KEY                       |
| group_id      | INTEGER  | FK → PromptGroup.group_id         |
| run_at        | DATETIME | NOT NULL                          |
| active        | BOOLEAN  | DEFAULT TRUE                      |
| created_at    | DATETIME | DEFAULT NOW                       |

#### `PromptGroupResult`
| Column        | Type     | Constraints                         |
|---------------|----------|-------------------------------------|
| result_id     | INTEGER  | PRIMARY KEY                         |
| group_id      | INTEGER  | FK → PromptGroup.group_id           |
| executed_at   | DATETIME | DEFAULT NOW                         |
| scheduled     | BOOLEAN  | DEFAULT FALSE                       |
| result_file   | TEXT     | Path to saved JSON file             |
| status        | TEXT     | "success" / "failed" / "running"    |
| error_message | TEXT     | NULLABLE                            |

---

## API Endpoints

All routes prefixed with `/api/prompt-groups`

| Method   | Path                                    | Description                        |
|----------|-----------------------------------------|-------------------------------------|
| GET      | `/prompt-groups`                        | List all groups                     |
| POST     | `/prompt-groups`                        | Create a new group                  |
| GET      | `/prompt-groups/{group_id}`             | Get group detail + items            |
| PUT      | `/prompt-groups/{group_id}`             | Update group (name, items, order)   |
| DELETE   | `/prompt-groups/{group_id}`             | Delete group                        |
| POST     | `/prompt-groups/{group_id}/execute`     | Execute chain now                   |
| POST     | `/prompt-groups/{group_id}/schedule`    | Schedule execution at a time        |
| GET      | `/prompt-groups/{group_id}/results`     | Get execution history               |
| DELETE   | `/prompt-groups/{group_id}/schedules`   | Clear all schedules for a group     |

---

## Implementation Plan

### Phase 1 — Database Layer
- [ ] Add SQLAlchemy models (`PromptGroup`, `PromptGroupItem`, `PromptGroupSchedule`, `PromptGroupResult`) to `app/models.py`
- [ ] Add Pydantic schemas to `app/schemas.py`
- [ ] Generate Alembic migration for new tables

### Phase 2 — Backend Services
- [ ] `app/services/prompt_chain.py` — Sequential prompt chain execution logic
  - Resolves prompts via existing `PromptStore`
  - Chains output: Prompt N output → Prompt N+1 input context
  - Saves results to `data/prompt_group_results/`
- [ ] `app/services/prompt_scheduler.py` — Background scheduler
  - Uses APScheduler for timing
  - Persists schedules to JSON for recovery
  - Triggers `prompt_chain.execute()` on schedule fire

### Phase 3 — Backend Routes
- [ ] `app/routes/prompt_groups.py` — CRUD + execute + schedule endpoints
- [ ] Register router in `app/main.py`

### Phase 4 — Frontend
- [ ] `frontend/src/services/promptGroupsApi.ts` — API client
- [ ] `frontend/src/pages/PromptGroups.tsx` — Main page
  - Group list view (cards)
  - Group create/edit form (reuse `PromptSelector`, `Card`, `Button`, `Input`, `Textarea`)
  - Group detail view with chain visualization
  - "Recalculate Now" + "Schedule Reschedule" buttons
  - Results display area
  - Status/notifications via `StatusBanner`, `Toast`, `Badge`
- [ ] Add route in `frontend/src/App.tsx`
- [ ] Add nav link in `frontend/src/components/Header.tsx`

---

## Component Reuse Map

| Existing Component     | Usage in PromptGroups                         |
|------------------------|-----------------------------------------------|
| `PageHeader`           | Page title                                    |
| `Card`                 | Group cards, forms, result panels             |
| `Button`               | All action buttons                            |
| `PromptSelector`       | Select prompt+version for each chain item     |
| `Toast`                | Success/error notifications                   |
| `Badge`                | Execution status indicators                   |
| `StatusBanner`         | Running/success/error banners                 |
| `Input`                | Group name, description fields                |
| `Textarea`             | Initial input text for chain execution        |

---

## File Structure (New Files)

```
app/
  routes/prompt_groups.py
  services/prompt_chain.py
  services/prompt_scheduler.py

frontend/src/
  pages/PromptGroups.tsx
  services/promptGroupsApi.ts

data/prompt_group_results/    (created at runtime)
```

## Files Modified

```
app/models.py                          (new SQLAlchemy models)
app/schemas.py                         (new Pydantic schemas)
app/main.py                            (register router)
frontend/src/App.tsx                   (new route)
frontend/src/components/Header.tsx     (nav link)
alembic/versions/xxx_*.py              (migration)