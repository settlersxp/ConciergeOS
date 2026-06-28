# Plan: Prompt Management Enhancements

> **Status**: Planned — Awaiting Implementation
> **Created**: 2026-06-28
> **Last Updated**: 2026-06-28 (Feature 3 added)
> **Depends On**: `docs/PLAN_PROMPT_VERSIONING.md` (core prompt system already implemented)

---

## 1. Overview

Enhance the existing Prompt Management page with three new capabilities:

1. **Create prompts from scratch** — Currently users can only duplicate existing prompt versions. Add the ability to create entirely new prompts (new `prompt_id`) with empty sections.
2. **AI-assisted section improvement** — Add an inline chat interface that lets users chat with an LLM to iteratively improve any of the 4 prompt sections (Intention, Restrictions, Output Structure, User Prompt Template).
3. **Clone section from another prompt/version** — Add a button to copy a single section's content from any other prompt + version, so users can reuse good section content across prompts.

### Design Goals

1. **Minimal backend changes** — Reuse the existing `get_llm_config()` client and simple chat completion pattern from `PerformanceTesting/llm_client.py`
2. **Consistent UI** — All new components reuse existing UI primitives (`Card`, `Button`, `Textarea`, `Input`, `Select`, `Toast`)
3. **Non-destructive** — AI improvements and cloned sections are previewed in modals and only applied when the user explicitly clicks "Apply"/"Clone"
4. **Self-contained tasks** — Each implementation task can be completed independently once its dependencies are done

---

## 2. Current State Analysis

### What Works

- **Prompt CRUD**: Full create/read/update/delete/duplicate via `app/routes/prompts.py`
- **Prompt Management UI**: `frontend/src/pages/PromptManagement.tsx` renders 4 editable sections per prompt
- **Prompt Editor Sections**: `frontend/src/components/ui/PromptEditorSection.tsx` wraps `PromptTextarea`
- **LLM Client**: `app/services/llm.py` exposes `get_llm_config()` returning `(OpenAI client, model_name)`
- **Chat Completions**: `PerformanceTesting/llm_client.py` shows the pattern for simple non-tool-calling LLM queries
- **Version API**: `GET /api/prompts/{prompt_id}/{version}` (`getByVersion`) returns full version data including all 4 sections

### What's Missing

- **No "create from scratch"** — `handleCreateNew` in PromptManagement.tsx calls `duplicate()`, which requires an existing prompt + version. There's no way to create a brand new `prompt_id`.
- **No AI assistance** — No endpoint or UI for LLM-powered prompt improvement.
- **No cross-prompt section reuse** — Users cannot copy a single section from one prompt/version to another without manual copy-paste.

---

## 3. Feature 1: Create Prompts from Scratch

### 3.1 User Experience

```
Current flow:
  Select existing prompt → Click "+ New Version" → Duplicate creates new version

New flow added:
  Click "+ New Prompt" → Modal opens → Enter prompt_id + name → Creates v1 with empty sections
```

### 3.2 UI Wireframe

```
┌──────────────────────────────────────────────┐
│  Create New Prompt                    [X]    │
├──────────────────────────────────────────────┤
│                                              │
│  Prompt ID *                                  │
│  ┌─────────────────────────────────────────┐ │
│  │ guest-search                           │ │
│  └─────────────────────────────────────────┘ │
│  ✅ Use kebab-case (e.g., "room-lookup")     │
│                                              │
│  Display Name *                               │
│  ┌─────────────────────────────────────────┐ │
│  │ Guest Search                            │ │
│  └─────────────────────────────────────────┘ │
│                                              │
│  All prompt sections will be created empty.  │
│  You can fill them in after creation.        │
│                                              │
│                    [Cancel]  [Create]        │
└──────────────────────────────────────────────┘
```

### 3.3 Backend Changes

**None required.** The existing `POST /api/prompts/{prompt_id}` endpoint already handles creating v1 of a new `prompt_id`:

