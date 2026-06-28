# ConciergeOS — Prompting System Implementation Reference

> **Purpose**: Single-source implementation reference for the entire prompting system.  
> **Audience**: LLM agent capable of recreating the full prompting functionality from this document alone.  
> **Last Updated**: 2026-06-28

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Prompt Versioning System](#2-prompt-versioning-system)
3. [Placeholder System](#3-placeholder-system)
4. [LLM Integration & Prompt Resolution](#4-llm-integration--prompt-resolution)
5. [Response Caching](#5-response-caching)
6. [Prompt Groups Chain Execution](#6-prompt-groups-chain-execution)
7. [Background Scheduler](#7-background-scheduler)
8. [API Reference](#8-api-reference)
9. [Frontend API Clients](#9-frontend-api-clients)
10. [Initialization & Seeding](#10-initialization--seeding)
11. [File Map](#11-file-map)

---

## 1. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Frontend (React)                            │
│  PromptManagement.tsx  │  GuestSearch.tsx  │  PromptGroups.tsx      │
│                           │                             │                        │
│  promptsApi.ts  │  api.ts            │  promptGroupsApi.ts              │
└───────────────────────────────│───────────────────────────────┘
                                │ HTTP/JSON
┌───────────────────────────────│───────────────────────────────┐
│                        Backend (FastAPI)                        │
│                                                                  │
│  ┌──────────────┐   ┌──────────────────┐   ┌──────────────┐    │
│  │ routes/      │   │ services/        │   │ models.py    │    │
│  │ prompts.py   │──▶│ prompts.py       │──▶│ PromptVer.   │    │
│  │ prompt_groups│──▶│ prompt_chain.py  │──▶│ PromptGroup  │    │
│  │ guest_search │──▶│ llm.py           │──▶│ PromptGroupItem │    │
│  └──────────────┘   │ placeholders.py  │   │ PromptGroupSchedule│
│                     │ response_cache.py│   │ PromptGroupResult │    │
│                     │ prompt_scheduler │   └──────────────┘    │
│                     └──────────────────┘                        │
│                              │                                  │
│                     ┌────────┴────────┐                         │
│                     │ SQLite (hotel.db)│                        │
│                     │  - PromptVersions│                        │
│                     │  - PromptGroup   │                        │
│                     │  - PromptGroupItem│                       │
│                     │  - PromptGroupSchedule                     │
│                     │  - PromptGroupResult                       │
│                     └─────────────────┘                         │
│                              │                                  │
│                     ┌────────┴────────┐                         │
│                     │  LLM Endpoint   │                         │
│                     │  (OpenAI compat)│                         │
│                     └─────────────────┘                         │
└─────────────────────────────────────────────────────────────────────┘
```

### Data Flow: Guest Search

```
User enters name → GuestSearch.tsx
    → POST /api/guest-search { customer_name, prompt_id, version, runtime_variables }
    → query_guest_with_llm(customer_name, prompt_id, version, runtime_variables)
        → PromptStore.resolve_prompt(prompt_id, version)
            → (system_prompt, user_prompt_template) from DB
            → resolve_placeholders(system_prompt)         # static placeholders
            → resolve_all_placeholders(user_template, vars) # static + runtime
        → call_llm_with_db_tools_with_cache_flag(user_message, system_prompt=system_prompt)
            → [cache check] → LLM tool-calling loop → response
    → Return (llm_response, was_cached)
```

### Data Flow: Prompt Group Chain

```
User clicks "Recalculate Now" → PromptGroups.tsx
    → POST /api/prompt-groups/{id}/execute { initial_input }
    → execute_chain(group_id, initial_input)
        FOR EACH item in group (ordered by position):
            → PromptStore.resolve_prompt(item.prompt_id, item.prompt_version)
            → Build user_message: accumulated_context + user_template
            → call_llm_with_db_tools_with_cache_flag(user_message, system_prompt)
            → llm_response → accumulated_context for next step
        → Save results to data/prompt_group_results/{groupId}_{timestamp}.json
        → Return chain_result
```

---

## 2. Prompt Versioning System

### 2.1 Database Model

**Table**: `PromptVersions` (SQLite, hotel.db)

| Column               | Type          | Constraints                                  |
|-----------------------|---------------|----------------------------------------------|
| `id`                 | INTEGER       | PRIMARY KEY AUTOINCREMENT                    |
| `prompt_id`          | TEXT(100)     | NOT NULL (e.g., "guest-search")              |
| `version`            | INTEGER       | NOT NULL (1, 2, 3...)                        |
| `name`               | TEXT(200)     | NOT NULL (human-readable name)               |
| `intention`          | TEXT          | NOT NULL — What the assistant should do       |
| `restrictions`       | TEXT          | NOT NULL — Rules, constraints, limitations    |
| `output_structure`   | TEXT          | NOT NULL — Expected response format           |
| `user_prompt_template`| TEXT         | NOT NULL — Dynamic user message template      |
| `is_default`         | BOOLEAN       | DEFAULT FALSE                                |
| `meta_json`          | TEXT          | NULLABLE — JSON blob (author, changelog)      |
| `created_at`         | DATETIME      | DEFAULT NOW                                  |
| `updated_at`         | DATETIME      | DEFAULT NOW, ON UPDATE                       |

**Unique Constraint**: `(prompt_id, version)`

**SQLAlchemy Model** (`app/models.py`):
```python
class PromptVersion(Base):
    __tablename__ = "PromptVersions"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    prompt_id: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    intention: Mapped[str] = mapped_column(Text, nullable=False)
    restrictions: Mapped[str] = mapped_column(Text, nullable=False)
    output_structure: Mapped[str] = mapped_column(Text, nullable=False)
    user_prompt_template: Mapped[str] = mapped_column(Text, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    meta_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        UniqueConstraint("prompt_id", "version", name="uq_prompt_version"),
    )
```

### 2.2 Prompt Structure

Each prompt is composed of **4 structured fields** that are combined at runtime:

| Field                  | Purpose                                          | Used As                    |
|------------------------|--------------------------------------------------|----------------------------|
| `intention`            | Core purpose and role of the assistant           | System prompt prefix       |
| `restrictions`         | Rules, constraints, and limitations              | System prompt middle       |
| `output_structure`     | Expected response format/structure               | System prompt suffix       |
| `user_prompt_template` | Dynamic user message with placeholders           | User message               |

**System prompt composition** (in `PromptStore.resolve_prompt()`):
```python
parts = []
if prompt.intention:
    parts.append(prompt.intention)
if prompt.restrictions:
    parts.append(prompt.restrictions)
if prompt.output_structure:
    parts.append(prompt.output_structure)
system_prompt = "\n\n".join(parts) if parts else ""
# Then resolve static placeholders in system_prompt
system_prompt = resolve_placeholders(system_prompt)
```

### 2.3 PromptStore Service

**File**: `app/services/prompts.py`

The `PromptStore` class provides all CRUD operations for versioned prompts. It uses SQLAlchemy sessions and stores prompts in the SQLite database.

#### Key Methods

```python
class PromptStore:
    def __init__(self, db_session_factory=None):
        """If no factory provided, uses SessionLocal (default app session)."""
    
    # --- CRUD ---
    
    def create_prompt(
        self,
        prompt_id: str,
        name: str,
        intention: str,
        restrictions: str,
        output_structure: str,
        user_prompt_template: str,
        metadata_dict: dict | None = None,
    ) -> PromptVersion:
        """Create version 1 of a new prompt. Auto-sets as default.
        Raises ValueError if prompt_id already exists."""
    
    def get_prompt(self, prompt_id: str, version: int | None = None) -> PromptVersion | None:
        """Get specific version, or the default if version is None."""
    
    def list_prompts(self, prompt_id: str) -> list[PromptVersion]:
        """List all versions for a prompt_id, ordered by version number."""
    
    def list_all_prompts(self) -> list[dict]:
        """Summary of all prompt IDs with default version and count."""
    
    def update_prompt(
        self,
        prompt_id: str,
        version: int,
        name: str | None = None,
        intention: str | None = None,
        restrictions: str | None = None,
        output_structure: str | None = None,
        user_prompt_template: str | None = None,
        metadata_dict: dict | None = None,
    ) -> PromptVersion:
        """Update an existing prompt version (partial update)."""
    
    def delete_prompt(self, prompt_id: str, version: int) -> bool:
        """Delete a version. If deleted was default, set next-lower as default."""
    
    def duplicate_prompt(self, prompt_id: str, version: int, name: str | None = None) -> PromptVersion:
        """Duplicate a version, creating version+1 with copied content."""
    
    def set_default(self, prompt_id: str, version: int) -> PromptVersion:
        """Set a specific version as the default for this prompt_id."""
    
    def get_default_prompt(self, prompt_id: str) -> PromptVersion | None:
        """Get the default version for a prompt_id."""
    
    # --- Prompt Resolution ---
    
    def resolve_prompt(self, prompt_id: str, version: int | None = None) -> tuple[str, str]:
        """Resolve a prompt to (system_prompt, user_prompt_template).
        
        System prompt = intention + restrictions + output_structure (joined by \\n\\n)
        Static placeholders in system_prompt are resolved.
        Returns the raw user_prompt_template (runtime resolution happens in caller).
        """
    
    # --- Seeding ---
    
    def seed_default_prompts(self) -> None:
        """On startup: if no prompts exist, seed from SHARED_SYSTEM_PROMPT."""
```

#### `resolve_prompt()` — Detailed Behavior

```python
def resolve_prompt(self, prompt_id: str, version: int | None = None) -> tuple[str, str]:
    prompt = self.get_prompt(prompt_id, version)
    if prompt is None:
        raise ValueError(f"Prompt {prompt_id} not found")
    
    # Compose system prompt from structured fields
    parts = []
    if prompt.intention:
        parts.append(prompt.intention)
    if prompt.restrictions:
        parts.append(prompt.restrictions)
    if prompt.output_structure:
        parts.append(prompt.output_structure)
    
    system_prompt = "\n\n".join(parts) if parts else ""
    
    # Resolve static placeholders (DATABASE_TABLES, GUEST_INFORMATION, etc.)
    from app.services.placeholders import resolve_placeholders
    system_prompt = resolve_placeholders(system_prompt)
    
    return system_prompt, prompt.user_prompt_template
```

---

## 3. Placeholder System

**File**: `app/services/placeholders.py`

The placeholder system enables dynamic content injection into prompt templates at runtime. It operates in **two phases**:

### Phase 1: Static Placeholders

Resolved from database schema, current data, and tool definitions. These are the **same for every query** within a process lifetime.

| Placeholder Key      | Category | Resolver Function          | Description                                       |
|-----------------------|----------|----------------------------|---------------------------------------------------|
| `{DATABASE_TABLES}`   | schema   | `_resolve_database_tables()` | Full DB schema via SQLAlchemy introspection       |
| `{GUEST_INFORMATION}` | data     | `_resolve_guest_information()` | Current guest directory table                     |
| `{ROOM_INFORMATION}`  | data     | `_resolve_room_information()` | List of all hotel rooms                           |
| `{CURRENT_DATE}`      | context  | `_resolve_current_date()`    | Today's date in ISO format (YYYY-MM-DD)           |
| `{AVAILABLE_TOOLS}`   | schema   | `_resolve_available_tools()` | Human-readable tool descriptions                  |

**Resolution function**: `resolve_placeholders(text: str) -> str`

```python
def resolve_placeholders(text: str) -> str:
    """Replace all {PLACEHOLDER_NAME} with resolved content."""
    def replacer(match: re.Match) -> str:
        name = match.group(1).upper()
        meta = AVAILABLE_PLACEHOLDERS.get(name)
        if meta and meta.get("resolver") in RESOLVERS:
            try:
                return RESOLVERS[meta["resolver"]]()
            except Exception:
                return match.group(0)  # Leave unresolved on error
        return match.group(0)
    return re.sub(r"\{([A-Za-z_][A-Za-z0-9_]*)\}", replacer, text)
```

### Phase 2: Runtime Variables

Resolved from a **key-value map** supplied at call time. Uses the `{table.field}` pattern.

Examples:
- `{customers.first_name}` → `"John"`
- `{customers.last_name}` → `"Doe"`
- `{customers.name}` → `"John Doe"`
- `{rooms.room_id}` → `"42"`

**Resolution function**: `resolve_all_placeholders(text: str, runtime_variables: dict) -> str`

```python
def resolve_all_placeholders(text: str, runtime_variables: dict[str, str] | None = None) -> str:
    # Phase 1: Static placeholders (DATABASE_TABLES, etc.)
    text = resolve_placeholders(text)
    
    # Phase 2: Runtime variables ({table.field} → user-provided value)
    if runtime_variables:
        for key, value in runtime_variables.items():
            placeholder = f"{{{key}}}"
            if placeholder in text:
                text = text.replace(placeholder, str(value))
    
    return text
```

**Order matters**: Static placeholders are resolved first so their content never gets partially mangled by runtime-variable replacement.

### Runtime Variable Auto-Mapping (in `query_guest_with_llm`)

When a customer name is provided, the system auto-generates runtime variables:

```python
name_parts = customer_name.strip().split(None, 1)
if len(name_parts) == 2:
    first, last = name_parts
    runtime_vars = {
        "customers.first_name": first,
        "customers.last_name": last,
        "customers.name": customer_name,
    }
elif len(name_parts) == 1:
    runtime_vars = {
        "customers.first_name": name_parts[0],
        "customers.last_name": "",
        "customers.name": name_parts[0],
    }
# Merge user-provided runtime_variables (allow overrides)
if runtime_variables:
    runtime_vars.update(runtime_variables)
```

### Field Schema Discovery

The endpoint `GET /api/prompts/field-schema` returns structured database schema info so the frontend can show users what `{table.field}` variables are available. Returns a dict mapping table names to lists of column info.

---

## 4. LLM Integration & Prompt Resolution

### 4.1 Main Entry Point: `query_guest_with_llm()`

**File**: `app/services/llm.py`

```python
def query_guest_with_llm(
    customer_name: str,
    prompt_id: str = "guest-search",
    version: int | None = None,
    runtime_variables: dict[str, str] | None = None,
) -> tuple[str, bool]:
    """Query the LLM using a versioned prompt.
    
    Returns: (llm_response, was_cached)
    """
```

#### Resolution Flow

```
1. PromptStore.resolve_prompt(prompt_id, version)
   → (system_prompt, user_prompt_template)
   
   IF prompt not found → fallback to hardcoded:
   - SHARED_SYSTEM_PROMPT (system)
   - Hardcoded user prompt template
   
2. Build runtime variables from customer_name:
   - Auto-map to customers.first_name, customers.last_name, customers.name
   - Merge with caller-provided runtime_variables
   
3. Resolve user prompt template:
   user_prompt = resolve_all_placeholders(user_template, runtime_vars)
   
4. Call LLM:
   result, was_cached = call_llm_with_db_tools_with_cache_flag(
       user_prompt,
       system_prompt=final_system,
   )
```

### 4.2 Hardcoded Fallback (`SHARED_SYSTEM_PROMPT`)

**File**: `app/services/llm.py` (module-level)

The shared system prompt is built at module import time from 3 parts:

```python
_BASE_SYSTEM_INSTRUCTIONS = """\
You are a helpful hotel concierge assistant with access to database query tools.

When providing information about a guest, always use the following markdown structure:

### Guest [Number] (ID: [ID])
* **Full Name:** [First name] [Last name]
* **Date of Birth:** [YYYY-MM-DD]
* **Special Guest:** [Yes/No]
* **Special Preferences:** [Preferences or 'None']
* **Reservations:**
  1. **Reservation ID:** [ID]
     * **Room id:** [ID]
     * **Room:** [Room Name]
     * **Check-in:** [YYYY-MM-DD] | **Check-out:** [YYYY-MM-DD]
     * **Status:** [STATUS] | **Source:** [SOURCE]
  2. ... (continue for all reservations)
"""

_SCHEMA_DESCRIPTION = _generate_schema_from_database()  # SQLAlchemy introspection
_GUEST_INFORMATION = _generate_guest_information()       # Guest directory table

_SYSTEM_PROMPT_WITH_SCHEMA = f"""\
{_BASE_SYSTEM_INSTRUCTIONS}

{_SCHEMA_DESCRIPTION}

{_GUEST_INFORMATION}
## Available Tools
You have access to the following database query tools:
- `query_guests`: Search for guests by name, ID, or attributes
- `query_rooms`: Search for rooms by ID or name
- `query_reservations`: Search for reservations by various criteria
- `get_hotel_summary`: Get overall hotel statistics

Use these tools to answer questions about the hotel database. Always call the 
appropriate tool rather than guessing at data.
"""

SHARED_SYSTEM_PROMPT = _SYSTEM_PROMPT_WITH_SCHEMA
```

### 4.3 Tool Definitions

**File**: `app/services/llm.py`

Four tools are registered for database queries. Each tool supports batch execution via a `params` list wrapper:

| Tool Name            | Executor                         | Schema                    |
|----------------------|----------------------------------|---------------------------|
| `query_guests`       | `tool_logic.execute_query_guests`| `GuestQuerySchema`        |
| `query_rooms`        | `tool_logic.execute_query_rooms` | `RoomQuerySchema`         |
| `query_reservations` | `tool_logic.execute_query_reservations` | `ReservationQuerySchema` |
| `get_hotel_summary`  | `tool_logic.execute_get_hotel_summary` | `HotelSummarySchema`   |

Tool definitions are in OpenAI function-calling format. Batch schemas are created dynamically via `create_model()` to wrap the base schema in a `params` list.

### 4.4 LLM Client Configuration

```python
def get_llm_config() -> tuple[OpenAI, str]:
    """Dynamically fetch LLM client and model from global config.
    
    Uses config_manager.test_settings.models_endpoint for base URL.
    Falls back to first available model if configured model not found.
    Ultimate fallback: client + "facebook/opt-125m"
    """
```

### 4.5 Tool Calling Loop

The LLM call uses `call_llm_with_db_tools_with_cache_flag()` from `response_cache.py` which:

1. Checks response cache (by SHA256 of normalized user message)
2. Initializes conversation: `[system_message, user_message]`
3. Calls LLM with tools attached
4. If LLM returns tool calls → execute tools → append results → repeat
5. If LLM returns text (no tool calls) → return as final response
6. Max 100 turns before aborting
7. Caches successful response

---

## 5. Response Caching

**File**: `app/services/response_cache.py`

### Cache Architecture

- **Storage**: In-memory dict (swappable for Redis later)
- **Key**: SHA256 of normalized text (strip whitespace + lowercase)
- **TTL**: Default 3600 seconds (1 hour)
- **Scope**: Per-process (singleton)

### Key Classes & Functions

```python
class CacheStore:
    """In-memory LLM response cache with TTL-based expiration."""
    def get(self, key: str) -> CacheEntry | None
    def set(self, key: str, response: str, ttl: int | None = None) -> None
    def clear(self) -> int
    def stats -> dict  # { hits, misses, size, total_requests, hit_rate }

def generate_cache_key(text: str) -> str:
    """SHA256 of stripped+lowercased text."""

def generate_http_cache_key(url: str) -> str:
    """SHA256 of normalized URL (sorted query params)."""
```

### Cache Flow in LLM Call

```
_call_llm_impl(user_message, ..., use_cache=True):
    
    cache_key = generate_cache_key(user_message)
    
    if use_cache:
        cached = cache.get(cache_key)
        if cached:
            return cached.response, True  # CACHE HIT
    
    # ... LLM tool-calling loop ...
    
    final_result = assistant_message.content
    if use_cache:
        cache.set(cache_key, final_result)  # STORE
    
    return final_result, False  # CACHE MISS (fresh)
```

### Public API

```python
call_llm_with_db_tools(user_message, model=None, max_turns=100, use_cache=True, 
                       system_prompt=None, tool_definitions=None) -> str

call_llm_with_db_tools_with_cache_flag(user_message, ..., system_prompt=None, ...) -> tuple[str, bool]

cache_clear() -> int          # Clear all cached entries
cache_stats() -> dict         # Get hit/miss/size statistics
```

---

## 6. Prompt Groups — Chain Execution

### 6.1 Database Models

**File**: `app/models.py`

#### `PromptGroup`
```python
class PromptGroup(Base):
    __tablename__ = "PromptGroup"
    
    group_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    items: Mapped[list["PromptGroupItem"]] = relationship(
        back_populates="group", cascade="all, delete-orphan", 
        order_by="PromptGroupItem.position"
    )
    schedules: Mapped[list["PromptGroupSchedule"]] = relationship(
        back_populates="group", cascade="all, delete-orphan"
    )
    results: Mapped[list["PromptGroupResult"]] = relationship(
        back_populates="group", cascade="all, delete-orphan"
    )
```

#### `PromptGroupItem`
```python
class PromptGroupItem(Base):
    __tablename__ = "PromptGroupItem"
    
    item_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    group_id: Mapped[int] = mapped_column(Integer, ForeignKey("PromptGroup.group_id", ondelete="CASCADE"), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    prompt_id: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt_version: Mapped[int] = mapped_column(Integer, nullable=False)
    
    group: Mapped["PromptGroup"] = relationship(back_populates="items")
```

#### `PromptGroupSchedule`
```python
class PromptGroupSchedule(Base):
    __tablename__ = "PromptGroupSchedule"
    
    schedule_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    group_id: Mapped[int] = mapped_column(Integer, ForeignKey("PromptGroup.group_id", ondelete="CASCADE"), nullable=False)
    run_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    schedule_type: Mapped[str] = mapped_column(String(20), default="daily", server_default="daily")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    group: Mapped["PromptGroup"] = relationship(back_populates="schedules")
```

#### `PromptGroupResult`
```python
class PromptGroupResult(Base):
    __tablename__ = "PromptGroupResult"
    
    result_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    group_id: Mapped[int] = mapped_column(Integer, ForeignKey("PromptGroup.group_id", ondelete="CASCADE"), nullable=False)
    executed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    scheduled: Mapped[bool] = mapped_column(Boolean, default=False)
    result_file: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="running")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    group: Mapped["PromptGroup"] = relationship(back_populates="results")
```

### 6.2 Chain Execution Logic

**File**: `app/services/prompt_chain.py`

```python
def execute_chain(
    group_id: int,
    initial_input: str = "",
    scheduled: bool = False,
    db: Session | None = None,
) -> dict[str, Any]:
```

#### Execution Steps

```
1. Load PromptGroup by group_id (raise ValueError if not found)
2. Load PromptGroupItems ordered by position (raise ValueError if empty)
3. Create PromptGroupResult record (status="running")
4. Set accumulated_context = initial_input
5. FOR EACH item (in position order):
   a. PromptStore.resolve_prompt(item.prompt_id, item.prompt_version)
      → (system_prompt, user_template)
   b. Build user_message:
      IF accumulated_context:
          user_message = f"{accumulated_context}\n\n---\n\n{user_template}"
      ELSE:
          user_message = user_template
   c. call_llm_with_db_tools_with_cache_flag(user_message, system_prompt=system_prompt)
      → (llm_response, was_cached)
   d. Append step result to chain_steps[]
   e. accumulated_context = llm_response  # Feed to next step
   f. ON ERROR: Append error step, set accumulated_context = "[ERROR]: ..."
6. Build chain_result dict with all steps
7. Save to JSON file: data/prompt_group_results/group_{id}_{timestamp}.json
8. Update PromptGroupResult record (status, result_file, error_message)
9. Return chain_result
```

#### Result JSON Structure

```json
{
  "group_id": 1,
  "group_name": "My Chain",
  "executed_at": "2026-06-28T15:51:31+00:00",
  "scheduled": false,
  "success": true,
  "steps_count": 3,
  "steps": [
    {
      "position": 1,
      "prompt_id": "guest-search",
      "prompt_version": 1,
      "system_prompt": "...",
      "user_message": "...",
      "response": "...",
      "cached": false,
      "error": null
    }
  ],
  "final_output": "...",
  "result_file": "data/prompt_group_results/group_1_20260628T155131.json",
  "result_id": 1
}
```

### 6.3 is_active Behavior

When `PromptGroup.is_active` is `False`:
- The scheduler skips recovering schedules for this group on startup
- The scheduler skips execution at fire time (logs warning, returns without recording result)
- When toggled off, all active APScheduler jobs are immediately cancelled
- When toggled off, all schedule records are marked `active=False`

---

## 7. Background Scheduler

**File**: `app/services/prompt_scheduler.py`

### Architecture

- Uses **APScheduler** (`BackgroundScheduler`) for timing
- Singleton pattern (`PromptScheduler.get()`)
- Persists job state to `data/scheduler_state.json`
- Recovers schedules from database on startup

### Schedule Types

| Type     | Trigger             | Behavior                            |
|----------|---------------------|--------------------------------------|
| `none`   | `DateTrigger`       | One-shot execution at `run_at`       |
| `daily`  | `IntervalTrigger(days=1)` | Repeats daily from `run_at`    |
| `weekly` | `IntervalTrigger(weeks=1)` | Repeats weekly from `run_at`   |

### Key Methods

```python
class PromptScheduler:
    @classmethod
    def get(cls) -> "PromptScheduler":
        """Singleton accessor."""
    
    def start(self) -> None:
        """Start scheduler, recover persisted schedules."""
    
    def shutdown(self) -> None:
        """Shutdown scheduler gracefully."""
    
    def schedule_execution(
        self,
        schedule_id: int,
        group_id: int,
        run_at: datetime,
        schedule_type: str = "daily"
    ) -> str:
        """Add APScheduler job. Returns job_id."""
    
    def cancel_schedule(self, schedule_id: int) -> bool:
        """Cancel job by database schedule_id."""
    
    @staticmethod
    def _execute_group(group_id: int, schedule_id: int) -> None:
        """APScheduler callback. Checks is_active before executing."""
    
    def _recover_schedules(self) -> None:
        """On startup: reload active schedules for active groups."""
```

### Startup Recovery

```python
def _recover_schedules(self) -> None:
    # JOIN PromptGroupSchedule WITH PromptGroup
    # WHERE schedule.active == True
    #   AND schedule.run_at > now
    #   AND group.is_active == True
    # For each matching schedule:
    #   → schedule_execution(schedule_id, group_id, run_at, schedule_type)
```

### Execution Callback

```python
@staticmethod
def _execute_group(group_id: int, schedule_id: int) -> None:
    # 1. Check if group is still active (is_active == True)
    # 2. If disabled → log warning, return without recording result
    # 3. Call execute_chain(group_id, scheduled=True)
    # 4. Log result
```

---

## 8. API Reference

### 8.1 Prompt Versioning Endpoints

**Prefix**: `/api/prompts`

| Method   | Path                                        | Description                            | Request Body                    |
|----------|---------------------------------------------|----------------------------------------|---------------------------------|
| `GET`    | `/api/prompts`                              | List all prompt IDs (summary)          | —                               |
| `GET`    | `/api/prompts/placeholders`                 | List available placeholder definitions | —                               |
| `GET`    | `/api/prompts/field-schema`                 | Get DB field schema for runtime vars   | —                               |
| `POST`   | `/api/prompts/ai-improve`                   | AI-improve a prompt section via chat   | `AiImproveRequest`              |
| `POST`   | `/api/prompts/{prompt_id}/{version}/preview`| Preview rendered prompt                | —                               |
| `GET`    | `/api/prompts/{prompt_id}/default`          | Get default version                    | —                               |
| `GET`    | `/api/prompts/{prompt_id}/{version}`        | Get specific version                   | —                               |
| `GET`    | `/api/prompts/{prompt_id}`                  | List all versions for prompt_id        | —                               |
| `POST`   | `/api/prompts/{prompt_id}`                  | Create new version (v1)                | `CreatePromptRequest`           |
| `PUT`    | `/api/prompts/{prompt_id}/{version}`        | Update existing version                | `UpdatePromptRequest`           |
| `DELETE` | `/api/prompts/{prompt_id}/{version}`        | Delete a version                       | —                               |
| `POST`   | `/api/prompts/{prompt_id}/{version}/duplicate` | Duplicate (creates next version)    | `DuplicatePromptRequest`        |
| `PATCH`  | `/api/prompts/{prompt_id}/{version}/set-default` | Set as default                    | —                               |

**Important**: Static routes (`/placeholders`, `/field-schema`, `/ai-improve`) are defined BEFORE parameterized routes (`/{prompt_id}`) so FastAPI matches them correctly.

### 8.2 Guest Search Endpoints

**Prefix**: `/api/guest-search`

| Method   | Path                  | Description            | Request Body        |
|----------|-----------------------|------------------------|---------------------|
| `POST`   | `/api/guest-search`   | Search guest by name   | `GuestSearchRequest`|

**Request Schema** (`GuestSearchRequest`):
```python
class GuestSearchRequest(BaseModel):
    customer_name: str
    prompt_id: str = "guest-search"
    version: int | None = None
    runtime_variables: Dict[str, str] = {}
```

**Response Schema** (`GuestSearchResponse`):
```python
class GuestSearchResponse(BaseModel):
    query: str
    llm_response: str
    cached: bool = False
```

### 8.3 Prompt Groups Endpoints

**Prefix**: `/api/prompt-groups`

| Method   | Path                                                  | Description                          |
|----------|-------------------------------------------------------|--------------------------------------|
| `GET`    | `/api/prompt-groups`                                  | List all groups                      |
| `POST`   | `/api/prompt-groups`                                  | Create new group                     |
| `GET`    | `/api/prompt-groups/{group_id}`                       | Get group detail + items             |
| `PUT`    | `/api/prompt-groups/{group_id}`                       | Update group (name, items, order)    |
| `DELETE` | `/api/prompt-groups/{group_id}`                       | Delete group (cascades to items)     |
| `PATCH`  | `/api/prompt-groups/{group_id}/toggle`                | Toggle active state                  |
| `POST`   | `/api/prompt-groups/{group_id}/execute`               | Execute chain now                    |
| `POST`   | `/api/prompt-groups/{group_id}/schedule`              | Schedule execution                   |
| `DELETE` | `/api/prompt-groups/{group_id}/schedules/{schedule_id}`| Cancel specific schedule            |
| `DELETE` | `/api/prompt-groups/{group_id}/schedules`             | Clear all schedules                  |
| `GET`    | `/api/prompt-groups/{group_id}/results`               | Get execution history                |
| `GET`    | `/api/prompt-groups/results/{result_id}/download`     | Download result JSON file            |

### 8.4 Pydantic Schemas

**File**: `app/schemas.py`

#### Prompt Versioning

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
    created_at: str
    updated_at: str

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
```

#### Prompt Groups

```python
class PromptGroupSchema(BaseModel):
    group_id: int
    name: str
    description: str | None = None
    is_active: bool = True
    created_at: str
    updated_at: str
    items: List[PromptGroupItemSchema] = []
    schedules: List[PromptGroupScheduleSchema] = []
    results: List[PromptGroupResultSchema] = []

class PromptGroupItemSchema(BaseModel):
    item_id: int
    group_id: int
    position: int
    prompt_id: str
    prompt_version: int

class PromptGroupScheduleSchema(BaseModel):
    schedule_id: int
    group_id: int
    run_at: str
    schedule_type: str = "daily"
    active: bool
    created_at: str

class PromptGroupResultSchema(BaseModel):
    result_id: int
    group_id: int
    executed_at: str
    scheduled: bool
    result_file: str | None = None
    status: str
    error_message: str | None = None

class CreateGroupRequest(BaseModel):
    name: str
    description: str | None = None
    items: List[PromptGroupItemCreate] = []

class UpdateGroupRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    is_active: bool | None = None
    items: List[PromptGroupItemCreate] | None = None

class PromptGroupScheduleCreate(BaseModel):
    run_at: str  # ISO 8601
    schedule_type: str = "daily"  # "none", "daily", "weekly"
```

---

## 9. Frontend API Clients

### 9.1 Prompts API Client

**File**: `frontend/src/services/promptsApi.ts`

```typescript
export const promptsApi = {
  listAll(): Promise<PromptSummary[]>,
  listVersions(promptId: string): Promise<PromptVersion[]>,
  getDefault(promptId: string): Promise<PromptVersion>,
  getByVersion(promptId: string, version: number): Promise<PromptVersion>,
  getPrompt(promptId: string, version: number): Promise<PromptVersion>,  // alias
  create(promptId: string, data: CreatePromptRequest): Promise<PromptVersion>,
  update(promptId: string, version: number, data: UpdatePromptRequest): Promise<PromptVersion>,
  remove(promptId: string, version: number): Promise<Record<string, unknown>>,
  duplicate(promptId: string, version: number, data?: DuplicatePromptRequest): Promise<PromptVersion>,
  setDefault(promptId: string, version: number): Promise<PromptVersion>,
  aiImprove(section: string, currentText: string, conversation: Array<{role,content}>, model?: string): Promise<{improved_text: string}>,
};

// Additional standalone functions:
export function listPlaceholders(): Promise<PlaceholderDefinition[]>
export function previewPrompt(promptId: string, version: number): Promise<{resolved_system_prompt, resolved_user_template}>
export function getFieldSchema(): Promise<Record<string, ColumnInfo[]>>
```

### 9.2 Prompt Groups API Client

**File**: `frontend/src/services/promptGroupsApi.ts`

Provides methods for group CRUD, execution, scheduling, and result management matching the backend endpoints.

### 9.3 Guest Search API Integration

**File**: `frontend/src/services/api.ts`

The guest search API accepts optional prompt selection:

```typescript
guestSearchApi.search(customerName, {
  prompt_id?: string,   // defaults to "guest-search"
  version?: number,     // defaults to None (use default version)
})
```

---

## 10. Initialization & Seeding

### 10.1 Prompt Seeding

On application startup, `PromptStore.seed_default_prompts()` checks if any prompts exist. If the database is empty, it seeds a default `guest-search:v1` prompt:

```python
def seed_default_prompts(self) -> None:
    # If prompts already exist, do nothing
    count = db.execute(select(PromptVersion).limit(1)).scalars().first()
    if count is not None:
        return
    
    from app.services.llm import SHARED_SYSTEM_PROMPT
    
    prompt = PromptVersion(
        prompt_id="guest-search",
        version=1,
        name="Guest Search v1",
        intention=SHARED_SYSTEM_PROMPT,  # Full hardcoded system prompt
        restrictions="",
        output_structure="",
        user_prompt_template=(
            "Please find all information about the guest named. "
            "The guest's name can have it's name translated into the following languages "
            "Arabic, Chinese, Devanagari, Japanese, Korean, Latin or Nordic. "
            "It is unclear if is the user's first name or last name. "
            "Retry once with every translated language if needed. "
            "Also bring the information about its reservations. : {customer_name}"
        ),
        is_default=True,
        meta_json=json.dumps({
            "author": "system",
            "migrated_from": "app/services/llm.py",
            "changelog": "Initial seed from hardcoded prompts",
        }),
    )
```

### 10.2 Scheduler Initialization

The scheduler is started via `PromptScheduler.get().start()` which:
1. Recovers pending schedules from the database (active schedules for active groups)
2. Starts the APScheduler background daemon
3. Persists job state to `data/scheduler_state.json`

### 10.3 Router Registration

In `app/main.py`:
```python
from app.routes.prompts import router as prompts_router
from app.routes.prompt_groups import router as prompt_groups_router
app.include_router(prompts_router)
app.include_router(prompt_groups_router)
```

---

## 11. File Map

### Backend Files

| File                              | Responsibility                                    |
|-----------------------------------|---------------------------------------------------|
| `app/models.py`                   | SQLAlchemy models (`PromptVersion`, `PromptGroup`, `PromptGroupItem`, `PromptGroupSchedule`, `PromptGroupResult`) |
| `app/schemas.py`                  | Pydantic request/response schemas                |
| `app/services/prompts.py`         | `PromptStore` — CRUD + `resolve_prompt()`        |
| `app/services/placeholders.py`    | Placeholder resolution (static + runtime)        |
| `app/services/llm.py`             | LLM client, tool definitions, `query_guest_with_llm()`, `SHARED_SYSTEM_PROMPT` |
| `app/services/response_cache.py`  | Response caching + diagnostic logging + tool calling loop |
| `app/services/prompt_chain.py`    | `execute_chain()` — sequential prompt chain       |
| `app/services/prompt_scheduler.py`| `PromptScheduler` — APScheduler + recovery        |
| `app/routes/prompts.py`           | Prompt versioning API endpoints                   |
| `app/routes/prompt_groups.py`     | Prompt groups API endpoints                       |
| `app/routes/guest_search.py`      | Guest search endpoint (uses `query_guest_with_llm`) |
| `app/main.py`                     | FastAPI app + router registration                 |

### Frontend Files

| File                                        | Responsibility                            |
|---------------------------------------------|-------------------------------------------|
| `frontend/src/types/prompt.ts`              | TypeScript interfaces for prompts         |
| `frontend/src/services/promptsApi.ts`       | API client for prompt CRUD                |
| `frontend/src/services/promptGroupsApi.ts`  | API client for prompt groups              |
| `frontend/src/services/api.ts`              | Guest search API (with prompt params)     |
| `frontend/src/pages/PromptManagement.tsx`   | Full-page prompt editor                   |
| `frontend/src/pages/PromptGroups.tsx`       | Prompt groups management page             |
| `frontend/src/pages/GuestSearch.tsx`        | Guest search with prompt selector         |
| `frontend/src/components/ui/PromptSelector.tsx` | Prompt version dropdown component     |

### Data Files

| Path                                          | Purpose                          |
|-----------------------------------------------|----------------------------------|
| `data/prompt_group_results/*.json`            | Chain execution results          |
| `data/scheduler_state.json`                   | APScheduler job state            |

### Database Tables (SQLite, hotel.db)

| Table                  | Purpose                              |
|------------------------|--------------------------------------|
| `PromptVersions`       | Versioned prompt storage             |
| `PromptGroup`          | Named prompt group collections       |
| `PromptGroupItem`      | Ordered prompt+version entries       |
| `PromptGroupSchedule`  | Scheduled execution records          |
| `PromptGroupResult`    | Execution result records             |

---

*End of implementation reference.*