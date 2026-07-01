"""
Multimodal name extraction service for Guest Search.

Supports extracting guest names from:
- Images (vision LLM)
- Audio recordings (multimodal LLM)

Uses the model configured in app/config.json under test_settings.model_name.
"""

import base64
import logging
import os
import subprocess
from datetime import datetime
from io import BytesIO

from typing import cast

from openai import OpenAI
from openai.types.chat import ChatCompletionUserMessageParam
from PIL import Image

from app.config import config_manager
from app.services.llm import get_llm_config_by_model_id, _build_client_from_model

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Image Cropping
# ---------------------------------------------------------------------------

def crop_image(image_bytes: bytes, x: float, y: float, width: float, height: float) -> bytes:
    """
    Crop an image using normalized coordinates (0.0-1.0).

    Args:
        image_bytes: Raw image data (any format PIL supports).
        x: Normalized X offset of crop region (0.0-1.0).
        y: Normalized Y offset of crop region (0.0-1.0).
        width: Normalized width of crop region (0.0-1.0).
        height: Normalized height of crop region (0.0-1.0).

    Returns:
        Cropped image as PNG bytes.
    """
    img = Image.open(BytesIO(image_bytes))
    img_w, img_h = img.size

    # Convert normalized coordinates to absolute pixel values
    left = int(x * img_w)
    top = int(y * img_h)
    right = int((x + width) * img_w)
    bottom = int((y + height) * img_h)

    # Clamp to image bounds
    left = max(0, min(left, img_w))
    top = max(0, min(top, img_h))
    right = max(0, min(right, img_w))
    bottom = max(0, min(bottom, img_h))

    cropped = img.crop((left, top, right, bottom))
    output = BytesIO()
    cropped.save(output, format="PNG")
    return output.getvalue()


# ---------------------------------------------------------------------------
# LLM Client
# ---------------------------------------------------------------------------

def _get_client_and_model(model_id: int | None = None) -> tuple[OpenAI, str]:
    """
    Create an OpenAI client and return it along with the configured model name.

    If model_id is provided, looks up the model from the LLMModels table.
    Otherwise falls back to the config.json settings.
    """
    if model_id is not None:
        client, model_name = get_llm_config_by_model_id(model_id)
        logger.info("Using model '%s' (DB model_id=%s) for extraction", model_name, model_id)
        return client, model_name

    # Build a minimal model-like object for _build_client_from_model
    class _ConfigModel:
        endpoint: str = config_manager.test_settings.models_endpoint
        model_name: str = config_manager.test_settings.model_name

    config_model = _ConfigModel()
    client, model_name = _build_client_from_model(config_model)
    logger.info("Using model '%s' at base URL '%s' for extraction", model_name, config_model.endpoint)
    return client, model_name


# ---------------------------------------------------------------------------
# Helper: Detect image extension from bytes
# ---------------------------------------------------------------------------

def _detect_image_ext(image_bytes: bytes) -> str:
    """Detect image file extension from magic bytes."""
    header = image_bytes[:8]
    if header[:8] == b'\x89PNG\r\n\x1a\n':
        return "png"
    elif header[:2] == b'\xff\xd8':
        return "jpeg"
    elif header[:4] == b'GIF8':
        return "gif"
    elif header[:4] == b'RIFF' and header[8:12] == b'WEBP':
        return "webp"
    # Default fallback
    return "png"


# ---------------------------------------------------------------------------
# Public API: Extract name from image
# ---------------------------------------------------------------------------

VISION_SYSTEM_PROMPT = (
    "You are a hotel concierge assistant. Your task is to extract the guest's name "
    "from the provided image. The image shows a region that may contain text"
    "Return ONLY the name as plain text, with no extra commentary."
)


