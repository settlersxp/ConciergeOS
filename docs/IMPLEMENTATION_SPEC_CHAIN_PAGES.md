# Implementation Spec: Prompt Chain Pages

> **Created:** 2026-01-07
> **Last Updated:** 2026-02-07
> **Status:** Complete
> **Related:** [IMPLEMENTATION_PROMPT_CHAIN_PAGES.md](./IMPLEMENTATION_PROMPT_CHAIN_PAGES.md)
> **Purpose:** Single source of truth — detailed implementation spec, checklist, and architecture for the Prompt Chain Pages feature.

---

## Table of Contents

1. [Overview & Architecture](#1-overview--architecture)
   1.1 [Multimodal Name Extraction](#15-multimodal-name-extraction)
2. [Implementation Checklist](#2-implementation-checklist)
3. [Phase 1: Backend Infrastructure](#3-phase-1-backend-infrastructure)
4. [Phase 2: Chain Execution Engine](#4-phase-2-chain-execution-engine)
5. [Phase 3: Frontend Types & API Client](#5-phase-3-frontend-types--api-client)
6. [Phase 4: Frontend Components](#6-phase-4-frontend-components)
7. [Phase 5: Routing & GuestSearch Replacement](#7-phase-5-routing--guestsearch-replacement)
8. [Design Decisions](#8-design-decisions)
9. [Migration Guide](#9-migration-guide)
10. [Appendix A: API Request/Response Examples](#appendix-a-api-requestresponse-examples)
11. [Appendix B: Example Prompt Templates](#appendix-b-example-prompt-templates)
12. [Appendix C: File Change Summary](#appendix-c-file-change-summary)

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
3. **Executes** each step sequentially (step-by-step), passing each step's output into the next step via `{step_N}` placeholder references
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

### Execution Order Diagram

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

### 1.5 Multimodal Name Extraction

The ChainInputSection component (Phase 5A) depends on a **multimodal name extraction** subsystem that enables operators to extract guest names from images (ID cards, booking confirmations, handwritten notes) and audio recordings (voice input). This section documents that subsystem.

#### 1.5.1 Overview

| Feature | Description |
|---------|-------------|
| Photo Upload | Select an image file from device. Display preview, allow region selection, send to LLM for name extraction. |
| Camera Capture | On mobile devices, open rear camera directly. Same preview/region/extraction flow. |
| Voice Input | Record audio via browser MediaRecorder API. Send audio blob to LLM for speech-to-text name extraction. |

After extraction, the LLM returns a name string that auto-populates the `{customer_name}` input field. The operator reviews, edits if needed, then presses Search.

**Models Used:**

| Modality | Model | Endpoint |
|----------|-------|----------|
| Vision | Configured LLM (Qwen3-VL etc.) | Existing vLLM (OpenAI-compatible) |
| Audio | Configured LLM (Gemma4 etc.) | Existing vLLM (OpenAI-compatible) |

The actual model is determined by the `model_id` parameter (optional) or falls back to the default model configured in `config.json`.

#### 1.5.2 Backend Schema: `NameExtractionResponse`

**File:** `backend/app/schemas.py`

```python
class NameExtractionResponse(BaseModel):
    """Response from the extract-name endpoint (multimodal name extraction)."""
    extracted_name: str = Field(..., description="The name extracted from the media by the LLM")
    source: str = Field(..., description="Source modality: 'image' or 'audio'")
```

> **NOTE:** The original design spec called for `confidence` and `model` fields. These were replaced with `source` ("image" | "audio") since the frontend needs to know which modality was used, and confidence scoring is not yet implemented on the LLM side.

#### 1.5.3 Backend Service: `guest_extraction.py`

**File:** `backend/app/services/guest_extraction.py` (303 lines)

**Responsibilities:**
1. **Image Cropping** — `crop_image()` crops an image using normalized coordinates (0.0–1.0) via Pillow
2. **LLM Client Builder** — `_get_client_and_model()` reuses `llm.py` utilities (`get_llm_config_by_model_id`, `_build_client_from_model`). Accepts optional `model_id` parameter, falls back to config.json default.
3. **Image Format Detection** — `_detect_image_ext()` detects format from magic bytes (PNG, JPEG, GIF, WEBP)
4. **Extract Name from Image** — `extract_name_from_image(image_bytes, cropped=False, model_id=None) -> str`
   - Encodes image as base64, sends to LLM with vision system prompt
   - Returns only the extracted name string
5. **Extract Name from Audio** — `extract_name_from_audio(audio_bytes, audio_format="webm", model_id=None) -> str`
   - Converts input audio to WAV (16kHz mono PCM) via `pydub` + `ffmpeg`
   - Saves converted WAV to `data/audio_extracted/` for debugging
   - Sends WAV to LLM with audio content type
   - Returns only the extracted name string

**Key Divergences from Original Design:**
- Functions return `str` (not tuple of `name, model`)
- Audio is always converted to WAV format before LLM call (not sent in original format)
- Model selection uses the existing `llm.py` infrastructure (not hardcoded)

#### 1.5.4 Backend Route: `POST /api/guest-search/extract-name`

**File:** `backend/app/routes/guest_search.py`

```
POST /api/guest-search/extract-name
Content-Type: multipart/form-data

Parameters:
  - file: UploadFile (required) — Image or audio file
  - crop_x: float (default 0.0) — Normalized X offset
  - crop_y: float (default 0.0) — Normalized Y offset
  - crop_w: float (default 0.0) — Normalized width
  - crop_h: float (default 0.0) — Normalized height
  - model_id: int | None (default None) — Optional LLM model ID

Response: NameExtractionResponse
```

**Flow:**
1. Read file bytes, detect content type
2. If `audio/*`: determine format from filename/content-type, call `extract_name_from_audio()`
3. If `image/*`: crop if crop coordinates provided (non-zero `crop_w`), call `extract_name_from_image()`
4. Return `NameExtractionResponse(extracted_name=..., source="audio"|"image")`
5. If unsupported content type: return 400 error

#### 1.5.5 Frontend API Client

**File:** `frontend/src/services/api.ts`

**Types Added:**
```typescript
export interface NameExtractionResponse {
  extracted_name: string;
  source: 'image' | 'audio';
  model_id?: number;
}

export interface CropRegion {
  x: number;     // 0.0 - 1.0
  y: number;     // 0.0 - 1.0
  width: number; // 0.0 - 1.0
  height: number; // 0.0 - 1.0
}
```

**Method Added:**
```typescript
extractName: async (
  file: File,
  crop?: CropRegion,
): Promise<NameExtractionResponse>
```

Uses `fetch` directly (not the shared `request` helper) to avoid `Content-Type: application/json` conflict with `multipart/form-data`. Builds a `FormData` body with the file and optional crop coordinates.

#### 1.5.6 Frontend Component: `RegionSelector`

**File:** `frontend/src/components/ui/RegionSelector.tsx` (272 lines)

**Props:**
```typescript
interface RegionSelectorProps {
  imageUrl: string;           // URL or data URI of the image
  alt?: string;               // Alt text for the image
  onRegionChange: (region: Region | null) => void;
}
```

**Implementation Details:**
- Renders an image with an overlaid `<canvas>` for drawing rectangular selection
- Uses Pointer Events (`onPointerDown`, `onPointerMove`, `onPointerUp`) for unified mouse/touch support
- Coordinates normalized (0.0–1.0) relative to displayed image dimensions
- Draws semi-transparent dark overlay outside selection area
- Draws dashed blue border (`#60a5fa`) around selection with corner handles
- Clear button appears when a region is selected
- Canvas auto-resizes to match displayed image size on mount and window resize

**Export:** Also exported from `frontend/src/components/ui/index.ts`

#### 1.5.7 Frontend Integration in ChainInputSection

**File:** `frontend/src/components/ui/ChainInputSection.tsx`

The ChainInputSection integrates all multimodal capabilities:

**State Variables:**
- `selectedImage` — Data URL of uploaded/captured image
- `imageFile` — File object for image
- `recordedAudio` — Data URL of recorded audio
- `audioFile` — File object for audio recording
- `cropRegion` — Selected crop region from RegionSelector
- `extractedName` — Name returned from extraction API
- `extracting` — Loading state during extraction
- `extractError` — Error message from extraction
- `isRecording` — Whether audio recording is in progress

**Handlers:**
| Handler | Purpose |
|---------|---------|
| `handleUploadPhoto` | Click hidden file input (accept="image/*") |
| `handleTakePhoto` | Click hidden file input (capture="environment" for rear camera) |
| `handleImageChange` | Read image file, create data URL, clear audio state |
| `handleSpeakName` | Start MediaRecorder with `getUserMedia({ audio })` |
| `handleStopRecording` | Stop recorder, create File from audio blobs |
| `handleExtractName` | Call `guestSearchApi.extractName(file, cropRegion)` |
| `handleClear` | Reset all media state |

**Media Button Row:**
- Upload Photo (hidden file input, `accept="image/*"`)
- Take Photo (hidden file input, `accept="image/*" capture="environment"`)
- Speak Name / Stop Recording (toggle based on `isRecording`)
- Clear (visible when media file exists)

**Extraction Flow:**
1. User uploads photo or records voice
2. For images: RegionSelector displays preview, user draws crop rectangle
3. User clicks "Extract Name" → calls `guestSearchApi.extractName(file, cropRegion)`
4. Extracted name populates `{customer_name}` field via `onInputChange("customer_name", ...)`
5. User clicks "Search" → chain executes with populated inputs

#### 1.5.8 Dependencies

**Backend:** `Pillow>=10.0.0` (image cropping), `pydub` (audio format conversion), `ffmpeg` (audio codec support)

**Frontend:** No additional npm dependencies required. Uses browser-native APIs:
- `FileReader` for reading uploaded files as data URLs
- `MediaRecorder` + `getUserMedia` for audio recording
- `<canvas>` for region selection overlay

---

## 2. Implementation Checklist

### Phase 1: Database Schema (No Dependencies)

- [x] **1.1** Add `alias` column to `PromptGroupItem` model (`backend/app/models.py`)
- [x] **1.2** Add `is_input_step` column to `PromptGroupItem` model (`backend/app/models.py`)
- [x] **1.3** Add `is_active` column to `PromptGroupItem` model (`backend/app/models.py`) — _beyond original spec_
- [x] **1.4** Add `is_chain_page` column to `PromptGroup` model (`backend/app/models.py`)
- [x] **1.5** Add `page_route` column to `PromptGroup` model (`backend/app/models.py`)
- [x] **1.6** Create Alembic migration file (`backend/alembic/versions/aaa_add_chain_page_fields.py`)
- [x] **1.7** Run `uv run alembic upgrade head` to apply migration
- [x] **1.8** Create separate migration for `is_active` on `PromptGroupItem` (`backend/alembic/versions/add_is_active_to_promptgroup_item.py`)

### Files
| File | Action |
|------|--------|
| `backend/app/models.py` | Added 4 new columns to PromptGroupItem + 2 to PromptGroup |
| `backend/alembic/versions/aaa_add_chain_page_fields.py` | Created |
| `backend/alembic/versions/add_is_active_to_promptgroup_item.py` | Created |

### Phase 2: Pydantic Schemas + Placeholder Engine

- [x] **2.1** Update `PromptGroupItemSchema` — add `alias`, `is_input_step`, `is_active`
- [x] **2.2** Update `PromptGroupItemCreate` — add `alias`, `is_input_step`
- [x] **2.3** Update `PromptGroupSchema` — add `is_chain_page`, `page_route`
- [x] **2.4** Update `_group_to_schema()` in `prompt_groups.py` routes to include new fields
- [x] **2.5** Update `create_group()` and `update_group()` routes to accept `alias`, `is_input_step` on items
- [x] **2.6** Add `chain_results` and `aliases` parameters to `resolve_placeholders()` in `placeholders.py`
- [x] **2.7** Add `{step_N}` and `{step_N.result}` regex resolution to `resolve_placeholders()`
- [x] **2.8** Add `{alias}` regex resolution to `resolve_placeholders()`
- [x] **2.9** Add `resolve_all_placeholders()` with runtime_variables support
- [x] **2.10** **Verify:** Existing `POST /api/prompt-groups/{id}/execute` still works (backward compat)

### Files
| File | Action |
|------|--------|
| `backend/app/schemas.py` | Extended 3 schemas + added ChainExecutionRequest, ChainStepRequest/Response |
| `backend/app/routes/prompt_groups.py` | Updated `_group_to_schema()`, `create_group()`, `update_group()` |
| `backend/app/services/placeholders.py` | Extended `resolve_placeholders()`, added `resolve_all_placeholders()` |

### Phase 3: Chain Execution Engine + New API Endpoints

- [x] **3.1** Update `execute_chain()` in `prompt_chain.py`:
  - [x] Add `page_mode: bool = False` parameter
  - [x] Add `user_inputs: dict[int, dict[str, str]] | None = None` parameter
  - [x] Build `aliases` map from steps
  - [x] Track `chain_results: dict[int, str]` per step
  - [x] Resolve `{step_N}` / `{alias}` in each step's user message
  - [x] Include `alias` field in `chain_steps` output
- [x] **3.2** Add `execute_chain_step()` function for step-by-step execution — _beyond original spec_
- [x] **3.3** Add `ChainExecutionRequest` Pydantic model to `schemas.py`
- [x] **3.4** Add `ChainStepRequest` + `ChainStepResponse` Pydantic models — _beyond original spec_
- [x] **3.5** Add `POST /api/prompt-groups/{group_id}/execute-chain` endpoint
- [x] **3.6** Add `POST /api/prompt-groups/{group_id}/execute-chain-step` endpoint — _beyond original spec_
- [x] **3.7** **Verify:** Both endpoints return chain results with per-step details

### Files
| File | Action |
|------|--------|
| `backend/app/services/prompt_chain.py` | Major refactor: chain results tracking + step-by-step execution |
| `backend/app/schemas.py` | Added `ChainExecutionRequest`, `ChainStepRequest`, `ChainStepResponse` |
| `backend/app/routes/prompt_groups.py` | Added `/execute-chain` + `/execute-chain-step` endpoints |

### Phase 4: Frontend Types + API Client

- [x] **4.1** Update `PromptGroupItem` TS interface — add `alias`, `is_input_step`, `is_active`
- [x] **4.2** Update `PromptGroupItemCreate` TS interface — add `alias`, `is_input_step`
- [x] **4.3** Update `PromptGroup` TS interface — add `is_chain_page`, `page_route`
- [x] **4.4** Add `ChainExecutionRequest` TS interface
- [x] **4.5** Add `ChainStepRequest` TS interface — _beyond original spec_
- [x] **4.6** Add `ChainStepResult` TS interface
- [x] **4.7** Add `ChainExecutionResult` TS interface
- [x] **4.8** Add `executeChain()` function to `promptGroupsApi.ts`
- [x] **4.9** Add `executeChainStep()` function to `promptGroupsApi.ts` — _beyond original spec_
- [x] **4.10** Export all functions from `promptGroupsApi`

### Files
| File | Action |
|------|--------|
| `frontend/src/types/prompt.ts` | Extended 3 interfaces, added 5 new ones |
| `frontend/src/services/promptGroupsApi.ts` | Added `executeChain` + `executeChainStep` functions |

### Phase 5: Frontend Components

#### 5A: ChainInputSection ✅

- [x] **5A.1** Created `frontend/src/components/ui/ChainInputSection.tsx` (401 lines)
- [x] **5A.2** Implemented `inferInputFields()` utility — parses template for `{placeholder}` patterns
- [x] **5A.3** Implemented `inferFieldType()` utility — text / date / select detection
- [x] **5A.4** Migrated media state from GuestSearch:
  - [x] Image upload + camera capture handlers
  - [x] Voice recording handlers (MediaRecorder API)
  - [x] Image extraction handler (calls `/api/guest-search/extract-name`)
  - [x] Audio extraction handler (calls `/api/guest-search/extract-name`)
  - [x] RegionSelector integration for image crop
- [x] **5A.5** Render template-derived input fields (text, select, date)
- [x] **5A.6** Render media input buttons (Upload Photo, Take Photo, Speak Name, Clear)
- [x] **5A.7** Render "Extract Name" button that populates `{customer_name}`
- [x] **5A.8** Call `onRun(inputs)` with `Record<number, Record<string, string>>` format
- [x] **5A.9** **Verify:** Component renders correctly with sample PromptGroupItem

> **STATUS (2026-02-07)**: Fully implemented. Replaced mocked `handleExtractName`
> with real API calls to `guestSearchApi.extractName()` for both image and audio.
> `RegionSelector` is integrated for image crop region selection. Audio recordings include playback preview.

#### 5B: ChainStepStatus ✅

- [x] **5B.1** Created `frontend/src/components/ui/ChainStepStatus.tsx` (106 lines)
- [x] **5B.2** Display prompt_id + version + alias (if set)
- [x] **5B.3** Display status indicator (success/running/failed) with color
- [x] **5B.4** Display cached indicator
- [x] **5B.5** Display error message if failed
- [x] **5B.6** Collapsible/expandable detail view
- [x] **5B.7** References section showing user_message
- [x] **5B.8** Response preview for successful steps

#### 5C: ChainOutputSection ✅

- [x] **5C.1** Created `frontend/src/components/ui/ChainOutputSection.tsx` (109 lines)
- [x] **5C.2** Render final output as text (pre-wrap monospace formatting)
- [x] **5C.3** Copy to clipboard button
- [x] **5C.4** Re-run chain button (calls `onRerun`)
- [x] **5C.5** Expand/collapse for long output (>2000 chars)
- [x] **5C.6** Character count display
- [x] **5C.7** Cached indicator

### Files Created
| File | Lines | Purpose |
|------|-------|---------|
| `frontend/src/components/ui/ChainInputSection.tsx` | 401 | Input fields + media handling |
| `frontend/src/components/ui/ChainStepStatus.tsx` | 106 | Step status bar |
| `frontend/src/components/ui/ChainOutputSection.tsx` | 109 | Final output renderer |

### Phase 6: Page, Routing, Seed Data, Navigation

- [x] **6.1** Created `frontend/src/pages/PromptChainPage.tsx` (323 lines)
  - [x] Load groups via `promptGroupsApi.list()`
  - [x] Find group by `page_route` match with URL param
  - [x] Fetch prompt templates for each step
  - [x] Render `ChainInputSection` for input steps
  - [x] Render `ChainStepStatus` for intermediate steps
  - [x] Render `ChainOutputSection` for last step
  - [x] Handle loading / not-found / error states
  - [x] Step-by-step execution with "Execute Next Step" buttons
  - [x] Progress tracking ("X of Y steps completed")
  - [x] Start Over button when all steps done
- [x] **6.2** Added wildcard route in `frontend/src/App.tsx`:
  ```tsx
  <Route path="/prompt-chains/:route" element={<PromptChainPage />} />
  ```
- [x] **6.3** Created `backend/Generator/seed_chain_pages.py` (163 lines)
  - [x] "Guest Intelligence" chain: `is_chain_page=true`, `page_route="/guest-intel"`
  - [x] 2 items: guest-search (position 1) + guest-intelligence (position 2)
  - [x] Position 1 marked as `is_input_step=true`, aliases "search" and "intelligence"
  - [x] "Hello World" example chain: `page_route="/hello"`
- [x] **6.4** Seed data runnable: `cd backend && uv run python Generator/seed_chain_pages.py`

### Files Created/Modified
| File | Action |
|------|--------|
| `frontend/src/pages/PromptChainPage.tsx` | Created (323 lines) |
| `frontend/src/App.tsx` | Added wildcard route |
| `backend/Generator/seed_chain_pages.py` | Created (163 lines) |

---

## 3. Phase 1: Backend Infrastructure

### 3.1 Files Modified

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
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1",
        comment="Enable or disable this step in the chain")

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
        back_populates="group", cascade="all, delete-orphan", order_by="PromptGroupItem.position"
    )
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
    alias: str | None = None
    is_input_step: bool = False
    is_active: bool = True
```

**Changes to `PromptGroupItemCreate`:**
```python
class PromptGroupItemCreate(BaseModel):
    position: int
    prompt_id: str
    prompt_version: int
    alias: str | None = None
    is_input_step: bool = False
```

**Changes to `PromptGroupSchema`:**
```python
class PromptGroupSchema(BaseModel):
    group_id: int
    name: str
    description: str | None = None
    is_active: bool = True
    created_at: str
    updated_at: str
    is_chain_page: bool = False
    page_route: str | None = None
    items: List[PromptGroupItemSchema] = []
    schedules: List[PromptGroupScheduleSchema] = []
    results: List[PromptGroupResultSchema] = []
```

#### `backend/alembic/versions/aaa_add_chain_page_fields.py`

```python
"""Add chain page fields to PromptGroup and PromptGroupItem

Revision ID: aaa_add_chain_page_fields
"""
from alembic import op
import sqlalchemy as sa

revision = 'aaa_add_chain_page_fields'


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

## 4. Phase 2: Chain Execution Engine

### 4.1 Placeholder Resolution

#### `backend/app/services/placeholders.py`

The `resolve_placeholders()` function supports 3-phase resolution:

```python
def resolve_placeholders(
    text: str,
    chain_results: dict[int, str] | None = None,
    aliases: dict[str, int] | None = None,
) -> str:
    """Replace all {PLACEHOLDER_NAME} occurrences with their resolved content.

    Resolution order:
    1. Static placeholders (DATABASE_TABLES, GUEST_INFORMATION, etc.)
    2. Chain result references ({step_N}, {step_N.result})
    3. Alias references ({alias_name})
    """
```

The `resolve_all_placeholders()` function adds runtime variable resolution:

```python
def resolve_all_placeholders(
    text: str,
    runtime_variables: dict[str, str] | None = None,
    chain_results: dict[int, str] | None = None,
    aliases: dict[str, int] | None = None,
) -> str:
    """Replace ALL placeholders: static + runtime + chain results.

    Phase 1 — Static placeholders (DATABASE_TABLES, GUEST_INFORMATION, etc.)
    Phase 2 — Runtime variables ({table.field} -> user-provided value)
    Phase 3 — Chain results ({step_N}, {alias})
    """
```

### 4.2 Chain Execution

#### `backend/app/services/prompt_chain.py`

**`execute_chain()`** — Full chain execution (batch mode):

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
```

**`execute_chain_step()`** — Single step execution (interactive mode):

```python
def execute_chain_step(
    group_id: int,
    step_position: int,
    inputs: dict[str, str] | None = None,
    initial_input: str = "",
    accumulated_context: str = "",
    db: Session | None = None,
) -> dict[str, Any]:
    """Execute a single step in a prompt chain.

    This is used for page-mode chain execution where each step is called independently.
    The first step receives user_inputs as template variables.
    Subsequent steps receive the accumulated context from previous steps.
    """
```

### 4.3 New API Endpoints

#### `backend/app/routes/prompt_groups.py`

**`POST /{group_id}/execute-chain`** — Batch execution:
```python
@router.post("/{group_id}/execute-chain")
def execute_chain_page(group_id: int, req: ChainExecutionRequest):
    """Execute chain with user inputs (page mode)."""
    result = execute_chain(
        group_id,
        initial_input=req.initial_input,
        page_mode=True,
        user_inputs=req.inputs,
    )
    return result
```

**`POST /{group_id}/execute-chain-step`** — Step-by-step execution:
```python
@router.post("/{group_id}/execute-chain-step")
def execute_chain_step_route(group_id: int, req: ChainStepRequest):
    """Execute a single step in a prompt chain (page mode, step-by-step)."""
    result = execute_chain_step(
        group_id,
        step_position=req.position,
        inputs=req.inputs,
        initial_input=req.initial_input,
        accumulated_context=req.accumulated_context,
    )
    return result
```

### 4.4 New Schemas

**`ChainExecutionRequest`** — Batch mode request:
```python
class ChainExecutionRequest(BaseModel):
    inputs: dict[int, dict[str, str]] = {}
    initial_input: str = ""
```

**`ChainStepRequest`** — Step-by-step request:
```python
class ChainStepRequest(BaseModel):
    position: int = Field(..., description="The step position (1-based)")
    inputs: dict[str, str] = Field(default_factory=dict)
    initial_input: str = Field(default="")
    accumulated_context: str = Field(default="")
```

**`ChainStepResponse`** — Step-by-step response:
```python
class ChainStepResponse(BaseModel):
    position: int
    prompt_id: str
    prompt_version: int
    alias: str | None = None
    status: str = "success"  # "success" or "failed"
    response: str | None = None
    cached: bool = False
    error: str | None = None
    user_message: str | None = None
    system_prompt: str | None = None
```

**`ChainStepResultSchema`** — Per-step result (batch mode):
```python
class ChainStepResultSchema(BaseModel):
    position: int
    prompt_id: str
    prompt_version: int
    alias: str | None = None
    system_prompt: str | None = None
    user_message: str | None = None
    response: str | None = None
    cached: bool = False
    error: str | None = None
```

**`ChainExecutionResultSchema`** — Batch mode response:
```python
class ChainExecutionResultSchema(BaseModel):
    group_id: int
    group_name: str
    executed_at: str
    scheduled: bool = False
    success: bool = False
    steps_count: int = 0
    steps: List[ChainStepResultSchema] = []
    final_output: str | None = None
    result_file: str = ""
    result_id: int = 0
```

**`UpdateGroupRequest`** — Updated to accept chain page fields:
```python
class UpdateGroupRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    is_active: bool | None = None
    is_chain_page: bool | None = None
    page_route: str | None = None
    items: List[PromptGroupItemCreate] | None = None
```

---

## 5. Phase 3: Frontend Types & API Client

### 5.1 TypeScript Types

#### `frontend/src/types/prompt.ts`

**Updated `PromptGroupItem`:**
```typescript
export interface PromptGroupItem {
  item_id: number;
  group_id: number;
  position: number;
  prompt_id: string;
  prompt_version: number;
  alias?: string;
  is_input_step?: boolean;
  is_active?: boolean;
}
```

**Updated `PromptGroupItemCreate`:**
```typescript
export interface PromptGroupItemCreate {
  position: number;
  prompt_id: string;
  prompt_version: number;
  alias?: string;
  is_input_step?: boolean;
}
```

**Updated `PromptGroup`:**
```typescript
export interface PromptGroup {
  group_id: number;
  name: string;
  description: string | null;
  is_active: boolean;
  is_chain_page?: boolean;
  page_route?: string | null;
  created_at: string;
  updated_at: string;
  items: PromptGroupItem[];
  schedules: PromptGroupSchedule[];
  results: PromptGroupResult[];
}
```

**Chain Execution Types:**
```typescript
export interface ChainExecutionRequest {
  inputs: Record<number, Record<string, string>>;
  initial_input?: string;
}

export interface ChainStepRequest {
  position: number;
  inputs: Record<string, string>;
  initial_input?: string;
  accumulated_context?: string;
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
  system_prompt: string | null;
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

### 5.2 API Client

#### `frontend/src/services/promptGroupsApi.ts`

**Batch execution:**
```typescript
export function executeChain(
  groupId: number,
  inputs: Record<number, Record<string, string>>,
  initialInput?: string,
): Promise<ChainExecutionResult>
```

**Step-by-step execution:**
```typescript
export function executeChainStep(
  groupId: number,
  position: number,
  inputs: Record<string, string>,
  initialInput?: string,
  accumulatedContext?: string,
): Promise<ChainStepResult>
```

**Exported as:**
```typescript
export const promptGroupsApi = {
  // ... existing methods ...
  executeChain,
  executeChainStep,
};
```

---

## 6. Phase 4: Frontend Components

### 6.1 Component Architecture

```
frontend/src/components/ui/
├── ChainInputSection.tsx      (401 lines) — Step input fields (text + media)
├── ChainStepStatus.tsx        (106 lines) — Intermediate step status bar
└── ChainOutputSection.tsx     (109 lines) — Final step output renderer
frontend/src/pages/
└── PromptChainPage.tsx        (323 lines) — Main chain page layout
```

### 6.2 `ChainInputSection.tsx` (401 lines)

This component:
1. Receives the step's `PromptGroupItem` + prompt `template` string
2. Parses the template for `{placeholder}` patterns via `inferInputFields()`
3. Renders appropriate input fields:
   - `{customer_name}` -> Text input
   - `{filter_status}` -> Select dropdown
   - `{date_range}` -> Date inputs
4. **Also includes** media input from GuestSearch:
   - Photo upload + camera capture with name extraction
   - Voice recording with name extraction
5. Collects all input values and passes them to the parent via `onRun(inputs)`

**Key features:**
- `RegionSelector` integration for image crop region selection
- Real API calls to `guestSearchApi.extractName()` for both image and audio
- Audio playback preview for recordings
- Template-derived field parsing with type inference

**Props:**
```typescript
interface ChainInputSectionProps {
  step: PromptGroupItem;
  template: string;
  inputs: Record<string, string>;
  onInputChange: (name: string, value: string) => void;
  onRun: (inputs: Record<number, Record<string, string>>, initialInput?: string) => void;
  loading: boolean;
}
```

### 6.3 `ChainStepStatus.tsx` (106 lines)

Collapsible status bar for intermediate steps.

**Features:**
- Prompt ID + version display
- Alias badge (if set)
- Status indicator: success / running / failed with color coding
- Cached indicator badge
- Collapsible detail view showing:
  - References (user_message)
  - Error message (if failed)
  - Response preview (if successful)

**Props:**
```typescript
interface ChainStepStatusProps {
  step: ChainStepResult;
  expanded?: boolean;
  onToggle?: () => void;
}
```

### 6.4 `ChainOutputSection.tsx` (109 lines)

Renders the final step's LLM output.

**Features:**
- Pre-wrap monospace formatting for LLM output
- Copy to clipboard button with feedback
- Expand/collapse for long output (>2000 chars truncated)
- Character count display
- Cached indicator
- Re-run chain button

**Props:**
```typescript
interface ChainOutputSectionProps {
  step: ChainStepResult;
  output: string | null;
  onRerun?: () => void;
}
```

### 6.5 `PromptChainPage.tsx` (323 lines)

Main page component. Uses **step-by-step execution** (calls one step at a time).

**Flow:**
1. Load all PromptGroups via `promptGroupsApi.list()`, find the one with matching `page_route`
2. If not found -> 404 page
3. If found -> fetch prompt template for each step via `promptsApi.getByVersion()`
4. Render each step's input section (`ChainInputSection`) and output section (`ChainStepStatus` / `ChainOutputSection`)
5. On "Search" click, call `executeChainStep()` for step 1
6. After step completes, show "Execute Next Step" button for the next step
7. After all steps complete, show "All steps completed" banner

**Key features:**
- Per-step input state management (`stepInputs` per position)
- Accumulated context passed between steps
- Auto-scroll to next step after completion
- Progress tracking ("X of Y steps completed")
- Start Over button when all steps done
- Handles loading, not-found, and error states

---

## 7. Phase 5: Routing & GuestSearch Replacement

### 7.1 Wildcard Route

#### `frontend/src/App.tsx`

```typescript
import PromptChainPage from "./pages/PromptChainPage";

<Route path="/prompt-chains/:route" element={<PromptChainPage />} />
```

### 7.2 Seed Data

#### `backend/Generator/seed_chain_pages.py` (163 lines)

Creates two chain pages:

**Guest Intelligence** (`/prompt-chains/guest-intel`):
- 2 steps: guest-search (v1, alias "search", is_input_step) + guest-intelligence (v1, alias "intelligence")
- Dynamically finds prompt versions from database

**Hello World** (`/prompt-chains/hello`):
- 1 step: default prompt (alias "hello", is_input_step)
- Demonstrates the chain concept with minimal setup

### 7.3 Execution Model

The actual implementation uses a **step-by-step execution** model rather than the batch model originally specified:

| Aspect | Original Spec | Actual Implementation |
|--------|---------------|----------------------|
| Execution | Single API call runs all steps | Frontend calls one step at a time |
| API | `POST /execute-chain` only | `POST /execute-chain` + `POST /execute-chain-step` |
| UX | All-or-nothing execution | Incremental execution with "Execute Next Step" buttons |
| State | Backend manages chain state | Frontend manages per-step state + accumulated context |
| Benefit | Simpler backend | Better UX, visible progress, ability to inspect intermediate results |

Both endpoints remain available:
- `/execute-chain` — for batch/scheduled execution
- `/execute-chain-step` — for interactive page-mode execution

---

## 8. Design Decisions

### 8.1 Media Input Lives in ChainInputSection (Option A)

**Rationale:** The photo/voice features are user-facing and meaningful. Moving them to a "pre-extraction" step would lose the rich UX. Instead, the ChainInputSection handles them and populates `{customer_name}` when the user clicks "Extract Name."

**How it works:**
1. User uploads photo or records voice
2. User clicks "Extract Name" -> API call to `/api/guest-search/extract-name`
3. Extracted name populates `{customer_name}` text field
4. User clicks "Search" -> chain executes with the populated inputs

### 8.2 Dynamic Wildcard Routing

Routes are **purely data-driven**. The only route needed is:
```
/prompt-chains/:route
```
The frontend loads all groups and finds the one with matching `page_route`. No route registration needed in code.

### 8.3 Template Placeholders vs Special Inputs

Two categories of input in the first step:

| Type | Example | Source |
|------|---------|--------|
| Template placeholder | `{customer_name}` | Parsed from `user_prompt_template` |
| Media button | Photo/Voice upload | Always present, populates `{customer_name}` |

This keeps the chain architecture clean while preserving the UX.

### 8.4 Chain Results Passed as Accumulated Context

For the step-by-step model, each step's output is passed to the next step as **accumulated context** (prepended to the user message). The `{step_N}` placeholder resolution provides an **additional** mechanism for precise control. This ensures:
- Old chains without `{step_N}` still work
- New chains can use `{step_N}` for precise control
- Both mechanisms can coexist

### 8.5 Alias Resolution

Aliases are resolved **after** step references. If a prompt has `alias: "search"`, then `{search}` in a subsequent step resolves to that step's output. This is more readable than `{step_1}`.

### 8.6 Step-by-Step Execution (Beyond Original Spec)

The implementation uses `execute_chain_step()` called from the frontend rather than `execute_chain()` for interactive execution. This provides:
- **Visible progress** — user sees each step complete before the next begins
- **Intermediate inspection** — user can review each step's output
- **Better error handling** — failed steps don't stop the entire chain
- **Flexibility** — user can choose to skip or rerun individual steps

### 8.7 Per-Item `is_active` Toggle (Beyond Original Spec)

Each `PromptGroupItem` has an `is_active` field that allows individual steps to be enabled/disabled without removing them from the chain. This provides:
- **A/B testing** — disable a step without losing its configuration
- **Debugging** — isolate problematic steps
- **Feature flags** — conditionally include steps

---

## 9. Migration Guide

### Running the Migration

```bash
# Apply chain page fields migration
cd backend
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

# Execute chain with inputs (batch mode)
curl -X POST http://localhost:8000/api/prompt-groups/1/execute-chain \
  -H "Content-Type: application/json" \
  -d '{"inputs": {"1": {"customer_name": "Ahmed Hassan"}}, "initial_input": ""}'

# Execute single step (step-by-step mode)
curl -X POST http://localhost:8000/api/prompt-groups/1/execute-chain-step \
  -H "Content-Type: application/json" \
  -d '{"position": 1, "inputs": {"customer_name": "Ahmed Hassan"}}'
```

---

## Appendix A: API Request/Response Examples

### POST /api/prompt-groups/{group_id}/execute-chain (Batch Mode)

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
      "prompt_id": "guest-intelligence",
      "prompt_version": 1,
      "alias": "intelligence",
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

### POST /api/prompt-groups/{group_id}/execute-chain-step (Step-by-Step Mode)

**Request (Step 1):**
```json
{
  "position": 1,
  "inputs": {
    "customer_name": "Ahmed Hassan"
  },
  "initial_input": "",
  "accumulated_context": ""
}
```

**Response (Step 1):**
```json
{
  "step": 1,
  "prompt_id": "guest-search",
  "prompt_version": 1,
  "alias": "search",
  "status": "success",
  "response": "Found 3 guests matching Ahmed Hassan...",
  "cached": false,
  "error": null
}
```

**Request (Step 2 — passes Step 1 output as context):**
```json
{
  "position": 2,
  "inputs": {},
  "initial_input": "",
  "accumulated_context": "Found 3 guests matching Ahmed Hassan..."
}
```

---

## Appendix B: Example Prompt Templates

### Step 1: guest-search (Input Step)

```
Search for guest: {customer_name}
Also bring the information about its reservations.
```

### Step 2: guest-intelligence (Output Step)

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

---

## Appendix C: File Change Summary

### Files Modified

| # | File | Phase | Description |
|---|------|-------|-------------|
| 1 | `backend/app/models.py` | 1 | Added `alias`, `is_input_step`, `is_active` to PromptGroupItem; `is_chain_page`, `page_route` to PromptGroup |
| 2 | `backend/app/schemas.py` | 1.5, 2, 3 | Added `NameExtractionResponse` schema; extended 3 schemas; added chain execution models |
| 3 | `backend/app/routes/guest_search.py` | 1.5 | Added `POST /api/guest-search/extract-name` endpoint |
| 4 | `backend/app/routes/prompt_groups.py` | 2, 3 | Updated `_group_to_schema()`, `create_group()`, `update_group()`; added `/execute-chain` + `/execute-chain-step` endpoints |
| 5 | `backend/app/services/placeholders.py` | 2 | Extended `resolve_placeholders()` with chain results; added `resolve_all_placeholders()` |
| 6 | `backend/app/services/prompt_chain.py` | 3 | Major refactor: chain results tracking, `page_mode` support; added `execute_chain_step()` |
| 7 | `frontend/src/services/api.ts` | 1.5 | Added `NameExtractionResponse`, `CropRegion` types; added `guestSearchApi.extractName()` method |
| 8 | `frontend/src/types/prompt.ts` | 4 | Extended 3 interfaces; added 5 new chain types |
| 9 | `frontend/src/services/promptGroupsApi.ts` | 4 | Added `executeChain()` + `executeChainStep()` functions |
| 10 | `frontend/src/App.tsx` | 6 | Added wildcard route for chain pages |

### Files Created

| # | File | Lines | Phase | Purpose |
|---|------|-------|-------|---------|
| 11 | `backend/alembic/versions/aaa_add_chain_page_fields.py` | — | 1 | Migration for chain page fields |
| 12 | `backend/alembic/versions/add_is_active_to_promptgroup_item.py` | — | 1 | Migration for `is_active` on PromptGroupItem |
| 13 | `backend/app/services/guest_extraction.py` | 303 | 1.5 | Multimodal name extraction service (image cropping, LLM client, extract from image/audio) |
| 14 | `backend/Generator/seed_chain_pages.py` | 163 | 6 | Seed data for Guest Intelligence + Hello World chains |
| 15 | `frontend/src/components/ui/ChainInputSection.tsx` | 401 | 5 | Input fields + media handling component |
| 16 | `frontend/src/components/ui/ChainStepStatus.tsx` | 106 | 5 | Step status bar component |
| 17 | `frontend/src/components/ui/ChainOutputSection.tsx` | 109 | 5 | Final output renderer component |
| 18 | `frontend/src/components/ui/RegionSelector.tsx` | 272 | 1.5 | Canvas-based region selector for image crop |
| 19 | `frontend/src/pages/PromptChainPage.tsx` | 323 | 6 | Main chain page with step-by-step execution |

### Grand Total

- **10 files modified**
- **8 files created**
- **18 files total**

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
Phase 3: Chain Executor + API Endpoints
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

**All phases: COMPLETE ✅**