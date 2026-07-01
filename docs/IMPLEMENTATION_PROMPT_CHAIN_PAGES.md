# Prompt Chain Pages — Cross-Step Result Passing

> **Status:** Design phase
> **Replaces:** Guest Search page (`/guest-search`)
> **Related:** [Prompt Groups](./DOCUMENTATION.md)

## Overview

Prompt Chain Pages extend the existing **PromptGroup** concept to enable building entire application pages from already-existing prompts. Each prompt in a chain receives the output of the previous prompt as context, allowing complex multi-step data processing pipelines where results flow between steps.

The core innovation is a new placeholder syntax `{step_N}` that lets any prompt in a chain explicitly reference the output of any prior step, rather than blindly appending all previous outputs.

## Motivation

### Current Limitation

The existing PromptGroup system executes a sequence of prompts sequentially, but:

1. **Blind accumulation**: Each step receives the raw text of all previous outputs concatenated together — no control over which data is relevant
2. **No visibility**: Chain execution produces a JSON file on disk — the intermediate steps are invisible
3. **No user interaction**: Chains can only be triggered via API, not rendered as interactive pages with input fields
4. **No aliasing**: Steps are referenced only by position number — `{step_1}` is not memorable

### Goal

Build a **configurable page system** where:

- A **PromptGroup** defines the "page logic" — the sequence of prompts that produce the page content
- The **first step** provides user-facing input fields (e.g., guest name search)
- **Middle steps** transform and enrich the data, referencing prior step outputs
- The **final step** produces the rendered page content (tables, cards, reports)
- Each step's LLM output is **explicitly referenced** via `{step_N}` or `{alias}` placeholders
- The page is **fully configurable** — different chains power different pages without code changes

## Architecture

### Component Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     PromptChain Page                         │
│                                                              │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐ │
│  │ Step 1   │──▶│ Step 2   │──▶│ Step 3   │──▶│ Step 4   │ │
│  │ (Input)  │   │ (Extract)│   │ (Enrich) │   │ (Render) │ │
│  │          │   │          │   │          │   │          │ │
│  │ [Form    ]   │ ✓ Status │   │ ✓ Status │   │ 📊 Final │ │
│  │  Fields]   │   │ Bar      │   │ Bar      │   │ Output │ │
│  └──────────┘   └──────────┘   └──────────┘   └──────────┘ │
│       │               │               │               │      │
│       ▼               ▼               ▼               ▼      │
│  {customer_name}  {step_1}        {step_2}       {step_3}    │
│  {filter}                           {result}             {result}
└─────────────────────────────────────────────────────────────┘
```

### Data Flow

```
User fills input form
        │
        ▼
POST /api/prompt-groups/{group_id}/execute-chain
   body: { "inputs": { "1": { "customer_name": "Ahmed" } } }
        │
        ▼
┌──────────────────────────────────────────────┐
│ execute_chain(page_mode=True)                 │
│                                               │
│  For each step in group.items:                │
│    1. Resolve {step_N} placeholders in template
│       using chain_results from prior steps    │
│    2. Resolve {DATABASE_TABLES}, {CURRENT_DATE}│
│    3. Build user message + system prompt      │
│    4. Call LLM                                │
│    5. Store response in chain_results[step]   │
│                                               │
│  Return: chain_results per step + final_output │
└──────────────────────────────────────────────┘
        │
        ▼
