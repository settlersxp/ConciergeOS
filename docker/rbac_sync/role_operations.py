"""Keycloak Role Operations module.

Handles creating, updating, and syncing roles to Keycloak with
their associated path and message attributes.

This module reuses functionality from keycloak_setup.roles for role
management, providing a thin wrapper for rbac_sync-specific operations.
"""

import logging

from keycloak_common import authenticate
from keycloak_setup.roles import (
    sync_role_to_keycloak,
)
from settings import settings

logger = logging.getLogger(__name__)


def sync_all_roles(yaml_path, create_if_missing: bool = True) -> dict[str, str]:
    """Sync all roles from YAML to Keycloak.

    Args:
        yaml_path: Path to the YAML file
        create_if_missing: Whether to create roles that don't exist

    Returns:
        Dictionary mapping role names to their action status
    """
    from .routes_persistence import parse_rbac_routes

    # Parse YAML
    logger.info("Parsing RBAC routes from: %s", yaml_path)
    roles_config = parse_rbac_routes(yaml_path)
    logger.info("Found %d roles to sync", len(roles_config))

    # Authenticate
    logger.info("Authenticating to Keycloak at %s", settings.KEYCLOAK_URL)
    token = authenticate()
    logger.info("Authenticated successfully")

    # Sync each role
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


def print_summary(results: dict[str, str]) -> None:
    """print a summary table of all operations."""
    logger.info("\n" + "=" * 60)
    logger.info("SYNC SUMMARY")
    logger.info("=" * 60)

    # Count by action
    created = sum(1 for v in results.values() if v == "created")
    updated = sum(1 for v in results.values() if v == "updated")
    skipped = sum(1 for v in results.values() if v == "skipped")
    failed = sum(1 for v in results.values() if v == "failed")

    logger.info(f"{'Action':<12} {'Count':>6}")
    logger.info("-" * 20)
    logger.info(f"{'Created':<12} {created:>6}")
    logger.info(f"{'Updated':<12} {updated:>6}")
    logger.info(f"{'Skipped':<12} {skipped:>6}")
    logger.info(f"{'Failed':<12} {failed:>6}")
    logger.info("-" * 20)
    logger.info(f"{'Total':<12} {len(results):>6}")

    # Detailed table
    logger.info("\n" + "-" * 60)
    logger.info(f"{'Role Name':<40} {'Action':<10}")
    logger.info("-" * 60)

    for role_name, action in sorted(results.items()):
        logger.info(f"{role_name:<40} {action:<10}")

    logger.info("=" * 60)
