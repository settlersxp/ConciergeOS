#!/usr/bin/env python3
"""Authentication helpers for Keycloak.

Provides a single source of truth for Keycloak admin authentication,
extracted from keycloak_common so tests can import from keycloak_setup.
"""

import requests

from settings import settings


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