Frontend renders:
  - Input fields (from step 1's template)
  - Status bars (from steps 2..N-1)
  - Final output (from step N)
```

## New Placeholder System

### Syntax

Three levels of cross-step referencing:

| Placeholder | Resolves To | Example |
|-------------|-------------|---------|
| `{step_N}` | Raw output of step at position N (1-indexed) | `{step_1}` → "Found guests: Ahmed, María" |
| `{step_N.result}` | Same as `{step_N}` (explicit form) | `{step_2.result}` |
| `{alias}` | Output of step with this alias | `{extraction}` → if alias "extraction" was set on step 1 |

### Placeholder Resolution Order

1. **Static placeholders** (unchanged): `{DATABASE_TABLES}`, `{GUEST_INFORMATION}`, `{CURRENT_DATE}`, etc.
2. **Runtime variables** (unchanged): `{table.field}` → user-provided values
3. **Chain results** (NEW): `{step_1}`, `{alias}` → outputs from prior chain steps
4. **Cross-step references** (NEW): `{step_2.user_name}` → specific field from chain result

### Example Chain with Placeholders

```yaml
Chain: "guest-intelligence"
Steps:
  - position: 1
    prompt_id: guest-search
    alias: "search"
    user_prompt: "Search for guest: {customer_name}"
    # No cross-step refs — this is the input step

  - position: 2
    prompt_id: guest-extract
    alias: "extraction"
    user_prompt: "Extract guest IDs from: {step_1}"
    # References: full output of step 1

  - position: 3
    prompt_id: guest-profile
    alias: "enrichment"
    user_prompt: "Get full profiles for these IDs: {step_2.result}"
    # References: just the structured part of step 2

  - position: 4
    prompt_id: report-render
    alias: "report"
    user_prompt: "Format this report: {step_3}"
    # References: full output of step 3
```

## Backend Changes

### 1. New Placeholder Category

**File:** `backend/app/services/placeholders.py`

Add a `CHAIN_RESULT` category:

```python
CHAIN_PLACEHOLDERS = {
    "step": {
        "description": "Output of a chain step (position N)",
        "category": "chain",
        "pattern": r"\{step_(\d+)(?:\.result)?\}",
    },
    "alias": {
        "description": "Output of a chain step by its alias label",
        "category": "chain",
        "pattern": r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}",
    },
}
```

Update `resolve_placeholders()` to accept an optional `chain_results` parameter:

```python
def resolve_placeholders(
    text: str,
    chain_results: dict[int, str] | None = None,
    aliases: dict[str, int] | None = None,  # alias_name -> step_position
):
    """Extended placeholder resolution with chain result support."""
    # ... existing static placeholder resolution ...

    # NEW: Chain result resolution
    if chain_results:
        # Replace {step_N} references
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
            text = re.sub(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}", alias_resolver, text)

    return text
```

### 2. Updated Chain Execution

**File:** `backend/app/services/prompt_chain.py`

Update `execute_chain()` to support chain results:

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
        page_mode: If True, treat first step as user-input step.
        user_inputs: {step_position: {field: value}} mapping for page mode.

    Returns:
        dict with chain_results, per-step details, and final_output.
    """
    chain_results: dict[int, str] = {}
    aliases: dict[str, int] = {}

    # Build alias map from items
    for item in items:
        if item.alias:
            aliases[item.alias] = item.position
        aliases[f"step_{item.position}"] = item.position

    for item in items:
        # Resolve user_inputs for this step if page_mode
        if page_mode and item.position in user_inputs:
            runtime_vars = user_inputs[item.position]
        else:
            runtime_vars = {}

        # Resolve placeholders: static + runtime + chain results
        system_prompt, user_template = prompt_store.resolve_prompt(
            item.prompt_id, item.prompt_version
        )
        user_message = resolve_placeholders(
            user_template,
            chain_results=chain_results,
            aliases=aliases,
        )
        user_message = resolve_all_placeholders(user_message, runtime_vars)

        # Add accumulated context for backward compat
        if item.position > 1 and chain_results.get(item.position - 1):
            user_message = (
                f"{chain_results[item.position - 1]}\n\n---\n\n{user_message}"
            )

        # Call LLM
        llm_response, was_cached = call_llm(...)

        # Store in chain_results
        chain_results[item.position] = llm_response

        # Add to step result
        step_result["chain_results"] = dict(chain_results)
```

### 3. New Model Fields

**File:** `backend/app/models.py`

Add `alias` to `PromptGroupItem`:

```python
class PromptGroupItem(Base):
    """Single prompt+version entry within a PromptGroup, with ordering."""
    __tablename__ = "PromptGroupItem"

    item_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    group_id: Mapped[int] = mapped_column(Integer, ForeignKey("PromptGroup.group_id", ondelete="CASCADE"), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    prompt_id: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt_version: Mapped[int] = mapped_column(Integer, nullable=False)
    alias: Mapped[str | None] = mapped_column(String(50), nullable=True, comment="Human-readable alias for cross-step referencing")
    is_input_step: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0", comment="Mark this step as the user-input entry point for page mode")
```

