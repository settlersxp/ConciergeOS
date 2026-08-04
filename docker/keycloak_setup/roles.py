#!/usr/bin/env python3
"""Role management for Keycloak setup.

Handles creation of realm roles and composite roles.
"""

from keycloak_common import get_role_by_name, kc_request

from .config import REALMS, get_composite_roles, get_roles


# ------------------------------------------------------------------
# Role Creation
# ------------------------------------------------------------------


def create_role(token: str, realm: str, role_name: str, description: str = "") -> str:
    """Create a realm role. Returns the role name (Keycloak roles are identified by name)."""
    # Check if role exists using keycloak_common helper
    role = get_role_by_name(token, realm, role_name)
    if role:
        print(f"    ⏭ Role {role_name} already exists")
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
        print(f"    ✓ Role {role_name} created")
    else:
        print(f"    ⚠ Failed to create role {role_name}: {resp.status_code} {resp.text}")
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
            print(f"    ✓ Composite role {role_name} configured with {len(composite_role_ids)} sub-roles")
        else:
            print(f"    ⚠ Failed to configure composites for {role_name}: {resp.status_code}")

    return role_name


def create_all_roles(token: str) -> dict[str, dict[str, str]]:
    """Create roles in all realms. Returns {realm: {role_name: role_data}}."""
    print("[3/8] Creating roles in realms...")
    role_data: dict[str, dict[str, str]] = {}

    for realm in REALMS:
        print(f"  Realm: {realm}")
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

    print()
    return role_data
