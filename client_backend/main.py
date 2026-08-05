"""FastAPI application for the client backend service.

This is the main entry point. All routes are prefixed with ``/client-api``
so Caddy can distinguish them from the main backend's ``/api`` routes.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Header, Request
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
# Helper: Extract role names from X-Forwarded-Groups header
# ---------------------------------------------------------------------------

def _extract_roles(x_forwarded_groups: str | None) -> list[str]:
    """Parse role names from oauth2-proxy X-Forwarded-Groups header.

    Format: "role:reservations:view,role:settings:view"
    """
    if not x_forwarded_groups:
        return []
    roles: list[str] = []
    for group in x_forwarded_groups.split(","):
        group = group.strip()
        if group.startswith("role:"):
            roles.append(group[5:])
    return roles


# ---------------------------------------------------------------------------
# Helper: Keycloak Admin API
# ---------------------------------------------------------------------------

def _authenticate_admin() -> str:
    """Authenticate as admin to the master realm and return access token."""
    import requests as sync_requests
    resp = sync_requests.post(
        f"{settings.KEYCLOAK_URL}/realms/master/protocol/openid-connect/token",
        data={
            "grant_type": "password",
            "client_id": "admin-cli",
            "username": settings.KEYCLOAK_ADMIN_USER,
            "password": settings.KEYCLOAK_ADMIN_PASSWORD,
        },
    )
    resp.raise_for_status()
    token = resp.json().get("access_token")
    if not token:
        raise RuntimeError("Failed to authenticate to Keycloak admin.")
    return token


def _fetch_roles_with_attrs(token: str) -> dict[str, dict[str, list[str]]]:
    """Fetch all roles with their attributes from Keycloak Admin API.

    NOTE: Keycloak's list endpoint does NOT return role attributes.
    We must fetch each role individually via GET /roles/{name}.
    """
    import requests as sync_requests
    headers = {"Authorization": f"Bearer {token}"}
    base = f"{settings.KEYCLOAK_URL}/admin/realms/{settings.KEYCLOAK_REALM}"

    # Step 1: Get list of role names
    resp = sync_requests.get(f"{base}/roles", headers=headers)
    resp.raise_for_status()

    result: dict[str, dict[str, list[str]]] = {}
    # Step 2: Fetch each role individually to get attributes
    for role in resp.json():
        name = role["name"]
        detail = sync_requests.get(f"{base}/roles/{name}", headers=headers)
        if detail.status_code == 200:
            attrs = detail.json().get("attributes") or {}
        else:
            attrs = {}
        result[name] = {
            "paths": attrs.get("paths", []),
            "menus": attrs.get("menus", []),
        }
    return result


def _get_menus_for_roles(
    role_names: list[str],
    roles_with_attrs: dict[str, dict[str, list[str]]],
) -> list[str]:
    """Aggregate menu items for a set of role names."""
    menus: set[str] = set()
    for role_name in role_names:
        attrs = roles_with_attrs.get(role_name, {})
        for menu in attrs.get("menus", []):
            menus.add(menu)
    # full-access role gets all menus from all roles
    if "full-access" in role_names:
        for attrs in roles_with_attrs.values():
            for menu in attrs.get("menus", []):
                menus.add(menu)
    return sorted(menus)


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
    await keycloak_client.get_access_token()
    return keycloak_client.get_token_info()


@app.post("/client-api/refresh-token")
async def refresh_token():
    """Force a token refresh."""
    token = await keycloak_client.refresh_token()
    return {
        "status": "refreshed",
        "expires_in": token.expires_in,
        "scope": token.scope,
    }


# ---------------------------------------------------------------------------
# User Info Endpoint (RBAC menus)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Token Claims Endpoint (Debug — JWT claims from Keycloak via oauth2-proxy)
# ---------------------------------------------------------------------------

@app.get("/client-api/me/token-claims")
async def token_claims(
    request: Request,
    x_forwarded_email: str | None = Header(None),
    x_forwarded_user: str | None = Header(None),
    x_forwarded_preferred_username: str | None = Header(None),
    x_forwarded_name: str | None = Header(None),
    x_forwarded_groups: str | None = Header(None),
    x_forwarded_access_token: str | None = Header(None),
):
    """Return the JWT-like claims forwarded by oauth2-proxy.

    oauth2-proxy extracts claims from the Keycloak JWT and forwards them
    as HTTP headers. This endpoint collects those headers so the frontend
    can display them in the debug panel to verify Keycloak token contents.
    """
    claims: dict = {}

    if x_forwarded_email:
        claims["email"] = x_forwarded_email
    if x_forwarded_user:
        claims["sub"] = x_forwarded_user
    if x_forwarded_preferred_username:
        claims["preferred_username"] = x_forwarded_preferred_username
    if x_forwarded_name:
        claims["name"] = x_forwarded_name

    # Parse roles from X-Forwarded-Groups (format: "role:xxx,role:yyy")
    if x_forwarded_groups:
        roles = []
        for group in x_forwarded_groups.split(","):
            group = group.strip()
            if group.startswith("role:"):
                roles.append(group[5:])
            else:
                roles.append(group)
        claims["realm_access"] = {"roles": roles}

    # Also expose the raw header values for debugging
    raw_headers: dict = {}
    for header_name, header_value in [
        ("X-Forwarded-Email", x_forwarded_email),
        ("X-Forwarded-User", x_forwarded_user),
        ("X-Forwarded-Preferred-Username", x_forwarded_preferred_username),
        ("X-Forwarded-Name", x_forwarded_name),
        ("X-Forwarded-Groups", x_forwarded_groups),
    ]:
        if header_value is not None:
            raw_headers[header_name] = header_value

    return {
        "claims": claims,
        "raw_headers": raw_headers,
    }


@app.get("/client-api/me")
async def me(
    request: Request,
    x_forwarded_groups: str | None = Header(None),
):
    """Return the current user's roles and accessible menu items.

    Reads role names from the X-Forwarded-Groups header (set by oauth2-proxy),
    then queries the Keycloak Admin API to fetch role attributes (paths, menus),
    and returns the aggregated menu items the user has access to.
    """
    roles = _extract_roles(x_forwarded_groups)

    try:
        admin_token = _authenticate_admin()
        roles_with_attrs = _fetch_roles_with_attrs(admin_token)
        menus = _get_menus_for_roles(roles, roles_with_attrs)
    except Exception as e:
        logger.error("Failed to fetch role attributes from Keycloak: %s", e, exc_info=True)
        # Return roles but empty menus on failure
        return {
            "roles": roles,
            "menus": [],
            "error": "Failed to fetch role attributes from Keycloak",
        }

    return {
        "roles": roles,
        "menus": menus,
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
    """Generic POST proxy to any backend endpoint."""
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