Add `is_chain_page` and `page_route` to `PromptGroup`:

```python
class PromptGroup(Base):
    __tablename__ = "PromptGroup"

    group_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    is_chain_page: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0", comment="If True, this group renders as a full page")
    page_route: Mapped[str | None] = mapped_column(String(200), nullable=True, comment="URL route for chain page (e.g., /guest-intel)")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

### 4. New API Endpoint

**File:** `backend/app/routes/prompt_groups.py`

```python
@router.post("/{group_id}/execute-chain")
def execute_chain_page(group_id: int, req: ChainExecutionRequest):
    """Execute chain with user inputs (page mode).

    The first step receives user_inputs, all subsequent steps
    receive the output of their predecessor via chain results.
    """
    result = execute_chain(
        group_id,
        initial_input=req.initial_input,
        page_mode=True,
        user_inputs=req.inputs,
    )
    return result


class ChainExecutionRequest(BaseModel):
    """Request body for page-mode chain execution."""
    inputs: dict[int, dict[str, str]] = {}
    """{step_position: {field_name: value}} for user-provided inputs"""
    initial_input: str = ""
    """Raw text passed to the first step before template resolution"""
```

### 5. Migration

**File:** `backend/alembic/versions/xxx_add_chain_page_fields.py`

```python
def upgrade():
    op.add_column("PromptGroupItem", sa.Column("alias", sa.String(50), nullable=True))
    op.add_column("PromptGroupItem", sa.Column("is_input_step", sa.Boolean, server_default="0"))
    op.add_column("PromptGroup", sa.Column("is_chain_page", sa.Boolean, server_default="0"))
    op.add_column("PromptGroup", sa.Column("page_route", sa.String(200), nullable=True))

def downgrade():
    op.drop_column("PromptGroup", "page_route")
    op.drop_column("PromptGroup", "is_chain_page")
    op.drop_column("PromptGroupItem", "is_input_step")
    op.drop_column("PromptGroupItem", "alias")
```

## Frontend Changes

### 1. New TypeScript Types

**File:** `frontend/src/types/prompt.ts`

```typescript
export interface PromptGroupItem {
  item_id: number;
  group_id: number;
  position: number;
  prompt_id: string;
  prompt_version: number;
  alias?: string;          // NEW: Human-readable alias
  is_input_step?: boolean;  // NEW: Mark as user-input entry point
}

export interface PromptGroupItemCreate {
  position: number;
  prompt_id: string;
  prompt_version: number;
  alias?: string;
}

export interface PromptGroup {
  group_id: number;
  name: string;
  description: string | null;
  is_active: boolean;
  is_chain_page?: boolean;   // NEW
  page_route?: string | null; // NEW
  created_at: string;
  updated_at: string;
  items: PromptGroupItem[];
  schedules: PromptGroupSchedule[];
  results: PromptGroupResult[];
}

// NEW: Chain page types
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
  inputs: Record<string, string>;
}

