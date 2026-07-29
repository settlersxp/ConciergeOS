"""FastAPI application for the client backend service.

This is the main entry point. All routes are prefixed with ``/client-api``
so Caddy can distinguish them from the main backend's ``/api`` routes.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import settings
from .keycloak_client import keycloak_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Client Backend",
    description=(
        "Dummy backend service that demonstrates service-to-service "
        "authentication via Keycloak (Client Credentials Grant)."
    ),
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Health & Token Endpoints
# ---------------------------------------------------------------------------


@app.get("/client-api/health")
async def health():
    """Simple health check."""
    return {
        "service": "client-backend",
        "status": "ok",
        "keycloak_url": settings.KEYCLOAK_URL,
        "keycloak_realm": settings.KEYCLOAK_REALM,
        "backend_url": settings.BACKEND_URL,
        "client_id": settings.CLIENT_API_CLIENT_ID,
    }


@app.get("/client-api/token-info")
async def token_info():
    """Inspect the current OAuth2 token.

    Demonstrates how the service acquires and caches a token from Keycloak
    using the Client Credentials Grant.  The decoded JWT payload shows the
    ``azp`` (authorized party), ``client_id``, and ``realm_access.roles``.
    """
    # This will fetch a new token if none is cached or if it is expired
    await keycloak_client.get_access_token()
    return keycloak_client.get_token_info()


@app.post("/client-api/refresh-token")
async def refresh_token():
    """Force a token refresh.

    Demonstrates that the service can re-authenticate at any time by
    presenting its client_id + client_secret to Keycloak.
    """
    token = await keycloak_client.refresh_token()
    return {
        "status": "refreshed",
        "expires_in": token.expires_in,
        "scope": token.scope,
    }

# ---------------------------------------------------------------------------
# Proxy: Call the Main Backend
# ---------------------------------------------------------------------------


@app.get("/client-api/backend/health")
async def backend_health():
    """Call the main backend's root endpoint (no auth required on the backend)."""
    try:
        resp = await keycloak_client.call_backend("GET", "/")
        return {
            "source": "client-backend -> backend",
            "status_code": resp.status_code,
            "data": resp.json(),
        }
    except Exception as exc:
        return JSONResponse(
            status_code=502,
            content={"error": str(exc), "target": "backend /"},
        )


@app.get("/client-api/backend/models")
async def backend_models():
    """Call the main backend's /api/models endpoint with a Bearer token."""
    try:
        resp = await keycloak_client.call_backend("GET", "/api/models")
        return {
            "source": "client-backend -> backend",
            "endpoint": "/api/models",
            "status_code": resp.status_code,
            "data": resp.json(),
        }
    except Exception as exc:
        return JSONResponse(
            status_code=502,
            content={"error": str(exc), "target": "backend /api/models"},
        )


@app.get("/client-api/backend/settings")
async def backend_settings():
    """Call the main backend's /api/settings endpoint with a Bearer token."""
    try:
        resp = await keycloak_client.call_backend("GET", "/api/settings")
        return {
            "source": "client-backend -> backend",
            "endpoint": "/api/settings",
            "status_code": resp.status_code,
            "data": resp.json(),
        }
    except Exception as exc:
        return JSONResponse(
            status_code=502,
            content={"error": str(exc), "target": "backend /api/settings"},
        )


@app.post("/client-api/backend/post/{path:path}")
async def backend_post(path: str, body: dict | None = None):
    """Generic POST proxy to any backend endpoint.

    Demonstrates that the service can forward authenticated requests to
    any endpoint on the main backend.
    """
    target = f"/{path}"
    try:
        resp = await keycloak_client.call_backend(
            "POST", target, json_body=body or {}
        )
        return {
            "source": "client-backend -> backend",
            "method": "POST",
            "endpoint": target,
            "status_code": resp.status_code,
            "data": resp.json(),
        }
    except Exception as exc:
        return JSONResponse(
            status_code=502,
            content={"error": str(exc), "target": target},
        )