```python
# app/routes/prompts.py, line 193-217
@router.post("/{prompt_id}")
async def create_version(prompt_id: str, body: CreatePromptRequest):
    existing = store.list_prompts(prompt_id)
    next_version = len(existing) + 1 if existing else 1  # ← Already handles new prompt_ids
    prompt = store.create_prompt(...)
```

When `prompt_id` doesn't exist yet, `existing` is empty, so `next_version = 1` and a brand new prompt is created.

### 3.4 Frontend Changes

| File | Changes |
|------|---------|
| `frontend/src/components/ui/CreatePromptModal.tsx` | **NEW** — Modal with `prompt_id` (Input) + `name` (Input) fields. On submit, calls `promptsApi.create(prompt_id, { name, intention: "", restrictions: "", output_structure: "", user_prompt_template: "" })`. |
| `frontend/src/pages/PromptManagement.tsx` | Add `showCreateModal` state. Add "+ New Prompt" button in the PromptSelector area. Render `<CreatePromptModal>` when open. On successful creation, reload prompt list and select the new prompt. |
| `frontend/src/components/ui/index.ts` | Export `CreatePromptModal` |

### 3.5 CreatePromptModal Component Spec

```typescript
interface CreatePromptModalProps {
  open: boolean;
  onClose: () => void;
  onCreate: (promptId: string, name: string) => Promise<void>;
}

// Internal state:
// - promptId: string (required, kebab-case validation)
// - name: string (required, non-empty)
// - loading: boolean
// - error: string | null

// Validation rules:
// - prompt_id: required, kebab-case regex ^[a-z][a-z0-9-]*$
// - name: required, min 1 character, max 200 characters
```

---

## 4. Feature 2: AI-Assisted Section Improvement

### 4.1 User Experience

```
Current state:
  Each section has a text area for manual editing

New flow:
  Click "Improve with AI" button next to any section label
  → Chat modal opens showing current section content (read-only context)
  → User types instructions: "Make this more concise", "Add XML formatting rules"
  → LLM responds with improved version
  → Conversation continues iteratively
  → User clicks "Apply" to replace section with LLM's latest suggestion
  → User clicks "Cancel" to discard changes
```

### 4.2 UI Wireframe

```
┌───────────────────────────────────────────────────────────┐
│  Improve "Intention" with AI                        [X]   │
├───────────────────────────────────────────────────────────┤
│                                                           │
│  Current Section Content (context for the AI):            │
│  ┌──────────────────────────────────────────────────────┐ │
│  │ You are a helpful hotel concierge assistant...       │ │
│  │ You have access to database query tools...           │ │
│  └──────────────────────────────────────────────────────┘ │
│                                                           │
│  Chat                                                     │
│  ┌──────────────────────────────────────────────────────┐ │
│  │                                                      │ │
│  │ User:  Make this more concise                        │ │
│  │         ─────────────────────────────────────────   │ │
│  │ AI:     Here's a more concise version:              │ │
│  │         "You are a hotel concierge assistant with   │ │
│  │          database tools. Help users find guest      │ │
│  │          information."                               │ │
│  │                                                      │ │
│  │ User:  Also mention the output format               │ │
│  │         ─────────────────────────────────────────   │ │
│  │ AI:     "You are a hotel concierge assistant with   │ │
│  │          database tools. Help users find guest      │ │
│  │          information. Format responses using the    │ │
│  │          specified markdown structure."              │ │
│  │                                                      │ │
│  └──────────────────────────────────────────────────────┘ │
│                                                           │
│  ┌──────────────────────────────────────────────────────┐ │
│  │ Type a message...                           [Send]   │ │
│  └──────────────────────────────────────────────────────┘ │
│                                                           │
│  Tip: The AI will suggest improvements. Click "Apply"     │
│  to replace the current section with the latest suggestion│
│                                                           │
│                    [Cancel]        [Apply Suggestion]     │
└───────────────────────────────────────────────────────────┘
```