def extract_name_from_image(image_bytes: bytes, cropped: bool = False, model_id: int | None = None) -> str:
    """
    Send an image to the configured LLM and extract the guest name.

    Args:
        image_bytes: Raw image data (already cropped if cropped=True).
        cropped: Whether the image was pre-cropped.
        model_id: Optional LLM model ID to use for extraction.

    Returns:
        Extracted name string.
    """
    client, model = _get_client_and_model(model_id)

    ext = _detect_image_ext(image_bytes)
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    mime_map = {
        "png": "image/png",
        "jpeg": "image/jpeg",
        "jpg": "image/jpeg",
        "gif": "image/gif",
        "webp": "image/webp",
    }
    mime = mime_map.get(ext, "image/png")

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": VISION_SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime};base64,{b64}",
                                "detail": "high",
                            },
                        },
                        {
                            "type": "text",
                            "text": "What name do you see in this image? Return only the name.",
                        },
                    ],
                },
            ],
            max_tokens=300,
            temperature=0,
        )

        name = response.choices[0].message.content or ""
        name = name.strip()

        if not name:
            logger.warning("Vision LLM returned an empty name extraction")

        logger.info("Extracted name from image: %s (model: %s, cropped: %s)", name, model, cropped)
        return name

    except Exception as e:
        logger.error("Failed to extract name from image (model: %s): %s", model, e, exc_info=True)
        raise RuntimeError(f"Vision extraction failed: {e}") from e


# ---------------------------------------------------------------------------
# Public API: Extract name from audio
# ---------------------------------------------------------------------------

AUDIO_SYSTEM_PROMPT = (
    "You are a hotel concierge assistant. The user has spoken a guest's name. "
    "Transcribe the name exactly as spoken. Return ONLY the name as plain text, "
    "with no extra commentary."
)


def convert_to_wav(audio_bytes, original_format) -> bytes:
    from pydub import AudioSegment
    import io
    # Load the original audio bytes
    audio = AudioSegment.from_file(io.BytesIO(audio_bytes), format=original_format)
    
    # Force to Mono and 16,000Hz (16kHz)
    audio = audio.set_channels(1).set_frame_rate(16000)
    
    # Export cleanly to PCM WAV bytes without extra metadata
    wav_io = io.BytesIO()
    audio.export(wav_io, format="wav", codec="pcm_s16le")
    return wav_io.getvalue()

def _save_debug_wav(wav_bytes: bytes):
    """
    Save the converted WAV file locally for debugging.
    """
    try:
        output_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "audio_extracted")
        os.makedirs(output_dir, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}.wav"
        filepath = os.path.join(output_dir, filename)

        with open(filepath, "wb") as f:
            f.write(wav_bytes)

        logger.info("DEBUG: Saved WAV file to %s (size: %d bytes)", filepath, len(wav_bytes))
        return filepath
    except Exception as e:
        logger.error("Failed to save debug WAV file: %s", str(e))


def extract_name_from_audio(audio_bytes: bytes, audio_format: str = "webm", model_id: int | None = None) -> str:
    """
    Send an audio recording to the configured LLM and extract the guest name.

    Automatically converts any input audio format to WAV using ffmpeg before sending to the LLM.
    Also saves the WAV file locally for debugging.

    Args:
        audio_bytes: Raw audio data (any supported format).
        audio_format: Source file format extension (e.g., "webm", "mp3", "wav").
        model_id: Optional LLM model ID to use for extraction.

    Returns:
        Extracted name string.
    """
    client, model = _get_client_and_model(model_id)

    # Convert any audio format to WAV for reliable LLM processing
    wav_bytes = convert_to_wav(audio_bytes, audio_format)

    # Save the WAV file locally for debugging (before LLM call)
    filepath = _save_debug_wav(wav_bytes)
    if not filepath:
        raise Exception("Could not save audio file")
    
    b64 = base64.b64encode(wav_bytes).decode('utf-8')

    try:
        logger.info("Sending WAV audio to LLM - original format: %s, WAV size: %d bytes", audio_format, len(wav_bytes))
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Extract the name from this audio file."
                        },
                        {
                            "type": "input_audio",
                            "input_audio": {
                                "data": b64,
                                "format": "wav"
                            }
                        }
                    ]
                }
            ],
            max_tokens=512
        )

        name = response.choices[0].message.content or ""
        name = name.strip()

        if not name:
            logger.warning("Audio LLM returned an empty name extraction")

        logger.info("Extracted name from audio: %s (model: %s, original format: %s)", name, model, audio_format)
        return name

    except Exception as e:
        logger.error("Failed to extract name from audio (model: %s): %s", model, e, exc_info=True)
        raise RuntimeError(f"Audio extraction failed: {e}") from e