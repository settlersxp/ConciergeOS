#!/usr/bin/env python3
"""Role management for Keycloak setup.

Handles creation of realm roles and composite roles.

This module also provides role synchronization functionality that can be
reused by the rbac_sync package for runtime role management.
"""

import logging

import requests

from keycloak_common import get_role_by_name, kc_request

from .config import REALMS, get_composite_roles, get_roles

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Role Listing
# ------------------------------------------------------------------


def list_roles(token: str, realm: str) -> set[str]:
    """Fetch all role names in the given realm.

    Args:
        token: Keycloak admin token
        realm: Realm name

    Returns:
        Set of role name strings
    """
    resp = kc_request("GET", f"/admin/realms/{realm}/roles", token)
    resp.raise_for_status()
    return {role["name"] for role in resp.json()}


def list_roles_with_attrs(token: str, realm: str) -> dict[str, dict[str, list[str]]]:
    """Fetch all roles with their attributes from the given realm.

    Returns {role_name: {"paths": [...], "menus": [...]}}.
    Roles without attributes are included with empty lists.

    Args:
        token: Keycloak admin token
        realm: Realm name

    Returns:
        Dictionary mapping role names to their attributes
    """
    resp = kc_request("GET", f"/admin/realms/{realm}/roles", token)
    resp.raise_for_status()
    result: dict[str, dict[str, list[str]]] = {}
    for role in resp.json():
        name = role["name"]
        attrs = role.get("attributes") or {}
        result[name] = {
            "paths": attrs.get("paths", []),
            "menus": attrs.get("menus", []),
        }
    return result


def upsert_role_with_attributes(
    token: str, realm: str, role_name: str, paths: list[str], menus: list[str]
) -> None:
    """Create or update a role with paths and menus attributes.

    If the role exists, updates its attributes. If not, creates it first.

    Args:
        token: Keycloak admin token
        realm: Realm name
        role_name: Name of the role
        paths: List of path patterns
        menus: List of menu identifiers
    """
    # Check if role exists
    resp = kc_request("GET", f"/admin/realms/{realm}/roles/{role_name}", token)
    if resp.status_code != 200:
        # Create role
        resp = kc_request(
            "POST",
            f"/admin/realms/{realm}/roles",
            token,
            {"name": role_name, "description": f"Test role: {role_name}"},
        )
        resp.raise_for_status()

    # Fetch current role data and set attributes
    resp = kc_request("GET", f"/admin/realms/{realm}/roles/{role_name}", token)
    resp.raise_for_status()
    role_data = resp.json()
    role_data["attributes"] = {
        "paths": paths,
        "menus": menus,
    }
    resp = kc_request(
        "PUT",
        f"/admin/realms/{realm}/roles/{role_name}",
        token,
        role_data,
    )
    resp.raise_for_status()


def delete_role(token: str, realm: str, role_name: str) -> requests.Response:
    """Delete a role by name. Returns the raw Response.

    Args:
        token: Keycloak admin token
        realm: Realm name
        role_name: Name of the role to delete

    Returns:
        Raw requests.Response object
    """
    return kc_request(
        "DELETE",
        f"/admin/realms/{realm}/roles/{role_name}",
        token,
    )


# ------------------------------------------------------------------
# Role Creation
# ------------------------------------------------------------------


def create_role(token: str, realm: str, role_name: str, description: str = "") -> str:
    """Create a realm role. Returns the role name (Keycloak roles are identified by name)."""
    # Check if role exists using keycloak_common helper
    role = get_role_by_name(token, realm, role_name)
    if role:
        logger.info("    ⏭ Role %s already exists", role_name)
        return role_name

    resp = kc_request(
        "POST",
        f"/admin/realms/{realm}/roles",
        token,
        {
            "name": role_name,
            "description": description,
        },
    )
    if resp.status_code in (201, 204):
        logger.info("    ✓ Role %s created", role_name)
    else:
        logger.warning("    ⚠ Failed to create role %s: %s %s", role_name, resp.status_code, resp.text)
    return role_name


def create_composite_role(
    token: str,
    realm: str,
    role_name: str,
    composite_role_names: list[str],
) -> str:
    """Create a composite role that inherits from the given composite roles."""
    # First create the role itself
    create_role(token, realm, role_name, f"Composite role: {', '.join(composite_role_names)}")

    # Get the composite role IDs using keycloak_common helper
    composite_role_ids = []
    for comp_name in composite_role_names:
        role = get_role_by_name(token, realm, comp_name)
        if role:
            composite_role_ids.append(role.get("id"))

    # Set composites
    if composite_role_ids:
        resp = kc_request(
            "PUT",
            f"/admin/realms/{realm}/roles/{role_name}/composites",
            token,
            composite_role_ids,
        )
        # PUT returns 204 No Content on success
        if resp.status_code in (200, 204):
            logger.info("    ✓ Composite role %s configured with %d sub-roles", role_name, len(composite_role_ids))
        else:
            logger.warning("    ⚠ Failed to configure composites for %s: %s", role_name, resp.status_code)

    return role_name