### 4.3 Backend Implementation

#### New Endpoint

**File**: `app/routes/prompts.py`
**Route**: `POST /api/prompts/ai-improve`

```python
@router.post("/ai-improve")
async def ai_improve(body: AiImproveRequest):
    """Use an LLM to help improve a prompt section.
    
    This endpoint takes the current section content and a conversation history,
    then sends them to the configured LLM for improvement suggestions.
    
    The system prompt instructs the LLM to act as a prompt engineering expert.
    """
    ...
```

#### Request Schema

```python
class ChatMessage(BaseModel):
    role: str          # "user" or "assistant"
    content: str

class AiImproveRequest(BaseModel):
    section: str               # One of: "intention", "restrictions", "output_structure", "user_prompt_template"
    current_text: str          # Current content of the section being improved
    conversation: list[ChatMessage]  # Chat history (user messages + assistant responses)
    model: str | None = None   # Optional: override the model to use
```

#### Response Schema

```python
class AiImproveResponse(BaseModel):
    reply: str                 # LLM's text response (the improvement suggestion)
```

#### Implementation Details

```python
@router.post("/ai-improve")
async def ai_improve(body: AiImproveRequest):
    from app.services.llm import get_llm_config
    
    client, model_name = get_llm_config()
    if body.model:
        model_name = body.model
    
    SECTION_DESCRIPTIONS = {
        "intention": "The Intention section defines what the LLM assistant should do — its purpose, role, and core responsibilities.",
        "restrictions": "The Restrictions section defines rules, constraints, and boundaries the LLM must follow.",
        "output_structure": "The Output Structure section defines the expected format and structure of the LLM's responses.",
        "user_prompt_template": "The User Prompt Template is the dynamic user message sent to the LLM, which may contain placeholders like {customer_name}.",
    }
    
    section_desc = SECTION_DESCRIPTIONS.get(body.section, "A section of an LLM prompt.")
    
    system_prompt = (
        "You are an expert prompt engineer helping a user improve a section of an LLM system prompt. "
        f"The section they are editing is: {body.section.upper()} — {section_desc}\n\n"
        "The current content of this section is:\n\n"
        "```\n"
        f"{body.current_text}\n"
        "```\n\n"
        "The user will ask you to improve, rewrite, or modify this section. "
        "Provide your improved version directly. "
        "Keep your responses focused on the prompt content — do not add meta-commentary unless the user asks questions."
    )
    
    messages: list[dict[str, str]] = [
        {"role": "system", "content": system_prompt},
    ]
    
    # Add conversation history
    for msg in body.conversation:
        messages.append({"role": msg.role, "content": msg.content})
    
    response = client.chat.completions.create(
        model=model_name,
        messages=messages,
        temperature=0.3,  # Low temperature for deterministic improvements
        max_tokens=2048,
    )
    
    reply = response.choices[0].message.content or "No response from the LLM."
    return {"reply": reply}
```

**Note on routing**: The `/ai-improve` route is a **static path** and must be registered **before** the parameterized `/{prompt_id}` route to avoid FastAPI matching `ai-improve` as a `prompt_id`. See existing comment at line 87-88 of `app/routes/prompts.py`.

### 4.4 Frontend Implementation

#### New API Function

**File**: `frontend/src/services/promptsApi.ts`

```typescript
export function aiImprove(
  section: string,
  currentText: string,
  conversation: Array<{ role: string; content: string }>,
  model?: string,
): Promise<{ reply: string }> {
  return request<{ reply: string }>(`/api/prompts/ai-improve`, {
    method: 'POST',
    body: JSON.stringify({
      section,
      current_text: currentText,
      conversation,
      ...(model ? { model } : {}),
    }),
  });
}
```

#### PromptImprovementChat Component

**File**: `frontend/src/components/ui/PromptImprovementChat.tsx`

```typescript
interface PromptImprovementChatProps {
  open: boolean;
  sectionName: string;        // e.g., "Intention", "Restrictions"
  currentText: string;        // Current content shown as read-only context
  onClose: () => void;
  onApply: (improvedText: string) => void;  // Called when user clicks "Apply"
}

