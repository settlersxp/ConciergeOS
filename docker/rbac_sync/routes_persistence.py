"""Persistence module for RBAC routes.

Handles reading and writing of RBAC routes files (JSON).
This module uses the Pydantic RBACRoutes model for type safety and validation.
"""

import logging
from pathlib import Path

from rbac_models import RBACRoute, RBACRoutes
from rbac_file import load_rbac_routes, load_role_definitions, write_rbac_routes

logger = logging.getLogger(__name__)


# Backward compatibility aliases
parse_rbac_routes = load_role_definitions


def load_existing_rbac_routes(routes_path: Path) -> dict[str, dict]:
    """Load existing RBAC routes and return {role_name: {paths, message}}.

    Args:
        routes_path: Path to the routes JSON file

    Returns:
        Dictionary mapping role names to their configuration
    """
    if not routes_path.exists():
        logger.info("Routes file not found: %s - will create new file", routes_path)
        return {}

    try:
        routes = load_rbac_routes(routes_path)
        return routes.role_definitions()
    except Exception as e:
        logger.error("Failed to read routes file: %s", e)
        return {}


def convert_keycloak_attrs_to_route_format(roles_with_attrs: dict[str, dict[str, list[str]]]) -> dict[str, dict]:
    """Convert Keycloak role attributes to route-compatible format.

    Args:
        roles_with_attrs: Dictionary from fetch_all_roles_with_attrs()

    Returns:
        Dictionary in compatible format {role_name: {paths, message}}
    """
    rbac_routes = RBACRoutes.from_keycloak_attrs(roles_with_attrs)
    return rbac_routes.role_definitions()


def write_rbac_routes_file(routes_path: Path, roles_config: dict[str, dict]) -> bool:
    """Write roles configuration to an RBAC routes JSON file.

    Args:
        routes_path: Path to the routes JSON file
        roles_config: Dictionary {role_name: {paths: [], message: ''}}

    Returns:
        True if successful, False otherwise
    """
    return write_rbac_routes(routes_path, roles_config)


def sync_rbac_routes(token: str, routes_path: Path) -> bool:
    """Fetch roles from Keycloak and write to an RBAC routes file.

    Args:
        token: Keycloak admin token
        routes_path: Path to the routes JSON file to write

    Returns:
        True if successful, False otherwise
    """
    from keycloak_common import fetch_all_roles_with_attrs

    logger.info("Syncing roles from Keycloak to routes file: %s", routes_path)

    roles_with_attrs = fetch_all_roles_with_attrs(token)
    logger.info("Fetched %d role(s) from Keycloak", len(roles_with_attrs))

    # Filter to only roles with paths defined
    roles_with_paths = {
        name: attrs for name, attrs in roles_with_attrs.items()
        if attrs.get("paths")
    }
    logger.info("Found %d role(s) with path attributes", len(roles_with_paths))

    if not roles_with_paths:
        logger.info("No roles with paths found - routes file will not be updated")
        return True

    # Convert to format and write
    roles_config = convert_keycloak_attrs_to_route_format(roles_with_paths)
    return write_rbac_routes_file(routes_path, roles_config)


