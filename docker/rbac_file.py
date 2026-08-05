"""Shared RBAC utilities for ConciergeOS.

This module provides common functions for parsing and loading RBAC route
definitions, used by both keycloak_setup and rbac_sync packages.

All functionality is delegated to the Pydantic models in rbac_models.py
for type safety and validation.

Usage:
    from rbac_file import load_role_definitions, load_role_descriptions
"""

import logging
from pathlib import Path

from rbac_models import RBACRoutes

logger = logging.getLogger(__name__)


def load_role_definitions(routes_path: Path | str) -> dict[str, dict]:
    """Load role definitions from RBAC routes file.

    Args:
        routes_path: Path to the RBAC routes JSON file

    Returns:
        Dictionary mapping role names to their full configuration:
        {role_name: {"paths": [...], "message": ""}}

    Raises:
        FileNotFoundError: If the routes file does not exist
    """
    routes = load_rbac_routes(routes_path)
    return routes.role_definitions()


def load_role_descriptions(routes_path: Path | str) -> dict[str, str]:
    """Load role names with human-readable descriptions from RBAC routes file.

    This is optimized for Keycloak role creation where only name and
    description are needed (not paths or other attributes).

    Args:
        routes_path: Path to the RBAC routes JSON file

    Returns:
        Dictionary mapping role names to descriptions:
        {role_name: description}

    Raises:
        FileNotFoundError: If the routes file does not exist

    Notes:
        The description is derived from the 'message' field by removing
        prefixes like "Access denied: " and suffixes like " role."
    """
    routes = load_rbac_routes(routes_path)
    return routes.role_descriptions()


def write_rbac_routes(
    routes_path: Path | str,
    roles_config: dict[str, dict],
) -> bool:
    """Write role configurations to an RBAC routes JSON file.

    Args:
        routes_path: Path to the JSON file to write
        roles_config: Dictionary {role_name: {"paths": [], "message": ""}}

    Returns:
        True if successful, False otherwise
    """
    from rbac_models import RBACRoute

    # Convert dict format to RBACRoute instances
    routes_list = [
        RBACRoute(role=role_name, **config)
        for role_name, config in roles_config.items()
    ]
    rbac_routes = RBACRoutes(routes=routes_list)
    return rbac_routes.to_json(routes_path)


def load_rbac_routes(routes_path: Path | str) -> RBACRoutes:
    """Load RBAC routes as a typed RBACRoutes model.

    Convenience function to load routes directly as a Pydantic model
    rather than a plain dictionary.

    Args:
        routes_path: Path to the RBAC routes JSON file

    Returns:
        RBACRoutes instance with all route data

    Raises:
        FileNotFoundError: If the routes file does not exist
    """
    path = Path(routes_path) if not isinstance(routes_path, Path) else routes_path

    if not path.exists():
        raise FileNotFoundError(f"RBAC routes file not found: {path}")

    logger.debug("Loading RBAC routes from JSON: %s", path)
    return RBACRoutes.from_json(path)