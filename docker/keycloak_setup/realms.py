#!/usr/bin/env python3
"""Realm management for Keycloak setup.

Handles creation and configuration of Keycloak realms.
"""

from keycloak_common import kc_request

from .config import REALMS


# ------------------------------------------------------------------
# Realm Creation
# ------------------------------------------------------------------


def create_realms(token: str) -> None:
    """Create realms: testing, production.

    Enables admin events and user events on each realm so that the
    role-sync service can poll the /admin/realms/{realm}/events endpoint.
    """
    print("[2/8] Creating realms...")
    for realm in REALMS:
        resp = kc_request("GET", f"/admin/realms/{realm}", token)
        if resp.status_code == 200:
            print(f"  ⏭ Realm {realm} already exists, ensuring events enabled")
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
        print(f"  ✓ Realm {realm} created (events enabled)")
    print()


def _ensure_events_enabled(token: str, realm: str) -> None:
    """Enable admin and user events on an existing realm.

    Keycloak 26 requires a full PUT (not PATCH) to update realm config.
    """
    realm_url = f"/admin/realms/{realm}"

    # Read current realm config
    resp = kc_request("GET", realm_url, token)
    resp.raise_for_status()
    config = resp.json()

    admin_events = config.get("adminEventsEnabled", False)
    user_events = config.get("eventsEnabled", False)

    if admin_events and user_events:
        return  # Already enabled

    # Merge event settings into full config
    config["adminEventsEnabled"] = True
    config["eventsEnabled"] = True
    config.setdefault("eventsExpiration", 43200)

    # PUT full config back (Keycloak 26 does not support PATCH for realms)
    resp = kc_request("PUT", realm_url, token, config)
    resp.raise_for_status()
    print(f"    ✓ Events enabled for {realm}")