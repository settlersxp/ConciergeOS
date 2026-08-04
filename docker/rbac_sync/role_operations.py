"""RBAC Role Operations — Adapter Module.

This module is a thin adapter that bridges `rbac_sync` to `keycloak_setup.roles`.

Architecture Note:
    All Keycloak CRUD operations are delegated to `keycloak_setup.roles`.
    This module only provides the `sync_all_roles()` convenience function
    which parses a routes file and delegates each role to
    `keycloak_setup.roles.sync_role_to_keycloak()`.

    Direct role operations (create, update, delete, list) should go through
    `keycloak_setup.roles` directly. This module is re-exported from
    `rbac_sync.__init__` for backward compatibility.
"""

import logging
from pathlib import Path

from keycloak_common import authenticate
from keycloak_setup.roles import sync_role_to_keycloak
from settings import settings

logger = logging.getLogger(__name__)


def sync_all_roles(routes_path: Path, create_if_missing: bool = True) -> dict[str, str]:
    """Sync all roles from a routes file (JSON) to Keycloak.

    Parses the routes file, then delegates each role to
    `keycloak_setup.roles.sync_role_to_keycloak()`.

    Args:
        routes_path: Path to the RBAC routes JSON file
        create_if_missing: Whether to create roles that don't exist in Keycloak

    Returns:
        Dictionary mapping role names to their action status
        ("created", "updated", "skipped", or "failed")
    """
    from .routes_persistence import parse_rbac_routes

    # Parse routes file
    logger.info("Parsing RBAC routes from: %s", routes_path)
    roles_config = parse_rbac_routes(routes_path)
    logger.info("Found %d roles to sync", len(roles_config))

    # Authenticate
    logger.info("Authenticating to Keycloak at %s", settings.KEYCLOAK_URL)
    token = authenticate()
    logger.info("Authenticated successfully")

    # Sync each role via keycloak_setup.roles
    results = {}
    realm = settings.KEYCLOAK_REALM

    for role_name, config in roles_config.items():
        logger.info("Processing role: %s", role_name)
        success, action = sync_role_to_keycloak(
            token, realm, role_name, config, create_if_missing
        )
        results[role_name] = action

        if not success:
            logger.warning("  %s: %s", action, role_name)
        else:
            logger.info("  %s: %s", action, role_name)

    return results
