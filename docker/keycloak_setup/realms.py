#!/usr/bin/env python3
"""Realm management for Keycloak setup.

Handles creation and configuration of Keycloak realms.
"""

import logging

from keycloak_common import kc_request

from .config import REALMS

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Realm Creation
# ------------------------------------------------------------------


def create_realms(token: str) -> None:
    """Create realms: testing, production.

    Enables admin events and user events on each realm so that the
    role-sync service can poll the /admin/realms/{realm}/events endpoint.
    """
    logger.info("[2/8] Creating realms...")
    for realm in REALMS:
        resp = kc_request("GET", f"/admin/realms/{realm}", token)
        if resp.status_code == 200:
            logger.info("  ⏭ Realm %s already exists, ensuring events enabled", realm)
            _ensure_events_enabled(token, realm)
            continue
        resp = kc_request("POST", "/admin/realms", token, {
            "realm": realm,
            "enabled": True,
            "adminEventsEnabled": True,
            "eventsEnabled": True,
            "eventsExpiration": 43200,  # 12 hours
        })
        resp.raise_for_status()
        logger.info("  ✓ Realm %s created (events enabled)", realm)
    logger.info("")


def get_realm_config(token: str, realm: str) -> dict:
    """Fetch full realm configuration.

    Args:
        token: Keycloak admin token
        realm: Realm name

    Returns:
        Realm configuration dictionary
    """
    resp = kc_request("GET", f"/admin/realms/{realm}", token)
    resp.raise_for_status()
    return resp.json()


# ------------------------------------------------------------------
# Internal Helpers
# ------------------------------------------------------------------


def _ensure_events_enabled(token: str, realm: str) -> None:
    """Enable admin and user events on an existing realm.

    Keycloak 26 requires a full PUT (not PATCH) to update realm config.
    """
    config = get_realm_config(token, realm)

    if config.get("adminEventsEnabled") and config.get("eventsEnabled"):
        return  # Already enabled

    # Merge event settings into full config
    config["adminEventsEnabled"] = True
    config["eventsEnabled"] = True
    config.setdefault("eventsExpiration", 43200)

    # PUT full config back (Keycloak 26 does not support PATCH for realms)
    resp = kc_request("PUT", f"/admin/realms/{realm}", token, config)
    resp.raise_for_status()
    logger.info("    ✓ Events enabled for %s", realm)
