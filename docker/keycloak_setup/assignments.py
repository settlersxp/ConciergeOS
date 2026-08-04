#!/usr/bin/env python3
"""Role assignment for Keycloak setup.

Handles assigning users to roles.
"""

from keycloak_common import fetch_all_roles_with_attrs, kc_request

from .config import USERS


# ------------------------------------------------------------------
# Role Assignment
# ------------------------------------------------------------------


def assign_user_to_roles(
    token: str,
    realm: str,
    user_id: str,
    role_names: list[str],
    username: str,
) -> None:
    """Assign a user to realm roles."""
    if not user_id:
        print(f"    ⚠ Skipping {username} (missing user ID)")
        return

    # Get all roles with their IDs using keycloak_common helper
    all_roles_data = fetch_all_roles_with_attrs(token, realm)
    # Fetch full role data to get IDs
    resp = kc_request("GET", f"/admin/realms/{realm}/roles", token)
    resp.raise_for_status()
    all_roles = {r["name"]: r for r in resp.json()}

    # Check existing role mappings
    resp = kc_request(
        "GET",
        f"/admin/realms/{realm}/users/{user_id}/role-mappings/realm",
        token,
    )
    resp.raise_for_status()
    existing_roles = {r["name"] for r in resp.json()}

    # Assign missing roles
    roles_payload = []
    for role_name in role_names:
        if role_name in existing_roles:
            print(f"    ⏭ {username} already has {role_name}")
            continue
        if role_name in all_roles:
            roles_payload.append({
                "id": all_roles[role_name]["id"],
                "name": role_name,
            })

    if roles_payload:
        resp = kc_request(
            "POST",
            f"/admin/realms/{realm}/users/{user_id}/role-mappings/realm",
            token,
            roles_payload,
        )
        if resp.status_code in (200, 204, 201):
            role_list = ", ".join(r["name"] for r in roles_payload)
            print(f"    ✓ {username} → {role_list}")
        else:
            print(f"    ⚠ Could not assign roles to {username}: {resp.status_code}")


def assign_all_users_to_roles(
    token: str,
    user_ids: dict[str, dict[str, str]],
    role_data: dict[str, dict[str, str]],
) -> None:
    """Assign all users to their respective roles in all realms."""
    print("[5/8] Assigning users to roles...")

    for realm in REALMS:
        print(f"  Realm: {realm}")
        for username, config in USERS.items():
            assign_user_to_roles(
                token,
                realm,
                user_ids[realm][username],
                config["roles"],
                username,
            )
    print()


# Import REALMS here to avoid circular imports
from .config import REALMS