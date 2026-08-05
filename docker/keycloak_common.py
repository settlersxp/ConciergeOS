#!/usr/bin/env python3
"""Shared Keycloak helpers for ConciergeOS Docker scripts.

Provides a single source of truth for Keycloak API interactions used across
role_sync.py, keycloak_setup.py, and test fixtures.

Usage:
    from keycloak_common import authenticate, kc_request, fetch_all_roles
"""

import logging

import requests

from settings import settings

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Authentication
# ------------------------------------------------------------------


def authenticate() -> str:
    """Authenticate as admin to the master realm and return access token."""
    resp = requests.post(
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


# ------------------------------------------------------------------
# HTTP Helper
# ------------------------------------------------------------------


def kc_request(
    method: str,
    path: str,
    token: str,
    payload: dict | list | None = None,
    params: dict | None = None,
) -> requests.Response:
    """Make an authenticated request to the Keycloak Admin API.

    Args:
        method: HTTP method (GET, POST, PUT, DELETE, etc.)
        path: Path appended to KEYCLOAK_URL (e.g., "/admin/realms/{realm}/roles")
        token: Bearer token for Authorization header
        payload: JSON body (optional)
        params: URL query parameters (optional)

    Returns:
        requests.Response
    """
    return requests.request(
        method,
        f"{settings.KEYCLOAK_URL}{path}",
        json=payload,
        params=params,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
    )


# ------------------------------------------------------------------
# Realm Helpers
# ------------------------------------------------------------------


def fetch_all_roles(token: str, realm: str | None = None) -> set[str]:
    """Fetch all role names in the given realm (defaults to settings.KEYCLOAK_REALM)."""
    r = realm or settings.KEYCLOAK_REALM
    resp = kc_request("GET", f"/admin/realms/{r}/roles", token)
    resp.raise_for_status()
    return {role["name"] for role in resp.json()}


def fetch_all_roles_with_attrs(token: str, realm: str | None = None) -> dict[str, dict[str, list[str]]]:
    """Fetch all roles with their attributes from the given realm (defaults to settings.KEYCLOAK_REALM).

    Returns {role_name: {"paths": [...], "menus": [...], "message": [...]}}.
    Roles without attributes are included with empty lists.

    NOTE: Keycloak's list endpoint does NOT return role attributes (even with shortCodes=false).
    We must fetch each role individually via GET /roles/{name} to get attributes.
    """
    r = realm or settings.KEYCLOAK_REALM

    # Step 1: Get list of role names (list endpoint doesn't include attributes)
    resp = kc_request("GET", f"/admin/realms/{r}/roles", token)
    resp.raise_for_status()

    result: dict[str, dict[str, list[str]]] = {}
    # Step 2: Fetch each role individually to get attributes
    for role in resp.json():
        name = role["name"]
        detail_resp = kc_request("GET", f"/admin/realms/{r}/roles/{name}", token)
        if detail_resp.status_code == 200:
            attrs = detail_resp.json().get("attributes") or {}
        else:
            attrs = {}
        result[name] = {
            "paths": attrs.get("paths", []),
            "menus": attrs.get("menus", []),
            "message": attrs.get("message", []),
        }
    return result


def get_role_by_name(token: str, realm: str, role_name: str) -> dict | None:
    """Return role data dict if found, else None."""
    resp = kc_request("GET", f"/admin/realms/{realm}/roles/{role_name}", token)
    if resp.status_code == 200:
        return resp.json()
    return None


# ------------------------------------------------------------------
# Event Helpers
# ------------------------------------------------------------------


def has_events(
    events: list[dict],
    resource_types: set[str],
    operation_types: set[str],
) -> bool:
    """Check if any event matches the given resource and operation types."""
    for event in events:
        if (
            event.get("resourceType") in resource_types
            and event.get("operationType") in operation_types
        ):
            return True
    return False