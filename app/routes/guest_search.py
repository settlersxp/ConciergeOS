#!/usr/bin/env python3
"""Guest search routes."""

from fastapi import APIRouter

from app.config import config_manager
from app.schemas import GuestSearchRequest, GuestSearchResponse
from app.services import query_guest_with_llm

router = APIRouter()


@router.post("/api/guest-search")
async def api_guest_search(body: GuestSearchRequest) -> GuestSearchResponse:
    """Query the LLM for all information about a given guest."""
    # Read cache setting from global config
    use_cache = config_manager.test_settings.response_cache_enabled
    
    llm_response, was_cached = query_guest_with_llm(
        body.customer_name,
        prompt_id=body.prompt_id,
        version=body.version,
        runtime_variables=body.runtime_variables if body.runtime_variables else None,
        use_cache=use_cache,
    )
    return GuestSearchResponse(
        query=body.customer_name,
        llm_response=llm_response,
        cached=was_cached,
    )
