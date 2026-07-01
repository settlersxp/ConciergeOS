# Implementation Spec: Prompt Chain Pages

> **Created:** 2026-01-07
> **Status:** In Progress
> **Related:** [IMPLEMENTATION_PROMPT_CHAIN_PAGES.md](./IMPLEMENTATION_PROMPT_CHAIN_PAGES.md)
> **Purpose:** This file serves as the detailed implementation spec. It captures every file to create/modify, every API surface, every migration, and every design decision.

---

## Table of Contents

1. [Overview & Architecture](#1-overview--architecture)
2. [Phase 1: Backend Infrastructure](#phase-1-backend-infrastructure)
3. [Phase 2: Chain Execution Engine](#phase-2-chain-execution-engine)
4. [Phase 3: Frontend Types & API Client](#phase-3-frontend-types--api-client)
5. [Phase 4: Frontend Components](#phase-4-frontend-components)
6. [Phase 5: Routing & GuestSearch Replacement](#phase-5-routing--guestsearch-replacement)
7. [Design Decisions](#design-decisions)
8. [Migration Guide](#migration-guide)

---

## 1. Overview & Architecture

### The Problem

The current Guest Search page (`/guest-search`) is a single monolithic component with:
- Text input for customer name
- Photo upload/capture with name extraction
- Voice recording with name extraction
- Single prompt execution (search)

This is a standalone feature that doesn't leverage the existing Prompt Group / Chain system. As we build more complex, multi-step user-facing pages, we need a **reusable page-in-a-box** pattern.

### The Solution: Prompt Chain Pages

A **PromptChainPage** is a generic container that:
1. Loads a **PromptGroup** (configured via the Prompt Management UI)
2. Renders **input fields** from the first step's prompt template
3. **Executes** each step sequentially, passing each step's output into the next step via `{step_N}` placeholder references
4. Renders the **final step's output** as the page content
5. Returns the **dynamic URL** via the `page_route` field on the PromptGroup

### Visual Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  URL: /prompt-chains/{page_route}                            │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ Page Header: "Guest Intelligence"                   │    │
│  │ Description: "Comprehensive guest profile analysis"  │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ [CHAIN INPUT SECTION — Step 1]                       │    │
│  │                                                       │    │
│  │ Text Input: "Customer Name" (from {customer_name})   │    │
│  │ [Upload Photo] [Take Photo] [Speak Name]             │    │
│  │                                                       │    │
│  │ [Image Preview with Region Selector]                 │    │
│  │ [Audio Playback]                                     │    │
│  │ [Extract Name] button                                  │    │
│  │                                                       │    │
│  │ [Search] button → triggers chain                     │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ [CHAIN STEP STATUS — Step 2] (collapsed)            │    │
│  │  guest-extract · v1    ── References: {step_1}     │    │
│  │  ────                                              │    │
│  │  [running/success/failed]                          │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ [CHAIN OUTPUT SECTION — Step 3]                      │    │
│  │                                                       │    │
│  │ <rendered LLM output here>                            │    │
│  │ [Copy] [Re-run Chain]                                │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

### Step Reference Syntax

| Syntax | Resolves To | Example |
|--------|-------------|---------|
| `{step_N}` | Raw output of step N (1-indexed) | `{step_1}` |
| `{step_N.result}` | Same as `{step_N}` | `{step_1.result}` |
| `{alias}` | Output of step with matching alias | `{search}` |
| `{DATABASE_TABLES}` | Existing static placeholder | (unchanged) |
| `{table.field}` | Existing runtime variable | (unchanged) |

---

## 2. Phase 1: Backend Infrastructure

### 2.1 Files to Modify

#### `backend/app/models.py`

**Changes to `PromptGroupItem`:**
```python
class PromptGroupItem(Base):
    __tablename__ = "PromptGroupItem"

    item_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    group_id: Mapped[int] = mapped_column(Integer, ForeignKey("PromptGroup.group_id", ondelete="CASCADE"), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    prompt_id: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt_version: Mapped[int] = mapped_column(Integer, nullable=False)

    # NEW FIELDS:
    alias: Mapped[str | None] = mapped_column(String(50), nullable=True,
        comment="Human-readable alias for cross-step referencing")
    is_input_step: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0",
        comment="Mark this step as the user-input entry point for page mode")

    group: Mapped["PromptGroup"] = relationship(back_populates="items")
```

**Changes to `PromptGroup`:**
```python
class PromptGroup(Base):
    __tablename__ = "PromptGroup"

    group_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")

    # NEW FIELDS:
    is_chain_page: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0",
        comment="If True, this group renders as a full page")
    page_route: Mapped[str | None] = mapped_column(String(200), nullable=True,
        comment="URL route for chain page (e.g., /guest-intel)")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    items: Mapped[list["PromptGroupItem"]] = relationship(
        back_populates="group",
        cascade="all, delete-orphan",
        order_by="PromptGroupItem.position"
    )
    schedules: Mapped[list["PromptGroupSchedule"]] = relationship(back_populates="group", cascade="all, delete-orphan")
    results: Mapped[list["PromptGroupResult"]] = relationship(back_populates="group", cascade="all, delete-orphan")
```

#### `backend/app/schemas.py`

**Changes to `PromptGroupItemSchema`:**
```python
class PromptGroupItemSchema(BaseModel):
    item_id: int
    group_id: int
    position: int
    prompt_id: str
    prompt_version: int
    # NEW FIELDS:
    alias: str | None = None
    is_input_step: bool = False
```

**Changes to `PromptGroupItemCreate`:**
```python
class PromptGroupItemCreate(BaseModel):
    position: int
    prompt_id: str
    prompt_version: int
    # NEW FIELDS:
    alias: str | None = None
    is_input_step: bool = False
```

**Changes to `PromptGroupSchema`:**
```python
class PromptGroupSchema(BaseModel):
    group_id: int
    name: str
    description: str | None
    is_active: bool
    created_at: str
    updated_at: str
    # NEW FIELDS:
    is_chain_page: bool = False
    page_route: str | None = None
    items: list[PromptGroupItemSchema] = []
    schedules: list[PromptGroupScheduleSchema] = []
    results: list[PromptGroupResultSchema] = []
```

#### `backend/alembic/versions/xxx_add_chain_page_fields.py`

```python
"""Add chain page fields to PromptGroup and PromptGroupItem

Revision ID: a782e25476e5_add_chain_page_fields
Revises: a782e25476e4
Create Date: 2026-01-07 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'a782e25476e5_add_chain_page_fields'
down_revision = 'a782e25476e4_add_prompt_group_tables'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("PromptGroupItem",
        sa.Column("alias", sa.String(50), nullable=True))
    op.add_column("PromptGroupItem",
        sa.Column("is_input_step", sa.Boolean, server_default="0"))

    op.add_column("PromptGroup",
        sa.Column("is_chain_page", sa.Boolean, server_default="0"))
    op.add_column("PromptGroup",
        sa.Column("page_route", sa.String(200), nullable=True))


def downgrade():
    op.drop_column("PromptGroup", "page_route")
    op.drop_column("PromptGroup", "is_chain_page")
    op.drop_column("PromptGroupItem", "is_input_step")
    op.drop_column("PromptGroupItem", "alias")
```

---

## 3. Phase 2: Chain Execution Engine

### 3.1 Files to Modify

#### `backend/app/services/placeholders.py`

**Add chain result resolution to `resolve_placeholders()`:**

```python
def resolve_placeholders(
    text: str,
    chain_results: dict[int, str] | None = None,
    aliases: dict[str, int] | None = None,  # alias_name -> step_position
) -> str:
    """Resolve all placeholders: static + runtime + chain results.

    Resolution order:
    1. Static placeholders (DATABASE_TABLES, GUEST_INFORMATION, etc.)
    2. Runtime variables ({table.field} → user-provided value)
    3. Chain results ({step_N}, {alias})
    """
    # Phase 1: Static placeholders (existing behavior)
    text = re.sub(r"\{([A-Za-z_][A-Za-z0-9_]*)\}", _static_replacer, text)

    # Phase 2: Runtime variables (existing behavior)
    # (Done in resolve_all_placeholders)

    # Phase 3: Chain result references
    if chain_results:
        # Replace {step_N} and {step_N.result}
        def step_resolver(match):
            pos = int(match.group(1))
            return chain_results.get(pos, match.group(0))
        text = re.sub(r"\{step_(\d+)(?:\.result)?\}", step_resolver, text)

        # Replace {alias} references
        if aliases:
            def alias_resolver(match):
                alias_name = match.group(1)
                if alias_name in aliases:
                    return chain_results.get(aliases[alias_name], match.group(0))
                return match.group(0)
            # Only match lowercase letters/underscores/digits (alias pattern)
            text = re.sub(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}", alias_resolver, text)

    return text
```

### 3.2 Files to Modify

#### `backend/app/services/prompt_chain.py`

**Major refactor: Add chain results tracking and page mode support.**

```python
def execute_chain(
    group_id: int,
    initial_input: str = "",
    scheduled: bool = False,
    db: Session | None = None,
    page_mode: bool = False,
    user_inputs: dict[int, dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Execute chain with cross-step result passing.

    Args:
        group_id: ID of the PromptGroup to execute.
        initial_input: Optional initial text for the first step.
        scheduled: Whether triggered by scheduler.
        db: Optional database session.
        page_mode: If True, first step receives user_inputs as template variables.
        user_inputs: {step_position: {field: value}} for page mode execution.

    Returns:
        dict with chain_results, per-step details, and final_output.
    """
    session_manager = db if db is not None else SessionLocal()
    should_close = db is None

    try:
        if should_close:
            session_manager.__enter__()

        # Load group + items
        group = session_manager.query(PromptGroup).filter(
            PromptGroup.group_id == group_id
        ).first()
        if not group:
            raise ValueError(f"PromptGroup {group_id} not found")

        items = (
            session_manager.query(PromptGroupItem)
            .filter(PromptGroupItem.group_id == group_id)
            .order_by(PromptGroupItem.position)
            .all()
        )
        if not items:
            raise ValueError(f"PromptGroup {group_id} has no items")

        # Build alias map: alias_name → step_position
        # Also maps "step_{N}" → N for built-in aliases
        aliases: dict[str, int] = {}
        for item in items:
            aliases[f"step_{item.position}"] = item.position
            if item.alias:
                aliases[item.alias] = item.position

        # Create result record
        result_record = PromptGroupResult(
            group_id=group_id,
            scheduled=scheduled,
            status="running",
        )
        session_manager.add(result_record)
        session_manager.commit()
        session_manager.refresh(result_record)

        chain_steps: list[dict[str, Any]] = []
        chain_results: dict[int, str] = {}

        prompt_store = PromptStore()

        for item in items:
            try:
                # --- Resolve prompt template ---
                system_prompt, user_template = prompt_store.resolve_prompt(
                    item.prompt_id, item.prompt_version
                )

                # --- Determine runtime variables for this step ---
                runtime_vars: dict[str, str] = {}
                if page_mode and user_inputs and item.position in user_inputs:
                    runtime_vars = user_inputs[item.position]

                # --- Phase 1: Resolve static placeholders ---
                system_prompt_resolved = resolve_placeholders(system_prompt)
                user_message = resolve_placeholders(user_template)

                # --- Phase 2: Resolve runtime variables ---
                user_message = _resolve_runtime_vars(user_message, runtime_vars)

                # --- Phase 3: Resolve chain results ({step_N}, {alias}) ---
                user_message = resolve_placeholders(
                    user_message,
                    chain_results=chain_results,
                    aliases=aliases,
                )

                # --- Phase 4: Resolve initial_input for first step ---
                if item.position == 1 and initial_input:
                    # Prepend initial_input to user message
                    user_message = f"{initial_input}\n\n---\n\n{user_message}"

                # --- Resolve model_id for this prompt version ---
                from app.models import PromptVersion as PV
                pv = session_manager.query(PV).filter(
                    PV.prompt_id == item.prompt_id,
                    PV.version == item.prompt_version,
                ).first()
                model_id_val = pv.model_id if pv else None

                # --- Call LLM ---
                from app.services.llm import get_llm_config_by_model_id
                from app.services.response_cache import (
                    call_llm_with_db_tools_with_cache_flag,
                )

                client, model_name = get_llm_config_by_model_id(model_id_val)
                llm_response, was_cached = call_llm_with_db_tools_with_cache_flag(
                    user_message,
                    system_prompt=system_prompt_resolved,
                )

                # --- Store in chain_results for subsequent steps ---
                chain_results[item.position] = llm_response

                chain_steps.append({
                    "position": item.position,
                    "prompt_id": item.prompt_id,
                    "prompt_version": item.prompt_version,
                    "alias": item.alias,
                    "system_prompt": system_prompt_resolved,
                    "user_message": user_message,
                    "response": llm_response,
                    "cached": was_cached,
                    "error": None,
                })

            except Exception as step_err:
                logger.error(
                    "Error executing step %s (%s:v%s): %s",
                    item.position, item.prompt_id, item.prompt_version,
                    step_err, exc_info=True,
                )
                chain_steps.append({
                    "position": item.position,
                    "prompt_id": item.prompt_id,
                    "prompt_version": item.prompt_version,
                    "alias": item.alias,
                    "system_prompt": None,
                    "user_message": None,
                    "response": None,
                    "cached": False,
                    "error": str(step_err),
                })
                # Continue chain even if step fails
                chain_results[item.position] = f"[ERROR in step {item.position}]: {step_err}"

        # --- Build final result ---
        success = all(step["error"] is None for step in chain_steps)
        chain_result = {
            "group_id": group_id,
            "group_name": group.name,
            "executed_at": datetime.now(timezone.utc).isoformat(),
            "scheduled": scheduled,
            "success": success,
            "steps_count": len(chain_steps),
            "steps": chain_steps,
            "final_output": chain_steps[-1]["response"] if chain_steps else None,
        }

        # Save to file
        result_file_path = _save_result_to_file(group_id, chain_result)

        # Update result record
        result_record.status = "success" if success else "failed"
        result_record.result_file = result_file_path
        if not success:
            errors = [step["error"] for step in chain_steps if step["error"]]
            result_record.error_message = "; ".join(errors)
        session_manager.commit()

        chain_result["result_file"] = result_file_path
        chain_result["result_id"] = result_record.result_id

        return chain_result

    finally:
        if should_close:
            session_manager.__exit__(*sys.exc_info())
```

### 3.3 Files to Modify

#### `backend/app/routes/prompt_groups.py`

**Add new endpoint and schema:**

```python
from app.schemas import ChainExecutionRequest, ChainExecutionResponse

@router.post("/{group_id}/execute-chain")
def execute_chain_page(group_id: int, req: ChainExecutionRequest):
    """Execute chain with user inputs (page mode).

    The first step receives user_inputs as template variables.
    Subsequent steps receive the output of their predecessor.
    """
    try:
        result = execute_chain(
            group_id,
            initial_input=req.initial_input,
            page_mode=True,
            user_inputs=req.inputs,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("Execution failed for group %d: %s", group_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
```

**Add to `backend/app/schemas.py`:**

```python
class ChainExecutionRequest(BaseModel):
    """Request body for page-mode chain execution."""
    inputs: dict[int, dict[str, str]] = {}
    """{step_position: {field_name: value}} for user-provided inputs"""
    initial_input: str = ""
    """Raw text passed to the first step before template resolution"""


class ChainStepResponse(BaseModel):
    """Per-step response from chain execution."""
    position: int
    prompt_id: str
    prompt_version: int
    alias: str | None = None
    status: str  # "running" | "success" | "failed"
    response: str | None = None
    cached: bool = False
    error: str | None = None
```

**Update `_group_to_schema()` to include new fields:**

```python
def _group_to_schema(group: PromptGroup) -> PromptGroupSchema:
    return PromptGroupSchema(
        group_id=group.group_id,
        name=group.name,
        description=group.description,
        is_active=group.is_active,
        is_chain_page=group.is_chain_page,
        page_route=group.page_route,
        created_at=group.created_at.isoformat() if group.created_at else "",
        updated_at=group.updated_at.isoformat() if group.updated_at else "",
        items=[
            PromptGroupItemSchema(
                item_id=item.item_id,
                group_id=item.group_id,
                position=item.position,
                prompt_id=item.prompt_id,
                prompt_version=item.prompt_version,
                alias=item.alias,
                is_input_step=item.is_input_step,
            )
            for item in group.items
        ],
        # ... existing schedules and results ...
    )
```

---

## 4. Phase 3: Frontend Types & API Client

### 4.1 Files to Create/Modify

#### `frontend/src/types/prompt.ts`

Add new types:

```typescript
export interface PromptGroupItem {
  item_id: number;
  group_id: number;
  position: number;
  prompt_id: string;
  prompt_version: number;
  // NEW:
  alias?: string;
  is_input_step?: boolean;
}

export interface PromptGroupItemCreate {
  position: number;
  prompt_id: string;
  prompt_version: number;
  alias?: string;
  is_input_step?: boolean;
}

export interface PromptGroup {
  group_id: number;
  name: string;
  description: string | null;
  is_active: boolean;
  // NEW:
  is_chain_page?: boolean;
  page_route?: string | null;
  created_at: string;
  updated_at: string;
  items: PromptGroupItem[];
  schedules: PromptGroupSchedule[];
  results: PromptGroupResult[];
}

// ─── Chain page types ──────────────────────────────────────────────

export interface ChainExecutionRequest {
  inputs: Record<number, Record<string, string>>;
  initial_input?: string;
}

export interface ChainStepResult {
  position: number;
  prompt_id: string;
  prompt_version: number;
  alias?: string;
  status: "running" | "success" | "failed";
  response: string | null;
  cached: boolean;
  error: string | null;
  user_message: string | null;
}

export interface ChainExecutionResult {
  group_id: number;
  group_name: string;
  executed_at: string;
  scheduled: boolean;
  success: boolean;
  steps_count: number;
  steps: ChainStepResult[];
  final_output: string | null;
  result_file: string;
  result_id: number;
}
```

#### `frontend/src/services/promptGroupsApi.ts`

Add `executeChain` function:

```typescript
/**
 * Execute chain with user inputs (page mode).
 *
 * @param groupId The PromptGroup ID
 * @param inputs {step_position: {field: value}} for user-provided inputs
 * @param initialInput Optional initial text for the first step
 * @returns ChainExecutionResult with per-step details
 */
export function executeChain(
  groupId: number,
  inputs: Record<number, Record<string, string>>,
  initialInput?: string,
): Promise<ChainExecutionResult> {
  const body: ChainExecutionRequest = {
    inputs,
    initial_input: initialInput || "",
  };
  return request<ChainExecutionResult>(
    `/api/prompt-groups/${groupId}/execute-chain`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    },
  );
}

export const promptGroupsApi = {
  // ... existing methods ...
  executeChain,
};
```

---

## 5. Phase 4: Frontend Components

### 5.1 Component Architecture

```
frontend/src/components/ui/
├── ChainInputSection.tsx      # Step 1 input fields (text + media)
├── ChainStepStatus.tsx        # Intermediate step status bar
└── ChainOutputSection.tsx     # Final step output renderer
frontend/src/pages/
└── PromptChainPage.tsx        # Main chain page layout
```

### 5.2 `ChainInputSection.tsx`

This component:
1. Receives the **first PromptGroupItem** of the chain
2. Parses the `user_prompt_template` for `{placeholder}` patterns
3. Renders appropriate input fields:
   - `{customer_name}` → Text input
   - `{filter_status}` → Select dropdown
   - `{date_range}` → Date inputs
4. **Also includes** media input from GuestSearch:
   - Photo upload + camera capture with name extraction
   - Voice recording with name extraction
5. Collects all input values and passes them to the parent via `onRun(inputs)`

**Key design decision:** The media input (photo/voice) doesn't map to a template placeholder. Instead, the ChainInputSection **always** exposes the media buttons. When the user extracts a name, it populates the `{customer_name}` field. This is the **Option A** approach: media handling lives inside the chain page.

**Template parsing utility:**

```typescript
function inferInputFields(template: string): InputField[] {
  const patterns: InputField[] = [];
  const placeholderRegex = /\{([a-zA-Z_][a-zA-Z0-9_]*)\}/g;
  let match;

  while ((match = placeholderRegex.exec(template)) !== null) {
    const name = match[1];

    // Skip chain result placeholders
    if (name.startsWith("step_")) continue;

    // Skip known static placeholders
    if (KNOWN_PLACEHOLDERS.has(name)) continue;

    // Skip table.field patterns
    if (name.includes(".")) continue;

    patterns.push({
      name,
      label: name.replace(/_/g, " ").replace(/\b\w/g (c) => c.toUpperCase()),
      type: inferFieldType(name),
    });
  }

  return patterns;
}
```

**Props:**
```typescript
interface ChainInputSectionProps {
  step: PromptGroupItem;
  inputs: Record<string, string>;
  onInputChange: (name: string, value: string) => void;
  onRun: (inputs: Record<number, Record<string, string>>) => void;
  loading: boolean;
}
```

### 5.3 `ChainStepStatus.tsx`

Collapsible status bar for intermediate steps.

**Props:**
```typescript
interface ChainStepStatusProps {
  step: ChainStepResult;
  expanded?: boolean;
  onToggle?: () => void;
}
```

**Content:**
- Prompt ID + version
- Alias (if set, shown in parentheses)
- References (e.g., "References: {step_1}")
- Status indicator: 🟢 success / 🟡 running / 🔴 failed
- Cached indicator (if applicable)
- Execution time
- Error message (if failed)

### 5.4 `ChainOutputSection.tsx`

Renders the final step's LLM output.

**Props:**
```typescript
interface ChainOutputSectionProps {
  step: ChainStepResult;
  output: string | null;
  onRerun?: () => void;
}
```

**Features:**
- Markdown rendering of LLM output
- Copy to clipboard button
- Expand/collapse for long output
- Re-run chain button
- Cached indicator

### 5.5 `PromptChainPage.tsx`

Main page component.

**Props/Params:**
```typescript
// React Router params
const { route } = useParams<{ route: string }>();
```

**Flow:**
1. Load all PromptGroups, find the one with matching `page_route`
2. If not found → 404 page
3. If found → render chain page

**Layout:**
```
<PageHeader title={group.name} description={group.description} />
<ChainInputSection step={group.items[0]} ... />
{chainResult && (
  <>
    {chainResult.steps.slice(1, -1).map(step => (
      <ChainStepStatus key={step.position} step={step} />
    ))}
    <ChainOutputSection
      step={chainResult.steps[chainResult.steps.length - 1]}
      output={chainResult.final_output}
    />
  </>
)}
```

---

## 6. Phase 5: Routing & GuestSearch Replacement

### 6.1 Files to Modify

#### `frontend/src/App.tsx`

Add wildcard route for chain pages:

```typescript
import PromptChainPage from "./pages/PromptChainPage";

<Route path="/prompt-chains/:route" element={<PromptChainPage />} />
```

### 6.2 Seed Data

Create a seed script `backend/Generator/seed_chain_pages.py`:

```python
"""Seed the 'Guest Intelligence' chain page."""

def seed_guest_intelligence_chain(db):
    """Create the Guest Intelligence chain with 2 prompts."""

    # Create the group
    group = PromptGroup(
        name="Guest Intelligence",
        description="Comprehensive guest profile and preference analysis",
        is_active=True,
        is_chain_page=True,
        page_route="/guest-intel",
    )
    db.add(group)
    db.commit()
    db.refresh(group)

    # Step 1: Search for guest
    db.add(PromptGroupItem(
        group_id=group.group_id,
        position=1,
        prompt_id="guest-search",
        prompt_version=1,
        alias="search",
        is_input_step=True,
    ))

    # Step 2: Extract & render results
    db.add(PromptGroupItem(
        group_id=group.group_id,
        position=2,
        prompt_id="guest-extract",
        prompt_version=1,
        alias="extraction",
    ))

    db.commit()
    return group
```

### 6.3 Optional: Navigate /guest-search → /prompt-chains/:route

Redirect the legacy `/guest-search` route to the new chain page:

```typescript
// In App.tsx, replace old GuestSearch route:
<Route path="/guest-search" element={<Navigate to="/prompt-chains/guest-intel" />} />
```

### 6.4 Navigation Update

Add link to Header navigation:

```typescript
{
  label: "Guest Intelligence",
  href: "/prompt-chains/guest-intel",
}
```

---

## 7. Design Decisions

### 7.1 Media Input Lives in ChainInputSection (Option A)

**Rationale:** The photo/voice features are user-facing and meaningful. Moving them to a "pre-extraction" step would lose the rich UX. Instead, the ChainInputSection handles them and populates `{customer_name}` when the user clicks "Extract Name."

**How it works:**
1. User uploads photo or records voice
2. User clicks "Extract Name" → API call to `/api/guest-search/extract-name`
3. Extracted name populates `{customer_name}` text field
4. User clicks "Search" → entire chain executes with the populated inputs

### 7.2 Dynamic Wildcard Routing

Routes are **purely data-driven**. The only route needed is:
```
/prompt-chains/:route
```
The frontend loads all groups and finds the one with matching `page_route`. No route registration needed in code.

### 7.3 Template Placeholders vs Special Inputs

Two categories of input in the first step:

| Type | Example | Source |
|------|---------|--------|
| Template placeholder | `{customer_name}` | Parsed from `user_prompt_template` |
| Media button | Photo/Voice upload | Always present, populates `{customer_name}` |

This keeps the chain architecture clean while preserving the UX.

### 7.4 Chain Results Passed as Context (Not Replaced)

For backward compatibility, when step N's output feeds into step N+1, it's **prepended as context** (existing behavior). The `{step_N}` placeholder resolution is an **additional** mechanism on top of that. This ensures:
- Old chains without `{step_N}` still work
- New chains can use `{step_N}` for precise control
- Both mechanisms can coexist

### 7.5 Alias Resolution

Aliases are resolved **after** step references. If a prompt has `alias: "search"`, then `{search}` in a subsequent step resolves to step 1's output. This is more readable than `{step_1}`.

---

## 8. Migration Guide

### Running the Migration

```bash
# Create migration
cd backend
uv run alembic revision --autogenerate -m "Add chain page fields"

# Apply
uv run alembic upgrade head
```

### Seed Data

```bash
cd backend
uv run python Generator/seed_chain_pages.py
```

### Verifying

```bash
# Check chain page is accessible
curl http://localhost:8000/api/prompt-groups | jq '.[] | {name, is_chain_page, page_route}'

# Execute chain with inputs
curl -X POST http://localhost:8000/api/prompt-groups/1/execute-chain \
  -H "Content-Type: application/json" \
  -d '{"inputs": {"1": {"customer_name": "Ahmed Hassan"}}, "initial_input": ""}'
```

---

## Appendix A: API Request/Response Examples

### POST /api/prompt-groups/{group_id}/execute-chain

**Request:**
```json
{
  "inputs": {
    "1": {
      "customer_name": "Ahmed Hassan"
    }
  },
  "initial_input": ""
}
```

**Response:**
```json
{
  "group_id": 1,
  "group_name": "Guest Intelligence",
  "executed_at": "2026-01-07T14:30:00Z",
  "scheduled": false,
  "success": true,
  "steps_count": 2,
  "steps": [
    {
      "position": 1,
      "prompt_id": "guest-search",
      "prompt_version": 1,
      "alias": "search",
      "status": "success",
      "response": "Found 3 guests matching Ahmed Hassan...",
      "cached": false,
      "error": null
    },
    {
      "position": 2,
      "prompt_id": "guest-extract",
      "prompt_version": 1,
      "alias": "extraction",
      "status": "success",
      "response": "{guest_id: 42, name: 'Ahmed Hassan', ...}",
      "cached": false,
      "error": null
    }
  ],
  "final_output": "{guest_id: 42, name: 'Ahmed Hassan', ...}",
  "result_file": "data/prompt_group_results/group_1_20260107T143000.json",
  "result_id": 1
}
```

## Appendix B: Example Prompt Templates

### Step 1: guest-search (Input Step)

```
Search for guest: {customer_name}
Also bring the information about its reservations.
```

### Step 2: guest-extract (Output Step)

```
From the search results above, extract and format:
- Guest ID
- Full name
- Date of birth
- Special preferences
- Reservation history
- Loyalty status

Reference results: {step_1}
```

## Appendix C: File Change Summary

| File | Change Type | Description |
|------|-------------|-------------|
| `backend/app/models.py` | Modified | Add `alias`, `is_input_step`, `is_chain_page`, `page_route` fields |
| `backend/app/schemas.py` | Modified | Extend schemas with new fields + new request/response schemas |
| `backend/alembic/versions/xxx.py` | New | Migration for new columns |
| `backend/app/services/placeholders.py` | Modified | Add chain results to placeholder resolution |
| `backend/app/services/prompt_chain.py` | Modified | Add `page_mode`, `user_inputs`, chain results tracking |
| `backend/app/routes/prompt_groups.py` | Modified | Add `/execute-chain` endpoint |
| `frontend/src/types/prompt.ts` | Modified | Extend types + add chain types |
| `frontend/src/services/promptGroupsApi.ts` | Modified | Add `executeChain` function |
| `frontend/src/components/ui/ChainInputSection.tsx` | New | Input fields + media handling |
| `frontend/src/components/ui/ChainStepStatus.tsx` | New | Step status bar |
| `frontend/src/components/ui/ChainOutputSection.tsx` | New | Final output renderer |
| `frontend/src/pages/PromptChainPage.tsx` | New | Main chain page layout |
| `frontend/src/App.tsx` | Modified | Add wildcard route |
| `backend/Generator/seed_chain_pages.py` | New | Seed data for chain pages |
| `docs/IMPLEMENTATION_SPEC_CHAIN_PAGES.md` | New | This file |