def create_all_roles(token: str) -> dict[str, dict[str, str]]:
    """Create roles in all realms. Returns {realm: {role_name: role_data}}."""
    logger.info("[3/8] Creating roles in realms...")
    role_data: dict[str, dict[str, str]] = {}

    for realm in REALMS:
        logger.info("  Realm: %s", realm)
        role_data[realm] = {}

        # Create granular roles
        for role_name, description in get_roles().items():
            role_data[realm][role_name] = create_role(
                token, realm, role_name, description
            )

        # Create composite roles
        for composite_name, sub_roles in get_composite_roles().items():
            role_data[realm][composite_name] = create_composite_role(
                token, realm, composite_name, sub_roles
            )

    logger.info("")
    return role_data


# ------------------------------------------------------------------
# Role Operations with Attributes (for RBAC Sync)
# ------------------------------------------------------------------
# These functions are also used by rbac_sync package for runtime role management.


def create_role_with_attributes(
    token: str, realm: str, role_name: str, paths: list[str], message: str
) -> bool:
    """Create a new role with paths and message attributes.

    Args:
        token: Admin access token
        realm: Realm name
        role_name: Name of the role to create
        paths: List of path patterns
        message: Custom 403 message

    Returns:
        True if successful, False otherwise
    """
    payload = {
        "name": role_name,
        "description": f"Role for {role_name}",
        "attributes": {
            "paths": paths,
            "message": [message] if message else [],
        },
    }

    resp = kc_request("POST", f"/admin/realms/{realm}/roles", token, payload)

    if resp.status_code == 201:
        logger.info("  Created role: %s", role_name)
        return True
    elif resp.status_code == 409:
        # Role already exists (race condition)
        logger.warning("  Role already exists: %s", role_name)
        return False
    else:
        logger.error("  Failed to create role %s: %s", role_name, resp.text)
        return False


def update_role_attributes(
    token: str, realm: str, role_name: str, paths: list[str], message: str
) -> bool:
    """Update an existing role's paths and message attributes.

    Args:
        token: Admin access token
        realm: Realm name
        role_name: Name of the role to update
        paths: List of path patterns
        message: Custom 403 message

    Returns:
        True if successful, False otherwise
    """
    # First, get the current role data
    role_data = get_role_by_name(token, realm, role_name)
    if not role_data:
        logger.error("  Role not found: %s", role_name)
        return False

    # Build the updated payload with all existing fields plus new attributes
    payload = {
        "name": role_name,
        "description": role_data.get("description", f"Role for {role_name}"),
        "composite": role_data.get("composite", False),
        "composites": role_data.get("composites"),
        "attributes": {
            "paths": paths,
            "message": [message] if message else [],
        },
    }

    # Remove None values
    payload = {k: v for k, v in payload.items() if v is not None}

    resp = kc_request("PUT", f"/admin/realms/{realm}/roles/{role_name}", token, payload)

    if resp.status_code == 204:
        logger.info("  Updated role: %s", role_name)
        return True
    else:
        logger.error("  Failed to update role %s: %s", role_name, resp.text)
        return False


def sync_role_to_keycloak(
    token: str, realm: str, role_name: str, config: dict, create_if_missing: bool = True
) -> tuple[bool, str]:
    """Sync a single role to Keycloak.

    Args:
        token: Admin access token
        realm: Realm name
        role_name: Name of the role
        config: Role configuration with paths and message
        create_if_missing: Whether to create role if it doesn't exist

    Returns:
        Tuple of (success: bool, action: str)
    """
    paths = config["paths"]
    message = config["message"]

    # Check if role exists
    role_data = get_role_by_name(token, realm, role_name)

    if role_data:
        # Update existing role
        success = update_role_attributes(token, realm, role_name, paths, message)
        return success, "updated" if success else "failed"
    else:
        # Create new role if requested
        if create_if_missing:
            success = create_role_with_attributes(token, realm, role_name, paths, message)
            return success, "created" if success else "failed"
        else:
            logger.warning("  Role not found and create_if_missing=False: %s", role_name)
            return False, "skipped"


def print_summary(results: dict[str, str]) -> None:
    """Print a summary table of all operations."""
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
