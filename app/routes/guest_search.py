#!/usr/bin/env python3
"""Guest search routes."""

from fastapi import APIRouter

from app.schemas import GuestSearchRequest, GuestSearchResponse
from app.services import query_guest_with_llm

router = APIRouter()


@router.post("/api/guest-search")
async def api_guest_search(body: GuestSearchRequest) -> GuestSearchResponse:
    """Query the LLM for all information about a given guest."""
    llm_response, was_cached = query_guest_with_llm(
        body.customer_name,
        prompt_id=body.prompt_id,
        version=body.version,
    )
    return GuestSearchResponse(
        query=body.customer_name,
        llm_response=llm_response,
        cached=was_cached,
    )
