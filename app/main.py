#!/usr/bin/env python3
"""
FastAPI application for ConciergeOS reservation dashboard.
"""

from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates

from app.schemas import GuestSearchRequest, GuestSearchResponse
from app.services import get_reservations_summary, query_guest_with_llm
from app.services.debug import debug_router

app = FastAPI(title="ConciergeOS")

templates = Jinja2Templates(directory="app/templates")
app.include_router(debug_router, prefix="/api")


@app.get("/")
async def index(request: Request):
    """Serve the main reservations dashboard page."""
    summary = get_reservations_summary()
    # model_dump() converts Pydantic schemas to plain dicts for Jinja2 rendering
    context = {
        "request": request,
        "rooms": summary.model_dump(mode="json")["rooms"],
        "errors": [e.model_dump(mode="json") for e in summary.errors],
    }
    return templates.TemplateResponse(request, "reservations.html", context)


@app.get("/api/reservations")
async def api_reservations():
    """JSON endpoint returning reservations grouped by room and errors."""
    summary = get_reservations_summary()
    return summary.model_dump(mode="json")


@app.get("/guest-search")
async def guest_search_page(request: Request):
    """Serve the guest search page."""
    return templates.TemplateResponse(request, "guest_search.html", {
        "request": request,
    })


@app.post("/api/guest-search")
async def api_guest_search(body: GuestSearchRequest) -> GuestSearchResponse:
    """Query the LLM for all information about a given guest."""
    llm_response = query_guest_with_llm(body.customer_name)
    return GuestSearchResponse(
        query=body.customer_name,
        llm_response=llm_response,
    )