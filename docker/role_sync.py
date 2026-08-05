#!/usr/bin/env python3
"""Role Sync Service for ConciergeOS RBAC.

Polls Keycloak's Admin Events API to detect role-related changes,
then fetches role attributes (paths) from Keycloak and regenerates
Caddy deny rules, pushing them via the Caddy Admin API.

Also persists role attributes back to rbac_routes.json for documentation
and version control purposes.

Environment Variables (see docker/settings.py for defaults):
    KEYCLOAK_URL, KEYCLOAK_REALM, KEYCLOAK_ADMIN_USER, KEYCLOAK_ADMIN_PASSWORD
    CADDY_ADMIN_URL, SYNC_INTERVAL, VALKEY_URL, SESSION_COOKIE_NAME
"""

import logging
import sys

from rbac_sync import run_sync_service

# ------------------------------------------------------------------
# Logging Configuration
# ------------------------------------------------------------------
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)-8s] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S%z",
    stream=sys.stdout,
    force=True,
)
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(line_buffering=True)

logger = logging.getLogger("role_sync")


def main() -> None:
    """Main entry point for the role sync service."""
    run_sync_service()


if __name__ == "__main__":
    main()