// Internal state:
// - messages: Array<{ role: 'user' | 'assistant'; content: string }>
// - input: string
// - sending: boolean
// - lastAssistantReply: string | null  // For the Apply button

// Behavior:
// 1. On open: messages=[], input="", lastAssistantReply=null
// 2. User types message → clicks Send
// 3. User message appended to messages
// 4. POST to /api/prompts/ai-improve with sectionName, currentText, messages
// 5. LLM reply appended as assistant message, stored in lastAssistantReply
// 6. "Apply" button enabled only when lastAssistantReply is non-null
// 7. On Apply: calls onApply(lastAssistantReply), closes modal
// 8. On Cancel: closes modal, no changes
```

#### PromptEditorSection Updates

**File**: `frontend/src/components/ui/PromptEditorSection.tsx`

Add an optional `onImprove` callback and render a sparkle/AI button next to the label:

```typescript
interface PromptEditorSectionProps {
  label: string;
  value: string;
  onChange: (val: string) => void;
  onImprove?: () => void;  // NEW: optional callback to open AI chat
}

// In render:
<div className="flex items-center justify-between">
  <span className="font-medium">{label}</span>
  {onImprove && (
    <button
      type="button"
      onClick={onImprove}
      className="text-xs text-primary-500 hover:text-primary-700 flex items-center gap-1"
      title="Improve with AI"
    >
      ✨ Improve with AI
    </button>
  )}
</div>
```

#### PromptManagement.tsx Updates

**File**: `frontend/src/pages/PromptManagement.tsx`

```typescript
// New state:
const [showImprovementChat, setShowImprovementChat] = useState(false);
const [improvingSection, setImprovingSection] = useState<string>("");
const [showCreateModal, setShowCreateModal] = useState(false);

// Handler to open AI chat for a specific section:
const handleImproveSection = (section: string) => {
  setImprovingSection(section);
  setShowImprovementChat(true);
};

// Handler to apply AI suggestion:
const handleApplyImprovement = (improvedText: string) => {
  const fieldMap: Record<string, keyof typeof editForm> = {
    "Intention": "intention",
    "Restrictions": "restrictions",
    "Output Structure": "output_structure",
    "User Prompt Template": "user_prompt_template",
  };
  const field = fieldMap[improvingSection];
  if (field) {
    setEditForm({ ...editForm, [field]: improvedText });
  }
  setShowImprovementChat(false);
  setImprovingSection("");
};

// Handler to create new prompt from scratch:
const handleCreateNewPrompt = async (promptId: string, name: string) => {
  try {
    await createPrompt(promptId, {
      name,
      intention: "",
      restrictions: "",
      output_structure: "",
      user_prompt_template: "",
    });
    showNotification(`Prompt "${promptId}" created successfully`, "success");
    // Reload prompt list
    const updated = await listAllPrompts();
    setAllPrompts(updated);
    setSelectedPromptId(promptId);
    setShowCreateModal(false);
  } catch (err) {
    showNotification(`Failed to create prompt: ${(err as Error).message}`, "error");
  }
};

// In render — Pass onImprove to each PromptEditorSection:
<PromptEditorSection
  label="Intention"
  value={editForm.intention}
  onChange={(v) => setEditForm({ ...editForm, intention: v })}
  onImprove={() => handleImproveSection("Intention")}
/>
// ... (same for Restrictions, Output Structure, User Prompt Template)

// Render modals:
{showCreateModal && (
  <CreatePromptModal
    open={showCreateModal}
    onClose={() => setShowCreateModal(false)}
    onCreate={handleCreateNewPrompt}
  />
)}

