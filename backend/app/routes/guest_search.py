#!/usr/bin/env python3
"""Guest search routes."""

import logging

from fastapi import APIRouter, Form, HTTPException, UploadFile

from app.schemas import GuestSearchRequest, GuestSearchResponse, NameExtractionResponse
from app.services import query_guest_with_llm
from app.services.guest_extraction import crop_image, extract_name_from_audio, extract_name_from_image

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/api/guest-search")
async def api_guest_search(body: GuestSearchRequest) -> GuestSearchResponse:
    """Query the LLM for all information about a given guest."""
    llm_response, was_cached = query_guest_with_llm(
        body.customer_name,
        prompt_id=body.prompt_id,
        version=body.version,
        runtime_variables=body.runtime_variables if body.runtime_variables else None,
    )
    return GuestSearchResponse(
        query=body.customer_name,
        llm_response=llm_response,
        cached=was_cached,
    )


@router.post("/api/guest-search/extract-name", response_model=NameExtractionResponse)
async def api_extract_name(
    file: UploadFile,
    crop_x: float = Form(0.0),
    crop_y: float = Form(0.0),
    crop_w: float = Form(0.0),
    crop_h: float = Form(0.0),
    model_id: int | None = Form(None),
) -> NameExtractionResponse:
    """
    Extract a guest name from a multimedia file (image or audio).

    For images:
    - If crop coordinates are provided (non-zero crop_w), the image is cropped first.

    For audio:
    - The entire file is sent to the audio-capable LLM.

    If model_id is provided, uses that specific model for extraction.
    Otherwise, falls back to the default configured model.
    """
    file_bytes = await file.read()
    content_type = file.content_type or ""

    # Log the model being used for extraction
    if model_id is not None:
        logger.info("Using model_id %s for extraction", model_id)

    # Detect audio vs image based on Content-Type header
    if "audio" in content_type:
        # Determine audio format from filename or Content-Type
        filename = file.filename or ""
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if not ext:
            # Fallback: try to guess from content_type
            ext = content_type.split("/")[-1].split(";")[0].strip()

        extracted_name = extract_name_from_audio(
            file_bytes, audio_format=ext or "webm", model_id=model_id
        )
        return NameExtractionResponse(extracted_name=extracted_name, source="audio")

    elif "image" in content_type:
        has_crop = crop_w > 0 and crop_h > 0

        if has_crop:
            image_bytes = crop_image(file_bytes, crop_x, crop_y, crop_w, crop_h)
        else:
            image_bytes = file_bytes

        extracted_name = extract_name_from_image(
            image_bytes, cropped=has_crop, model_id=model_id
        )
        return NameExtractionResponse(extracted_name=extracted_name, source="image")

    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {content_type}. Expected an image or audio file.",
        )
