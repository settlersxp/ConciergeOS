#!/usr/bin/env python3
"""Client management for Keycloak setup.

Handles creation and configuration of Keycloak clients.
"""

import logging

import requests

from keycloak_common import kc_request
from settings import settings

# Import config values at module level
from .config import (
    APP_DOMAIN,
    CLIENT_API_ID,
    CLIENT_ID,
    DOMAIN_WILD_CARD,
    LOCAL_REDIRECT_URI,
    LOCAL_WEB_ORIGIN,
    OIDC_APP1_REDIRECT_URI,
    OIDC_APP2_REDIRECT_URI,
    POST_LOGOUT_URI,
    REALMS,
)

logger = logging.getLogger(__name__)


# Global secret storage (updated during client creation)
_actual_client_secret = ""
_client_api_secret = ""


# ------------------------------------------------------------------
# Client Creation
# ------------------------------------------------------------------


def _create_client_in_realm(
    token: str,
    realm: str,
    client_id: str,
    /,
    service_account: bool = False,
    redirect_uris: list[str] | None = None,
    web_origins: list[str] | None = None,
    post_logout_uris: list[str] | None = None,
) -> tuple[str, str]:
    """Create (or update) a Keycloak client. Returns (client_uuid, secret)."""

    # Check if client exists
    resp = kc_request("GET", f"/admin/realms/{realm}/clients", token)
    resp.raise_for_status()
    clients = resp.json()
    match = [c for c in clients if c["clientId"] == client_id]

    if match:
        client_uuid = match[0]["id"]
        logger.info("    ⏭ Client %s already exists in %s, updating secret...", client_id, realm)
    else:
        payload: dict = {
            "clientId": client_id,
            "enabled": True,
            "publicClient": False,
            "standardFlowEnabled": not service_account,
            "implicitFlowEnabled": False,
            "directAccessGrantsEnabled": True,
            "serviceAccountsEnabled": service_account,
        }
        if redirect_uris:
            payload["redirectUris"] = redirect_uris
        if web_origins:
            payload["webOrigins"] = web_origins
        if post_logout_uris:
            payload["attributes"] = {
                "post.logout.redirect.uris": "##".join(post_logout_uris),
            }
        if service_account:
            payload["attributes"] = {
                **(payload.get("attributes") or {}),
                "client_credentials.use_refresh_token": "false",
            }

        resp = kc_request("POST", f"/admin/realms/{realm}/clients", token, payload)
        resp.raise_for_status()
        client_uuid = resp.headers.get("Location", "").split("/")[-1]
        if not client_uuid:
            resp = kc_request("GET", f"/admin/realms/{realm}/clients", token)
            resp.raise_for_status()
            match = [c for c in resp.json() if c["clientId"] == client_id]
            client_uuid = match[0]["id"]

    # Regenerate secret
    resp = requests.post(
        f"{settings.KEYCLOAK_URL}/admin/realms/{realm}/clients/{client_uuid}/client-secret",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
    )
    resp.raise_for_status()
    secret_value = resp.json().get("value", "")
    logger.info("    ✓ Client %s in %s (secret: %s)", client_id, realm, secret_value)
    return client_uuid, secret_value


def create_client(token: str, realm: str) -> str:
    """Create the conciergeos client in a realm. Returns the client UUID.

    Keycloak 26 always generates a random secret. After creation, the actual
    secret is stored in _actual_client_secret and printed to stdout so the
    caller can set the OAUTH2_PROXY_CLIENT_SECRET environment variable.
    """
    global _actual_client_secret

    client_uuid, secret_value = _create_client_in_realm(
        token,
        realm,
        CLIENT_ID,
        service_account=False,
        redirect_uris=[
            OIDC_APP1_REDIRECT_URI,
            OIDC_APP2_REDIRECT_URI,
            DOMAIN_WILD_CARD,
            LOCAL_REDIRECT_URI,
        ],
        web_origins=[APP_DOMAIN, LOCAL_WEB_ORIGIN],
        post_logout_uris=[POST_LOGOUT_URI, DOMAIN_WILD_CARD, LOCAL_REDIRECT_URI],
    )
    _actual_client_secret = secret_value
    return client_uuid


def create_client_api(token: str, realm: str) -> tuple[str, str]:
    """Create the client-api service client (Client Credentials Grant).

    Returns (client_uuid, secret).
    """
    global _client_api_secret

    client_uuid, secret_value = _create_client_in_realm(
        token,
        realm,
        CLIENT_API_ID,
        service_account=True,
    )
    _client_api_secret = secret_value
    return client_uuid, secret_value


def create_all_clients(token: str) -> dict[str, str]:
    """Create clients in all realms. Returns {realm: client_uuid}."""
    logger.info("[6/8] Creating clients in realms...")
    client_uuids: dict[str, str] = {}

    for realm in REALMS:
        client_uuids[realm] = create_client(token, realm)
    logger.info("")
    return client_uuids


def create_all_client_apis(token: str) -> dict[str, tuple[str, str]]:
    """Create the client-api service client in all realms.

    Returns {realm: (client_uuid, secret)}.
    """
    logger.info("[6b/8] Creating client-api service client in realms...")
    results: dict[str, tuple[str, str]] = {}

    for realm in REALMS:
        logger.info("  Realm: %s", realm)
        results[realm] = create_client_api(token, realm)
    logger.info("")
    return results


# Accessor functions for secrets
def get_actual_client_secret() -> str:
    """Get the concierge client secret."""
    return _actual_client_secret


def get_client_api_secret() -> str:
    """Get the client-api service secret."""
    return _client_api_secret