{showImprovementChat && (
  <PromptImprovementChat
    open={showImprovementChat}
    sectionName={improvingSection}
    currentText={
      improvingSection === "Intention" ? editForm.intention :
      improvingSection === "Restrictions" ? editForm.restrictions :
      improvingSection === "Output Structure" ? editForm.output_structure :
      editForm.user_prompt_template
    }
    onClose={() => { setShowImprovementChat(false); setImprovingSection(""); }}
    onApply={handleApplyImprovement}
  />
)}

// "+ New Prompt" button:
<Button variant="secondary" onClick={() => setShowCreateModal(true)}>
  + New Prompt
</Button>
```

---

## 5. Feature 3: Clone Section from Another Prompt/Version

### 5.1 User Experience

```
Current state:
  To reuse a section from another prompt, users must manually copy-paste

New flow:
  Click "Clone" button next to any section
  → Modal opens with prompt + version selectors
  → Select source prompt → Select source version → Preview source section content
  → Click "Clone" to replace current section with source content
  → Click "Cancel" to discard
```

### 5.2 UI Wireframe

```
┌──────────────────────────────────────────────┐
│  Clone Section from Another Prompt     [X]   │
├──────────────────────────────────────────────┤
│                                              │
│  Clone "Intention" section from:             │
│                                              │
│  Source Prompt                                │
│  ┌─────────────────────────────────────────┐ │
│  │  guest-search                 ▼        │ │
│  └─────────────────────────────────────────┘ │
│                                              │
│  Source Version                               │
│  ┌─────────────────────────────────────────┐ │
│  │  v3                             ▼        │ │
│  └─────────────────────────────────────────┘ │
│                                              │
│  Preview of source section:                   │
│  ┌─────────────────────────────────────────┐ │
│  │ You are a helpful hotel concierge...    │ │
│  │ You have access to database query tools │ │
│  └─────────────────────────────────────────┘ │
│                                              │
│                    [Cancel]  [Clone]         │
└──────────────────────────────────────────────┘
```

### 5.3 Backend Changes

**None required.** The existing `GET /api/prompts/{prompt_id}/{version}` endpoint (already exposed as `getByVersion` in the frontend API) returns a `PromptVersion` object containing all 4 section fields. This is sufficient to fetch the source section content.

### 5.4 Frontend Changes

| File | Changes |
|------|---------|
| `frontend/src/components/ui/CloneSectionModal.tsx` | **NEW** — Modal with prompt selector, version selector, section preview, and Clone/Cancel buttons. Uses `listAllPrompts()`, `listVersions()`, and `getByVersion()` from `promptsApi`. |
| `frontend/src/components/ui/PromptEditorSection.tsx` | Add `onClone?: () => void` prop. Render "Clone" button next to "Improve with AI" button. |
| `frontend/src/components/ui/index.ts` | Export `CloneSectionModal`. |
| `frontend/src/pages/PromptManagement.tsx` | Add `showCloneModal` and `cloningSection` state. Pass `onClone` callback to all 4 `PromptEditorSection` instances. Render `<CloneSectionModal>` when open. |

### 5.5 CloneSectionModal Component Spec

```typescript
interface CloneSectionModalProps {
  open: boolean;
  section: string;            // e.g., "intention", "restrictions" (the field key)
  sectionLabel: string;       // e.g., "Intention", "Restrictions" (display name)
  onClose: () => void;
  onClone: (text: string) => void;
}

// Internal state:
// - sourcePromptId: string
// - sourceVersion: number | null
// - previewText: string | null
// - loading: boolean
// - error: string | null
// - allPrompts: PromptSummary[]
// - sourceVersions: PromptVersion[]