export interface ChainExecutionResult {
  chain_id: string;
  group_id: number;
  group_name: string;
  executed_at: string;
  status: "success" | "failed";
  steps: ChainStepResult[];
  final_output: string | null;
}
```

### 2. New Chain Page Component

**File:** `frontend/src/components/ui/PromptChainPage.tsx`

The chain page component renders:

1. **Input section** (first step or step marked as `is_input_step`):
   - Parse the step's `user_prompt_template` for `{placeholder}` patterns
   - Generate input fields based on placeholder names:
     - `{customer_name}` → text input with label "Customer Name"
     - `{date_range}` → date inputs
     - `{filter_status}` → select dropdown
   - Render a "Run Chain" button

2. **Chain status section** (steps 2 to N-1):
   - Collapsible status bars showing:
     - Prompt ID + version
     - Alias (human-readable label)
     - References (which `{step_N}` placeholders it uses)
     - Status indicator (running/success/failed)
     - Execution time
     - Brief preview of output

3. **Output section** (final step):
   - Full rendering of the last step's LLM output
   - Copy button, expand/collapse
   - Re-run button that triggers the entire chain again

4. **Header**:
   - Chain name and description
   - "Powered by" indicator
   - Quick actions: re-run, history, settings

### 3. Input Field Inference from Templates

The component parses `user_prompt_template` to detect placeholder patterns:

```typescript
function inferInputFields(template: string): InputField[] {
  const patterns: InputField[] = [];

  // Match {placeholder_name} patterns
  const placeholderRegex = /\{([a-zA-Z_][a-zA-Z0-9_]*)\}/g;
  let match;

  while ((match = placeholderRegex.exec(template)) !== null) {
    const name = match[1];
    // Skip chain result placeholders (step_*, alias references)
    if (name.startsWith('step_') || name.match(/^[a-z]+$/)) continue;

    // Skip known static placeholders
    if (KNOWN_PLACEHOLDERS.has(name)) continue;

    // Skip runtime variable prefixes (table.field patterns)
    if (name.includes('.')) continue;

    // Generate input field
    const label = name
      .replace(/_/g, ' ')
      .replace(/\b\w/g, c => c.toUpperCase());
    patterns.push({ name, label, type: inferFieldType(name) });
  }

  return patterns;
}

function inferFieldType(name: string): 'text' | 'date' | 'select' {
  if (name.includes('date') || name.includes('time')) return 'date';
  if (name.includes('filter') || name.includes('status') || name.includes('type')) return 'select';
  return 'text';
}
```

### 4. New Page Route

**File:** `frontend/src/pages/PromptChainPage.tsx`

```typescript
// Route: /prompt-chains/:route
export default function PromptChainPage() {
  const { route } = useParams<{ route: string }>();
  const [group, setGroup] = useState<PromptGroup | null>(null);
  const [chainResult, setChainResult] = useState<ChainExecutionResult | null>(null);
  const [inputs, setInputs] = useState<Record<number, Record<string, string>>>({});

  useEffect(() => {
    // Load chain page definition by page_route
    const loadChainPage = async () => {
      const groups = await promptGroupsApi.list();
      const page = groups.find(g => g.page_route === route);
      if (page) setGroup(page);
    };
    loadChainPage();
  }, [route]);

  const handleRun = async () => {
    const result = await promptGroupsApi.executeChain(group.group_id, inputs);
    setChainResult(result);
  };

  if (!group) return <Loading />;

  return (
    <div className="mx-auto max-w-7xl px-4 py-8">
      {/* Header */}
      <PageHeader title={group.name} description={group.description} />

      {/* Input Section (first step) */}
      <ChainInputSection
        step={group.items[0]}
        inputs={inputs}
        onInputChange={setInputs}
        onRun={handleRun}
      />

      {/* Chain Steps (intermediate) */}
      {chainResult?.steps.slice(1, -1).map(step => (
        <ChainStepStatus key={step.position} step={step} />
      ))}

      {/* Final Output (last step) */}
      {chainResult && (
        <ChainOutputSection
          step={chainResult.steps[chainResult.steps.length - 1]}
          output={chainResult.final_output}
        />
      )}
    </div>
  );
}
```

### 5. Update Navigation

Add chain page links to the navigation menu:

**File:** `frontend/src/components/Header.tsx`

```typescript
// New nav items for chain pages
{
  label: "Guest Intelligence",
  href: "/prompt-chains/guest-intel",
},
```

## Example: Guest Intelligence Chain

This chain replaces the current Guest Search page. It's configured as a PromptGroup:

```json
{
  "group_id": 1,
  "name": "Guest Intelligence",
  "description": "Comprehensive guest profile and preference analysis",
  "is_chain_page": true,
  "page_route": "/guest-intel",
  "items": [
    {
      "position": 1,
      "prompt_id": "guest-search",
      "prompt_version": 1,
      "alias": "search",
      "is_input_step": true
    },
    {
      "position": 2,
      "prompt_id": "guest-extract",
      "prompt_version": 1,
      "alias": "extraction"
    },
    {
      "position": 3,
      "prompt_id": "guest-profile",
      "prompt_version": 1,
      "alias": "enrichment"
    },
    {
      "position": 4,
      "prompt_id": "report-render",
      "prompt_version": 1,
      "alias": "report",
      "is_output_step": true
    }
  ]
}
```

### Step Templates

**Step 1** (search) — user fills `{customer_name}`:
```
Search for guest: {customer_name}
Also bring the information about its reservations.
```

**Step 2** (extraction) — references `{step_1}`:
```
From the search results above, extract:
- All guest IDs found
- All guest names
- Any reservation IDs mentioned
Format as a structured list.
```

**Step 3** (enrichment) — references `{step_2.result}`:
```
Using these guest IDs, retrieve full profile information:
{step_2.result}

