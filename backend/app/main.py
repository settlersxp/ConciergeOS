#!/usr/bin/env python3
"""
FastAPI application for ConciergeOS reservation dashboard.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.routes import (
    guest_search_router,
    models_router,
    performance_testing_router,
    prompts_router,
    reservations_router,
    settings_router,
)
from app.routes.prompt_groups import router as prompt_groups_router
from app.services.debug import debug_router
from app.services.http_cache_middleware import HttpCacheMiddleware
from app.services.prompt_scheduler import PromptScheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start up and shut down the prompt group scheduler."""
    scheduler = PromptScheduler.get()
    scheduler.start()
    yield
    scheduler.shutdown()


app = FastAPI(title="ConciergeOS", lifespan=lifespan)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Custom handler that safely encodes binary data in validation errors.

    The default handler crashes with UnicodeDecodeError when multipart/form-data
    includes binary file uploads that fail validation.
    """
    sanitized = []
    for error in exc.errors():
        sanitized_error = dict(error)
        ctx = sanitized_error.get("ctx")
        if isinstance(ctx, dict):
            # Replace any binary values in the context with a safe placeholder
            for key, value in ctx.items():
                if isinstance(value, bytes):
                    ctx[key] = f"<binary data ({len(value)} bytes)>"
        sanitized.append(sanitized_error)

    return JSONResponse(status_code=422, content={"detail": sanitized})

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# HTTP response cache middleware — caches GET responses by URI + query params
app.add_middleware(HttpCacheMiddleware, ttl=3600)

# ── Include route modules ────────────────────────────────────────────────────

app.include_router(reservations_router)
app.include_router(guest_search_router)
app.include_router(settings_router)
app.include_router(performance_testing_router)
app.include_router(prompts_router)
app.include_router(models_router)
app.include_router(prompt_groups_router)
app.include_router(debug_router, prefix="/api")