// Behavior:
// 1. On open: fetch listAllPrompts() to populate prompt dropdown
// 2. When prompt selected: fetch listVersions(promptId) to populate version dropdown
// 3. When version selected: fetch getByVersion(promptId, version), extract the target section text, store in previewText
// 4. On Clone: call onClone(previewText), close modal
// 5. On Cancel: close modal, no changes
// 6. Clone button disabled until previewText is available
```

---

## 6. Task Breakdown (Dependency-Ordered)

Tasks are ordered by dependencies. Tasks on the same level can be worked on in parallel.

### Level 0 — No Dependencies

| # | Task | File(s) | Description |
|---|------|---------|-------------|
| **T1** | Backend: AI Improve Endpoint | `app/routes/prompts.py` | Add `POST /api/prompts/ai-improve` route with `AiImproveRequest`/`AiImproveResponse` schemas. Uses `get_llm_config()` + simple chat completion. **Critical**: register before `/{prompt_id}` route. |

### Level 1 — Depends on T1

| # | Task | File(s) | Description |
|---|------|---------|-------------|
| **T2** | Frontend API: AI Improve Function | `frontend/src/services/promptsApi.ts` | Add `aiImprove(section, currentText, conversation, model?)` function that calls `POST /api/prompts/ai-improve`. |

### Level 2 — Depends on T2 (Backend + API ready)

| # | Task | File(s) | Description |
|---|------|---------|-------------|
| **T3** | Frontend: PromptImprovementChat Component | `frontend/src/components/ui/PromptImprovementChat.tsx` | **NEW** — Chat modal component. Manages conversation state, calls `promptsApi.aiImprove()`, shows messages, provides Apply/Cancel buttons. |
| **T4** | Frontend: CreatePromptModal Component | `frontend/src/components/ui/CreatePromptModal.tsx` | **NEW** — Modal with prompt_id + name inputs, kebab-case validation, calls `promptsApi.create()`. |
| **T5** | Frontend: CloneSectionModal Component | `frontend/src/components/ui/CloneSectionModal.tsx` | **NEW** — Modal with prompt/version selectors, section preview, Clone/Cancel buttons. Uses existing `listAllPrompts()`, `listVersions()`, `getByVersion()` API functions. |
| **T6** | Frontend: Update PromptEditorSection | `frontend/src/components/ui/PromptEditorSection.tsx` | Add optional `onImprove` and `onClone` props. Render "Improve with AI" and "Clone" buttons next to label when callbacks are provided. |

### Level 3 — Depends on T3, T4, T5, T6 (All components ready)

| # | Task | File(s) | Description |
|---|------|---------|-------------|
| **T7** | Frontend: Export Components | `frontend/src/components/ui/index.ts` | Add `CreatePromptModal`, `PromptImprovementChat`, and `CloneSectionModal` to the barrel exports. |
| **T8** | Frontend: Wire Up PromptManagement | `frontend/src/pages/PromptManagement.tsx` | Add "+ New Prompt" button, `showCreateModal`, `showImprovementChat`, `showCloneModal` state. Pass `onImprove` and `onClone` callbacks to all 4 `PromptEditorSection` instances. Render all 3 modals conditionally. |

---

## 7. Files Summary

### New Files (3)

| File | Purpose | Task |
|------|---------|------|
| `frontend/src/components/ui/PromptImprovementChat.tsx` | Chat modal for AI-assisted prompt improvement | T3 |
| `frontend/src/components/ui/CreatePromptModal.tsx` | Modal for creating prompts from scratch | T4 |
| `frontend/src/components/ui/CloneSectionModal.tsx` | Modal for cloning a section from another prompt/version | T5 |

### Modified Files (5)

| File | Changes | Task |
|------|---------|------|
| `app/routes/prompts.py` | Add `POST /api/prompts/ai-improve` endpoint + request/response schemas | T1 |
| `frontend/src/services/promptsApi.ts` | Add `aiImprove()` function | T2 |
| `frontend/src/components/ui/PromptEditorSection.tsx` | Add `onImprove` and `onClone` props + buttons | T6 |
| `frontend/src/components/ui/index.ts` | Export all 3 new components | T7 |
| `frontend/src/pages/PromptManagement.tsx` | Wire up all 3 features (create, AI improve, clone) | T8 |

---

## 8. Testing Checklist

### Backend

- [ ] T1: `POST /api/prompts/ai-improve` returns LLM reply for valid request
- [ ] T1: Endpoint correctly includes section description in system prompt
- [ ] T1: Conversation history is properly forwarded to LLM
- [ ] T1: Route is registered before `/{prompt_id}` (no routing conflict)
- [ ] T1: Works with all 4 section types (intention, restrictions, output_structure, user_prompt_template)

### Frontend

- [ ] T4: CreatePromptModal validates prompt_id (kebab-case regex)
- [ ] T4: CreatePromptModal validates name (non-empty)
- [ ] T4: CreatePromptModal calls API and closes on success
- [ ] T4: CreatePromptModal shows error on duplicate prompt_id
- [ ] T3: PromptImprovementChat opens with empty conversation
- [ ] T3: PromptImprovementChat sends user message + current text to backend
- [ ] T3: PromptImprovementChat displays LLM reply in chat
- [ ] T3: PromptImprovementChat Apply button only enabled after LLM reply received
- [ ] T3: PromptImprovementChat Apply replaces section text and closes
- [ ] T3: PromptImprovementChat Cancel closes without changes
- [ ] T3: Multi-turn conversation works (user → AI → user → AI)
- [ ] T5: CloneSectionModal populates prompt dropdown on open
- [ ] T5: CloneSectionModal populates version dropdown when prompt selected
- [ ] T5: CloneSectionModal shows preview of source section when version selected
- [ ] T5: CloneSectionModal Clone button disabled until preview available
- [ ] T5: CloneSectionModal Clone replaces current section text and closes
- [ ] T5: CloneSectionModal Cancel closes without changes
- [ ] T6: "Improve with AI" button only shows when `onImprove` is provided
- [ ] T6: "Clone" button only shows when `onClone` is provided
- [ ] T8: "+ New Prompt" button opens CreatePromptModal
- [ ] T8: After creating new prompt, it's selected and shown in the editor
- [ ] T8: All 4 sections have AI improve and Clone buttons wired up correctly
- [ ] T8: Applying AI improvement updates the correct section field
- [ ] T8: Cloning section updates the correct section field

---

## 9. Implementation Order

```
T1 (Backend: AI Improve Endpoint)
  └── T2 (Frontend API: AI Improve Function)
          ├── T3 (PromptImprovementChat component)
          ├── T4 (CreatePromptModal component)
          ├── T5 (CloneSectionModal component)
          └── T6 (PromptEditorSection update - onImprove + onClone)
                  └── T7 (Export all 3 components)
                  └── T8 (Wire up PromptManagement page)
```

**Recommended execution order**: T1 → T2 → T3 → T4 → T5 → T6 → T7 → T8

---

## 10. Appendix: Section Descriptions for AI System Prompt

These descriptions are used in the `/api/prompts/ai-improve` system prompt to give the LLM context about which section is being improved:

| Section | Description |
|---------|-------------|
| `intention` | The Intention section defines what the LLM assistant should do — its purpose, role, and core responsibilities. It sets the overall behavior and tone of the assistant. |
| `restrictions` | The Restrictions section defines rules, constraints, and boundaries the LLM must follow. This includes formatting rules, negative constraints ("never do X"), and behavioral guardrails. |
| `output_structure` | The Output Structure section defines the expected format and structure of the LLM's responses. This typically includes markdown templates, headings, bullet points, and data field layouts. |
| `user_prompt_template` | The User Prompt Template is the dynamic user message sent to the LLM at query time. It may contain placeholders like `{customer_name}` that are resolved from runtime variables before being sent to the LLM. |

---

*End of plan document.*