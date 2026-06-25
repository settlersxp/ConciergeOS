#!/usr/bin/env python3
"""
FastAPI application for ConciergeOS reservation dashboard.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import (
    guest_search_router,
    performance_testing_router,
    reservations_router,
    settings_router,
)
from app.services.debug import debug_router

app = FastAPI(title="ConciergeOS")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Include route modules ────────────────────────────────────────────────────

app.include_router(reservations_router)
app.include_router(guest_search_router)
app.include_router(settings_router)
app.include_router(performance_testing_router)
app.include_router(debug_router, prefix="/api")