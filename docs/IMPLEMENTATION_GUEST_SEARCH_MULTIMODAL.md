# ConciergeOS -- Guest Search Multi-Modal Input Implementation

> **Purpose**: Step-by-step implementation guide for adding photo upload, camera capture, region selection, and voice input to the Guest Search page.
> **Audience**: LLM agent capable of implementing the full feature from this document alone.
> **Last Updated**: 2026-06-28

---

## Table of Contents

1. [Overview](#1-overview)
2. [Dependency Graph](#2-dependency-graph)
3. [Phase 1: Backend Schemas](#3-phase-1-backend-schemas)
4. [Phase 2: Backend Extraction Service](#4-phase-2-backend-extraction-service)
5. [Phase 3: Backend Route](#5-phase-3-backend-route)
6. [Phase 4: Frontend API Client](#6-phase-4-frontend-api-client)
7. [Phase 5: Frontend RegionSelector Component](#7-phase-5-frontend-regionselector-component)
8. [Phase 6: Frontend GuestSearch Page](#8-phase-6-frontend-guestsearch-page)
9. [Testing](#9-testing)

---

## 1. Overview

The Guest Search page currently accepts a plain text customer name. This enhancement adds three additional input methods:

1. **Photo Upload** -- Select an image file from the device (ID card, booking confirmation, handwritten note). Display it in a preview area, allow the operator to draw a rectangle around the name region, then send the image (optionally cropped) to the LLM for name extraction.
2. **Camera Capture** -- On mobile devices, open the rear camera directly. Same preview, region selection, and extraction flow as photo upload.
3. **Voice Input** -- Record audio via the browser MediaRecorder API, send the audio blob to the LLM (Gemma4 multimodal) for speech-to-text name extraction.

After extraction, the LLM returns a name string that is auto-populated into the existing Customer Name input field. The operator reviews, edits if needed, then presses Search as before.

### Models Used

| Modality | Model    | Endpoint              |
|----------|----------|-----------------------|
| Vision   | Qwen3-VL | Existing vLLM (OpenAI-compatible) |
| Audio    | Gemma4   | Existing vLLM (OpenAI-compatible) |

### Existing Components Reused

The following components from `frontend/src/components/ui/` are reused as-is:

| Component  | Source              | Usage                                    |
|------------|---------------------|------------------------------------------|
| `Card`     | `Card.tsx`          | Sections wrapper                         |
| `Button`   | `Button.tsx`        | Upload, Camera, Record, Extract, Search  |
| `Input`    | `Input.tsx`         | Customer name text field                 |
| `FormField`| `FormField.tsx`     | Label + input wrapper                    |
| `PageHeader`| `PageHeader.tsx`   | Page title and description               |
| `Toast`    | `Toast.tsx`         | Success/error notifications              |
| `Badge`    | `Badge.tsx`         | Recording indicator, status labels       |
| `PromptSelector` | `PromptSelector.tsx` | Prompt version dropdown                |

---

## 2. Dependency Graph

```
Phase 1: Backend Schemas (app/schemas.py)
    |
    +-> Phase 2: Backend Extraction Service (app/services/guest_extraction.py)
              |
              +-> Phase 3: Backend Route (app/routes/guest_search.py)
                        |
                        +-> Phase 4: Frontend API Client (frontend/src/services/api.ts)
                                  |
                                  +-> Phase 5: Frontend RegionSelector (frontend/src/components/ui/RegionSelector.tsx)
                                  |        |
                                  +-> Phase 6: Frontend GuestSearch Page (frontend/src/pages/GuestSearch.tsx)
```

Each phase must be completed in order. Phase 5 (RegionSelector) and Phase 4 (API Client) can be worked on in parallel since they are independent of each other, but both are required before Phase 6.

---

## 3. Phase 1: Backend Schemas

**File**: `app/schemas.py`

### 3.1 Add `NameExtractionResponse`

Append after the existing `GuestSearchResponse` class (line 133):

```python
class NameExtractionResponse(BaseModel):
    """Response from the extract-name endpoint."""

    extracted_name: str = Field(..., description="The name extracted from the media by the LLM")
    confidence: float = Field(default=1.0, description="LLM confidence score (0.0-1.0), optional")
    model: str = Field(default="", description="Model used for extraction")
```

No request schema is needed because the endpoint accepts `multipart/form-data` directly via FastAPI's `UploadFile` and `Form` parameters, not a JSON body.

---

## 4. Phase 2: Backend Extraction Service

**File**: `app/services/guest_extraction.py` (NEW)

### 4.1 Module Structure

```python
#!/usr/bin/env python3
"""Multi-modal name extraction service.

Uses the LLM to extract a person's name from an image (with optional crop region)
or an audio recording.
"""

import base64
import io
import logging
from typing import Any

from openai import OpenAI

from app.config import config_manager
from PIL import Image

logger = logging.getLogger(__name__)
```

### 4.2 Image Cropping Helper

```python
def crop_image(image_bytes: bytes, crop_x: float, crop_y: float, crop_w: float, crop_h: float) -> bytes:
    """Crop an image using normalized coordinates (0.0-1.0).

    Args:
        image_bytes: Raw image data (any format supported by Pillow).
        crop_x: Left edge as fraction of image width.
        crop_y: Top edge as fraction of image height.
        crop_w: Width as fraction of image width.
        crop_h: Height as fraction of image height.

    Returns:
        Cropped image as PNG bytes.
    """
    img = Image.open(io.BytesIO(image_bytes))
    w, h = img.size

    left = int(crop_x * w)
    top = int(crop_y * h)
    right = int((crop_x + crop_w) * w)
    bottom = int((crop_y + crop_h) * h)

    # Clamp to image bounds
    left = max(0, min(left, w))
    top = max(0, min(top, h))
    right = max(0, min(right, w))
    bottom = max(0, min(bottom, h))

    cropped = img.crop((left, top, right, bottom))
    buffer = io.BytesIO()
    cropped.save(buffer, format="PNG")
    return buffer.getvalue()
```

### 4.3 LLM Client Builder

```python
def _get_vision_client() -> tuple[OpenAI, str]:
    """Create an OpenAI client configured for vision (Qwen3-VL)."""
    models_endpoint = config_manager.test_settings.models_endpoint
    base_url = models_endpoint.rstrip('/').replace('/models', '')
    client = OpenAI(base_url=base_url, api_key="none")

    # Try to find a Qwen3-VL model, fall back to first available
    try:
        models = client.models.list()
        for m in models.data:
            if "qwen3" in m.id.lower() and ("vl" in m.id.lower() or "vision" in m.id.lower()):
                return client, m.id
        # Fallback: try any qwen3 model
        for m in models.data:
            if "qwen3" in m.id.lower():
                return client, m.id
        # Ultimate fallback
        if models.data:
            return client, models.data[0].id
    except Exception as e:
        logger.warning("Failed to auto-select vision model: %s", e)

    return client, "Qwen3-VL"  # Default identifier
```

```python
def _get_audio_client() -> tuple[OpenAI, str]:
    """Create an OpenAI client configured for audio (Gemma4)."""
    models_endpoint = config_manager.test_settings.models_endpoint
    base_url = models_endpoint.rstrip('/').replace('/models', '')
    client = OpenAI(base_url=base_url, api_key="none")

    try:
        models = client.models.list()
        for m in models.data:
            if "gemma" in m.id.lower() and "4" in m.id.lower():
                return client, m.id
        for m in models.data:
            if "gemma4" in m.id.lower() or "gemma-4" in m.id.lower():
                return client, m.id
        if models.data:
            return client, models.data[0].id
    except Exception as e:
        logger.warning("Failed to auto-select audio model: %s", e)

    return client, "Gemma4"
```

### 4.4 Extract Name from Image

```python
VISION_PROMPT = (
    "Extract the person's name from this image. "
    "The image may show an ID card, booking confirmation, document, or handwritten note. "
    "Return only the name, nothing else. Do not include titles, greetings, or explanations."
)


def extract_name_from_image(
    image_bytes: bytes,
    crop_x: float | None = None,
    crop_y: float | None = None,
    crop_w: float | None = None,
    crop_h: float | None = None,
) -> tuple[str, str]:
    """Extract a name from an image using Qwen3-VL.

    If crop coordinates are provided, crop the image first.
    Returns (extracted_name, model_id).
    """
    client, model_id = _get_vision_client()

    # Crop if coordinates provided
    if crop_x is not None and crop_y is not None and crop_w is not None and crop_h is not None:
        image_bytes = crop_image(image_bytes, crop_x, crop_y, crop_w, crop_h)

    # Convert to base64 data URL
    ext = _detect_image_ext(image_bytes)
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    data_url = f"data:image/{ext};base64,{b64}"

    response = client.chat.completions.create(
        model=model_id,
        messages=[
            {"role": "user", "content": [
                {"type": "text", "text": VISION_PROMPT},
                {"type": "image_url", "image_url": {"url": data_url}},
            ]},
        ],
        max_tokens=100,
    )

    name = response.choices[0].message.content.strip()
    return name, model_id
```

### 4.5 Extract Name from Audio

```python
AUDIO_PROMPT = (
    "Transcribe the spoken name in this audio recording. "
    "Return only the name, nothing else. Do not include greetings or explanations."
)


def extract_name_from_audio(audio_bytes: bytes, audio_format: str) -> tuple[str, str]:
    """Extract a name from an audio recording using Gemma4.

    Returns (extracted_name, model_id).
    """
    client, model_id = _get_audio_client()

    b64 = base64.b64encode(audio_bytes).decode("utf-8")
    data_url = f"data:audio/{audio_format};base64,{b64}"

    response = client.chat.completions.create(
        model=model_id,
        messages=[
            {"role": "user", "content": [
                {"type": "text", "text": AUDIO_PROMPT},
                {"type": "input_audio", "input_audio": {
                    "data": b64,
                    "format": audio_format,
                }},
            ]},
        ],
        max_tokens=100,
    )

    name = response.choices[0].message.content.strip()
    return name, model_id
```

### 4.6 Image Format Detection Helper

```python
def _detect_image_ext(image_bytes: bytes) -> str:
    """Detect image format from magic bytes. Returns 'png' by default."""
    header = image_bytes[:8]
    if header[:8] == b'\x89PNG\r\n\x1a\n':
        return "png"
    if header[:2] == b'\xff\xd8':
        return "jpeg"
    if header[:4] == b'GIF8':
        return "gif"
    if header[:4] == b'RIFF' and header[8:12] == b'WEBP':
        return "webp"
    return "png"
```

### 4.7 Dependencies

Add `Pillow` to the project dependencies in `pyproject.toml` if not already present. Verify with:

```bash
grep -i pillow pyproject.toml
```

If missing, add under `[project.dependencies]`:
```
Pillow>=10.0.0
```

---

## 5. Phase 3: Backend Route

**File**: `app/routes/guest_search.py`

### 5.1 Add Imports

```python
from fastapi import APIRouter, UploadFile, File, Form, HTTPException

from app.schemas import GuestSearchRequest, GuestSearchResponse, NameExtractionResponse
from app.services import query_guest_with_llm
from app.services.guest_extraction import extract_name_from_image, extract_name_from_audio
```

### 5.2 Add Extraction Endpoint

Append after the existing `api_guest_search` route:

```python
@router.post("/api/guest-search/extract-name")
async def api_extract_name(
    file: UploadFile = File(..., description="Image or audio file"),
    crop_x: float | None = Form(None, ge=0.0, le=1.0),
    crop_y: float | None = Form(None, ge=0.0, le=1.0),
    crop_w: float | None = Form(None, ge=0.0, le=1.0),
    crop_h: float | None = Form(None, ge=0.0, le=1.0),
) -> NameExtractionResponse:
    """Extract a person's name from an image or audio file using the LLM.

    For images, optional crop coordinates (0.0-1.0) can be provided to focus
    on a specific region of the image.
    """
    content = await file.read()
    content_type = file.content_type or ""

    try:
        if content_type.startswith("image/"):
            name, model = extract_name_from_image(
                content,
                crop_x=crop_x,
                crop_y=crop_y,
                crop_w=crop_w,
                crop_h=crop_h,
            )
        elif content_type.startswith("audio/"):
            # Detect audio format from content type
            audio_format = content_type.split("/")[-1].split(";")[0].strip()
            # Normalize common formats
            format_map = {
                "webm": "webm",
                "wav": "wav",
                "mp4": "mp4",
                "mp3": "mp3",
                "ogg": "ogg",
                "m4a": "m4a",
            }
            audio_format = format_map.get(audio_format, "webm")
            name, model = extract_name_from_audio(content, audio_format)
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported content type: {content_type}. Expected image/* or audio/*",
            )

        return NameExtractionResponse(
            extracted_name=name,
            confidence=1.0,
            model=model,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Name extraction failed: {str(e)}")
```

### 5.3 Register Router

Verify the guest_search router is mounted in `app/main.py`. Check the existing registration pattern and ensure the new route is included (it will be automatically since it is on the same router).

---

## 6. Phase 4: Frontend API Client

**File**: `frontend/src/services/api.ts`

### 6.1 Add Response Type

Add to the imports at the top:

```typescript
export interface NameExtractionResponse {
  extracted_name: string;
  confidence: number;
  model: string;
}
```

### 6.2 Add `extractName` Method

Append to the existing `guestSearchApi` object:

```typescript
export const guestSearchApi = {
  // ... existing search method ...

  extractName: (
    file: File,
    crop?: { x: number; y: number; w: number; h: number },
  ) => {
    const formData = new FormData();
    formData.append("file", file);
    if (crop) {
      formData.append("crop_x", String(crop.x));
      formData.append("crop_y", String(crop.y));
      formData.append("crop_w", String(crop.w));
      formData.append("crop_h", String(crop.h));
    }
    return request<NameExtractionResponse>('/api/guest-search/extract-name', {
      method: 'POST',
      headers: {},  // Let browser set Content-Type (multipart boundary)
      body: formData,
    });
  },
};
```

IMPORTANT: The `request` helper in `api.ts` currently forces `Content-Type: application/json` on all requests. For the `extractName` call, this header must be omitted so the browser can set the correct `multipart/form-data` boundary. Update the `request` function to conditionally apply the header:

```typescript
async function request<T>(url: string, options?: RequestInit & { omitContentType?: true }): Promise<T> {
  const headers = options?.omitContentType
    ? {}
    : { 'Content-Type': 'application/json', ...(options?.headers || {}) };
  
  const resp = await fetch(url, {
    headers,
    ...options,
  });
  // ... rest of the function unchanged ...
}
```

However, to minimize changes to the shared `request` helper, a simpler approach is to use `fetch` directly in the `extractName` method rather than going through `request`. This avoids modifying the generic helper:

```typescript
extractName: (
  file: File,
  crop?: { x: number; y: number; w: number; h: number },
): Promise<NameExtractionResponse> => {
  return new Promise((resolve, reject) => {
    const formData = new FormData();
    formData.append("file", file);
    if (crop) {
      formData.append("crop_x", String(crop.x));
      formData.append("crop_y", String(crop.y));
      formData.append("crop_w", String(crop.w));
      formData.append("crop_h", String(crop.h));
    }
    fetch('/api/guest-search/extract-name', {
      method: 'POST',
      body: formData,
    })
      .then(async (resp) => {
        if (!resp.ok) {
          const body = await resp.text().catch(() => '');
          throw new Error(resp.statusText + (body ? `: ${body}` : ''));
        }
        const text = await resp.text();
        if (!text) reject(new Error('Empty response'));
        resolve(JSON.parse(text) as NameExtractionResponse);
      })
      .catch(reject);
  });
},
```

---

## 7. Phase 5: Frontend RegionSelector Component

**File**: `frontend/src/components/ui/RegionSelector.tsx` (NEW)

### 7.1 Purpose

Renders an image with an overlaid canvas that allows the user to draw a rectangular selection region by clicking and dragging. Supports both mouse and touch events. Returns the selected region as normalized coordinates (0.0-1.0 relative to the original image natural dimensions).

### 7.2 Component Interface

```typescript
import { useState, useRef, useCallback, useEffect } from "react";

interface Selection {
  x: number;  // 0.0-1.0 relative to natural image width
  y: number;  // 0.0-1.0 relative to natural image height
  w: number;  // 0.0-1.0
  h: number;  // 0.0-1.0
}

interface RegionSelectorProps {
  imageSrc: string;           // data URL or object URL of the image
  naturalWidth: number;       // image.naturalWidth (original pixel dimensions)
  naturalHeight: number;
  onSelect: (selection: Selection | null) => void;
  className?: string;
}

export default function RegionSelector({
  imageSrc,
  naturalWidth,
  naturalHeight,
  onSelect,
  className = "",
}: RegionSelectorProps) {
  // ...
}
```

### 7.3 Implementation Details

State:
- `selection: Selection | null` -- current rectangle
- `isDrawing: boolean` -- whether the user is currently dragging
- `start: { x: number, y: number } | null` -- draw start position in canvas pixel coords
- `current: { x: number, y: number } | null` -- current drag endpoint in canvas pixel coords

Refs:
- `canvasRef: HTMLCanvasElement` -- the overlay canvas
- `imageRef: HTMLImageElement` -- the displayed image
- `containerRef: HTMLDivElement` -- relative-positioned wrapper

Constants:
- `HIGHLIGHT_COLOR = "rgba(34, 197, 94, 0.9)"` -- green border
- `HIGHLIGHT_FILL = "rgba(34, 197, 94, 0.15)"` -- semi-transparent fill

Key functions:

```typescript
const getCanvasCoords = (clientX: number, clientY: number) => {
  const rect = canvasRef.current.getBoundingClientRect();
  return {
    x: clientX - rect.left,
    y: clientY - rect.top,
  };
};

const toNormalized = (pxX: number, pxY: number, pxW: number, pxH: number): Selection => {
  // Convert from displayed canvas pixel coords to normalized (0-1) relative to natural image size
  const scaleX = naturalWidth / canvasRef.current.width;
  const scaleY = naturalHeight / canvasRef.current.height;
  return {
    x: Math.max(0, pxX * scaleX),
    y: Math.max(0, pxY * scaleY),
    w: Math.max(0, pxW * scaleX),
    h: Math.max(0, pxH * scaleY),
  };
};
```

Normalization: Because the displayed image is scaled to fit the container, the pixel coordinates on the canvas must be converted to coordinates relative to the displayed image size, then scaled by the ratio of natural-to-displayed dimensions.

```typescript
// More robust normalization using the displayed image element dimensions:
const toNormalized = (pxX: number, pxY: number, pxW: number, pxH: number): Selection => {
  const img = imageRef.current;
  const displayW = img.clientWidth;
  const displayH = img.clientHeight;
  return {
    x: Math.max(0, Math.min(1, pxX / displayW)),
    y: Math.max(0, Math.min(1, pxY / displayH)),
    w: Math.max(0, Math.min(1, pxW / displayW)),
    h: Math.max(0, Math.min(1, pxH / displayH)),
  };
};
```

Drawing:

```typescript
const draw = useCallback(() => {
  const ctx = canvasRef.current.getContext("2d");
  if (!ctx) return;
  ctx.clearRect(0, 0, canvasRef.current.width, canvasRef.current.height);

  if (current && start) {
    const x = Math.min(start.x, current.x);
    const y = Math.min(start.y, current.y);
    const w = Math.abs(current.x - start.x);
    const h = Math.abs(current.y - start.y);
    ctx.fillStyle = HIGHLIGHT_FILL;
    ctx.fillRect(x, y, w, h);
    ctx.strokeStyle = HIGHLIGHT_COLOR;
    ctx.lineWidth = 2;
    ctx.strokeRect(x, y, w, h);
  }
}, [start, current]);
```

Canvas sizing (match displayed image):

```typescript
useEffect(() => {
  const img = imageRef.current;
  if (!img || !canvasRef.current) return;
  const updateSize = () => {
    canvasRef.current.width = img.clientWidth;
    canvasRef.current.height = img.clientHeight;
    draw();
  };
  updateSize();
  window.addEventListener("resize", updateSize);
  return () => window.removeEventListener("resize", updateSize);
}, [imageSrc, draw]);
```

Touch support: Use `touchstart`, `touchmove`, `touchend` with `e.touches[0].clientX/Y` and `e.preventDefault()` to avoid scrolling while drawing.

Mouse events: `onMouseDown`, `onMouseMove`, `onMouseUp`.

Clear handler: On double-click, clear the selection and call `onSelect(null)`.

### 7.4 Render Structure

```tsx
return (
  <div className={`relative inline-block ${className}`} ref={containerRef}>
    <img
      ref={imageRef}
      src={imageSrc}
      alt="Preview"
      className="max-w-full rounded-md block"
      onLoad={() => { /* trigger canvas resize */ }}
    />
    <canvas
      ref={canvasRef}
      className="absolute inset-0 w-full h-full cursor-crosshair"
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseUp}
      onTouchStart={handleTouchStart}
      onTouchMove={handleTouchMove}
      onTouchEnd={handleTouchEnd}
      onDoubleClick={handleDoubleClick}
    />
  </div>
);
```

### 7.5 Export from index.ts

Add to `frontend/src/components/ui/index.ts`:

```typescript
export { default as RegionSelector } from "./RegionSelector";
```

---

## 8. Phase 6: Frontend GuestSearch Page

**File**: `frontend/src/pages/GuestSearch.tsx`

### 8.1 New State Variables

```typescript
// Media input state
const [mediaFile, setMediaFile] = useState<File | null>(null);
const [mediaPreview, setMediaPreview] = useState<string | null>(null);  // object URL
const [imageNaturalSize, setImageNaturalSize] = useState<{ w: number; h: number } | null>(null);
const [selection, setSelection] = useState<{ x: number; y: number; w: number; h: number } | null>(null);
const [extracting, setExtracting] = useState(false);

// Voice recording state
const [recording, setRecording] = useState(false);
const [mediaRecorder, setMediaRecorder] = useState<MediaRecorder | null>(null);
const [audioChunks, setAudioChunks] = useState<Blob[]>([]);
```

### 8.2 Hidden File Inputs

Two hidden `<input>` elements for file selection, toggled via `<Button>` clicks:

```tsx
<input
  id="photoUpload"
  type="file"
  accept="image/*"
  className="hidden"
  onChange={handleFileSelect}
/>
<input
  id="photoCamera"
  type="file"
  accept="image/*"
  capture="environment"
  className="hidden"
  onChange={handleFileSelect}
/>
```

The `capture="environment"` attribute on the second input triggers the rear camera on mobile devices.

### 8.3 File Selection Handler

```typescript
const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
  const file = e.target.files?.[0];
  if (!file) return;

  // Clear previous state
  setSelection(null);
  if (mediaPreview) URL.revokeObjectURL(mediaPreview);

  setMediaFile(file);
  setMediaPreview(URL.createObjectURL(file));

  // Load natural dimensions for region selector
  if (file.type.startsWith("image/")) {
    const img = new Image();
    img.onload = () => {
      setImageNaturalSize({ w: img.naturalWidth, h: img.naturalHeight });
    };
    img.src = URL.createObjectURL(file);
  }
};
```

### 8.4 Voice Recording Handlers

```typescript
const startRecording = async () => {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const recorder = new MediaRecorder(stream);
    const chunks: Blob[] = [];

    recorder.ondataavailable = (e) => {
      if (e.data.size > 0) chunks.push(e.data);
    };

    recorder.onstop = () => {
      const blob = new Blob(chunks, { type: recorder.mimeType || "audio/webm" });
      const file = new File([blob], "recording.webm", { type: blob.type });
      setMediaFile(file);
      // No preview for audio
      setMediaPreview(null);
      setImageNaturalSize(null);
      setSelection(null);
      setAudioChunks([]);
    };

    recorder.start();
    setMediaRecorder(recorder);
    setRecording(true);
    setAudioChunks(chunks);
  } catch (e) {
    setToast({ message: "Microphone access denied", type: "error" });
  }
};

const stopRecording = () => {
  mediaRecorder?.stop();
  setRecording(false);
  // Stop all tracks to release the microphone
  mediaRecorder?.stream?.getTracks().forEach((t) => t.stop());
};
```

### 8.5 Extract Name Handler

```typescript
const handleExtractName = async () => {
  if (!mediaFile) {
    setToast({ message: "No media selected", type: "error" });
    return;
  }

  setExtracting(true);
  try {
    const data = await guestSearchApi.extractName(mediaFile, selection || undefined);
    setQuery(data.extracted_name);
    setToast({ message: `Name extracted: ${data.extracted_name}`, type: "success" });
  } catch (e: unknown) {
    setToast({ message: e instanceof Error ? e.message : "Extraction failed", type: "error" });
  } finally {
    setExtracting(false);
  }
};
```

### 8.6 Clear Media Handler

```typescript
const handleClearMedia = () => {
  if (mediaPreview) URL.revokeObjectURL(mediaPreview);
  setMediaFile(null);
  setMediaPreview(null);
  setImageNaturalSize(null);
  setSelection(null);
};
```

### 8.7 Updated Render

The Card body is restructured to include the media input section above the existing Customer Name field:

```tsx
<Card>
  {/* Prompt selector (existing) */}
  <div className="mt-4">
    <PromptSelector ... />
  </div>

  {/* NEW: Multi-modal input section */}
  <div className="mt-4">
    <div className="flex gap-2 flex-wrap">
      <Button variant="secondary" onClick={() => document.getElementById("photoUpload")?.click()}>
        Upload Photo
      </Button>
      <Button variant="secondary" onClick={() => document.getElementById("photoCamera")?.click()}>
        Take Photo
      </Button>
      <Button
        variant={recording ? "danger" : "secondary"}
        onClick={recording ? stopRecording : startRecording}
      >
        {recording ? "Stop Recording" : "Record Voice"}
      </Button>
      {mediaFile && (
        <Button variant="ghost" onClick={handleClearMedia}>
          Clear
        </Button>
      )}
    </div>

    {/* Hidden file inputs */}
    <input id="photoUpload" type="file" accept="image/*" className="hidden" onChange={handleFileSelect} />
    <input id="photoCamera" type="file" accept="image/*" capture="environment" className="hidden" onChange={handleFileSelect} />
  </div>

  {/* NEW: Media preview with region selector */}
  {mediaPreview && imageNaturalSize && (
    <div className="mt-4">
      <RegionSelector
        imageSrc={mediaPreview}
        naturalWidth={imageNaturalSize.w}
        naturalHeight={imageNaturalSize.h}
        onSelect={setSelection}
      />
      <p className="mt-1 text-xs text-primary-500 dark:text-primary-400">
        Click and drag to select the name region. Double-click to clear.
      </p>
    </div>
  )}

  {/* Audio recording indicator */}
  {mediaFile && mediaFile.type.startsWith("audio/") && !mediaPreview && (
    <div className="mt-4 flex items-center gap-2">
      <Badge variant="secondary">Audio recording selected</Badge>
    </div>
  )}

  {/* Recording indicator */}
  {recording && (
    <div className="mt-4 flex items-center gap-2">
      <Badge variant="danger">Recording...</Badge>
    </div>
  )}

  {/* NEW: Extract Name button */}
  {mediaFile && (
    <div className="mt-4 flex justify-between items-center">
      <p className="text-xs text-primary-500 dark:text-primary-400">
        {mediaFile.name}
        {selection ? ` (region selected)` : ""}
      </p>
      <Button variant="accent" loading={extracting} onClick={handleExtractName}>
        Extract Name
      </Button>
    </div>
  )}

  {/* EXISTING: Customer Name input */}
  <div className="mt-4">
    <FormField htmlFor="guestQuery" label="Customer Name">
      <Input
        id="guestQuery"
        type="text"
        placeholder="e.g. عائشة إبراهيم"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        onKeyDown={handleKeyDown}
      />
    </FormField>
  </div>

  {/* EXISTING: Search button */}
  <div className="mt-4 flex justify-end">
    <Button variant="primary" loading={loading} onClick={handleSearch}>
      Search
    </Button>
  </div>
</Card>
```

### 8.8 Cleanup Effect

Add a `useEffect` cleanup to revoke object URLs on unmount:

```typescript
import { useState, useEffect } from "react";

// ... inside component:
useEffect(() => {
  return () => {
    if (mediaPreview) URL.revokeObjectURL(mediaPreview);
  };
}, [mediaPreview]);
```

---

## 9. Testing

### 9.1 Backend Tests

1. Start the server: `uv run uvicorn app.main:app --reload`
2. Test image extraction with curl:
   ```bash
   curl -X POST http://localhost:8000/api/guest-search/extract-name \
     -F "file=@/path/to/test_image.jpg" \
     -F "crop_x=0.2" -F "crop_y=0.3" -F "crop_w=0.4" -F "crop_h=0.1"
   ```
3. Test audio extraction with curl:
   ```bash
   curl -X POST http://localhost:8000/api/guest-search/extract-name \
     -F "file=@/path/to/test_audio.webm"
   ```
4. Verify Pillow is installed: `uv run python -c "from PIL import Image; print('OK')"`

### 9.2 Frontend Tests

1. Build the frontend: `cd frontend && npm run build`
2. Check for TypeScript errors: `cd frontend && npx tsc --noEmit`
3. Verify the page renders at `/guest-search`
4. Test each input method:
   - Upload a photo with text (ID card mockup), draw a rectangle, extract name
   - Use camera on mobile device, extract name
   - Record voice saying a guest name, extract name
5. Verify the extracted name populates the input field
6. Verify Search still works as before with the populated name

### 9.3 End-to-End Flow

```
1. Navigate to /guest-search
2. Click "Upload Photo" and select an image with a visible name
3. Draw a rectangle around the name region on the preview
4. Click "Extract Name"
5. Verify the name field is populated
6. Edit the name if needed
7. Click "Search"
8. Verify the LLM response appears below
```

---

## Appendix A: Complete File List

| Phase | File | Action |
|-------|------|--------|
| 1 | `app/schemas.py` | Modify -- add `NameExtractionResponse` |
| 2 | `app/services/guest_extraction.py` | Create -- new extraction service |
| 2 | `pyproject.toml` | Modify -- add Pillow dependency if missing |
| 3 | `app/routes/guest_search.py` | Modify -- add extract-name endpoint, update imports |
| 4 | `frontend/src/services/api.ts` | Modify -- add `extractName` method and type |
| 5 | `frontend/src/components/ui/RegionSelector.tsx` | Create -- canvas region selector |
| 5 | `frontend/src/components/ui/index.ts` | Modify -- export RegionSelector |
| 6 | `frontend/src/pages/GuestSearch.tsx` | Modify -- add media input, preview, recording |

## Appendix B: Color Palette Reference

Use the existing Tailwind color tokens already defined in the project:

| Token | Usage |
|-------|-------|
| `secondary-400` | Primary action buttons |
| `accent-400` | Extract Name button |
| `accent-600` | Danger/stop recording button |
| `surface-200` | Secondary buttons |
| `green-600` | Region selection highlight (rgba in canvas) |

## Appendix C: Accessibility

- All buttons have visible text labels (no icon-only buttons)
- The canvas region selector is keyboard-accessible via Tab + Enter to start selection, arrow keys to adjust, Escape to cancel
- `aria-label` attributes on hidden file inputs for screen readers
- Recording state is announced via a visible Badge element
- The Extract Name button is disabled when no media is selected