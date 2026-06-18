#!/usr/bin/env python3
"""
FastAPI application for ConciergeOS reservation dashboard.
"""

from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates

from app.services import get_reservations_summary

app = FastAPI(title="ConciergeOS")

templates = Jinja2Templates(directory="app/templates")


@app.get("/")
async def index(request: Request):
    """Serve the main reservations dashboard page."""
    data = get_reservations_summary()
    context = {
        "request": request,
        "rooms": data["rooms"],
        "errors": data["errors"],
    }
    return templates.TemplateResponse(request, "reservations.html", context)


@app.get("/api/reservations")
async def api_reservations():
    """JSON endpoint returning reservations grouped by room and errors."""
    return get_reservations_summary()