For each guest, include:
- Complete personal details
- All reservation history
- Special preferences and notes
- Loyalty status
```

**Step 4** (report) — references `{step_3.result}`:
```
Format this guest intelligence report:
{step_3.result}

Create a structured report with:
- Guest summary cards (name, loyalty, preferences)
- Reservation timeline
- Preference analysis
- Actionable recommendations for hospitality staff
```

## API Endpoints Summary

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/prompt-groups` | List all groups (existing) |
| GET | `/api/prompt-groups/{id}` | Get single group (existing) |
| POST | `/api/prompt-groups/{id}/execute` | Execute chain (existing, no inputs) |
| **POST** | **`/api/prompt-groups/{id}/execute-chain`** | **Execute with user inputs (page mode)** |
| GET | `/api/prompt-groups/{id}/results` | Get execution history (existing) |
| GET | `/api/prompt-groups/results/{id}/download` | Download result file (existing) |

## Routing Table

| Route | Component | Source |
|-------|-----------|--------|
| `/prompt-groups` | PromptGroups (existing list) | Existing |
| `/prompt-chains/:route` | PromptChainPage (new) | New page |
| `/guest-search` | GuestSearch (legacy) | Existing — eventually removed |
| `/prompt-management` | PromptManagement (existing) | Existing — add chain page config |

## Implementation Phases

### Phase 1: Core Infrastructure
- [ ] Add `alias` and `is_input_step` to `PromptGroupItem` model
- [ ] Add `is_chain_page` and `page_route` to `PromptGroup` model
- [ ] Create Alembic migration
- [ ] Update schemas (Pydantic)
- [ ] Update TypeScript types

### Phase 2: Chain Execution Engine
- [ ] Update `resolve_placeholders()` in `placeholders.py` to accept `chain_results`
- [ ] Update `execute_chain()` in `prompt_chain.py` to:
  - Build alias map from items
  - Store each step's output in `chain_results`
  - Pass `chain_results` to placeholder resolver before each step
  - Return per-step details with chain context
- [ ] Add `POST /api/prompt-groups/{id}/execute-chain` endpoint
- [ ] Add `ChainExecutionRequest` schema

### Phase 3: Frontend — Chain Page Component
- [ ] Create `PromptChainPage.tsx` component
- [ ] Create `ChainInputSection.tsx` (input fields from template)
- [ ] Create `ChainStepStatus.tsx` (collapsed status bar)
- [ ] Create `ChainOutputSection.tsx` (final output renderer)
- [ ] Add input field inference utility (`inferInputFields`)
- [ ] Wire up to API

### Phase 4: Navigation & Routing
- [ ] Add `/prompt-chains/:route` route
- [ ] Add chain page configuration modal in PromptManagement
- [ ] Add navigation items for chain pages
- [ ] Update `promptGroupsApi` to support `executeChain`

### Phase 5: Migration from Guest Search
- [ ] Create seed data for "Guest Intelligence" chain
- [ ] Replace Guest Search page with chain page
- [ ] Remove or deprecate old `/guest-search` endpoint
- [ ] Update navigation to point to new chain page

## Backward Compatibility

All changes are **backward compatible**:

- The `alias` field on `PromptGroupItem` is nullable — existing chains without aliases work unchanged
- The `is_chain_page` flag on `PromptGroup` defaults to `false` — existing groups retain their current behavior
- The `execute-chain` endpoint is new — the existing `execute` endpoint is unchanged
- The `{step_N}` placeholder resolution only activates when `chain_results` is provided (page mode)

