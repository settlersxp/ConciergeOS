#!/usr/bin/env python3
"""User management for Keycloak setup.

Handles creation and configuration of Keycloak users.
"""

from keycloak_common import kc_request

from .config import USERS


# ------------------------------------------------------------------
# User Creation
# ------------------------------------------------------------------


def create_user(token: str, realm: str, username: str, password: str) -> str:
    """Create a user in a realm. Returns the user ID.

    Keycloak blocks password grant for users with pending required actions
    (e.g., UPDATE_PASSWORD, VERIFY_EMAIL) with "Account is not fully set up".
    We set firstName/lastName and clear requiredActions to avoid this.
    """
    # Check if user exists
    resp = kc_request(
        "GET",
        f"/admin/realms/{realm}/users",
        token,
        params={"username": username, "max": 1},
    )
    resp.raise_for_status()

    if resp.json():
        print(f"    ⏭ User {username} already exists")
        user_id = resp.json()[0]["id"]
        # Ensure existing users also have required actions cleared
        _clear_required_actions(token, realm, user_id)
        return user_id

    resp = kc_request(
        "POST",
        f"/admin/realms/{realm}/users",
        token,
        {
            "username": username,
            "firstName": username,
            "lastName": "User",
            "enabled": True,
            "email": f"{username}@conciergeos.local",
            "credentials": [
                {
                    "type": "password",
                    "value": password,
                    "temporary": False,
                }
            ],
            "emailVerified": True,
            "requiredActions": [],
        },
    )
    resp.raise_for_status()

    # Extract user ID from Location header (HTTP 201 returns location)
    user_id = resp.headers.get("Location", "").split("/")[-1]
    if not user_id:
        # Fallback: query by username again
        resp = kc_request(
            "GET",
            f"/admin/realms/{realm}/users",
            token,
            params={"username": username, "max": 1},
        )
        resp.raise_for_status()
        user_id = resp.json()[0]["id"]

    # Clear any required actions that Keycloak may have added
    _clear_required_actions(token, realm, user_id)

    print(f"    ✓ User {username} created")
    return user_id


def _clear_required_actions(token: str, realm: str, user_id: str) -> None:
    """Clear required actions on a user so password grant authentication works.

    Keycloak blocks password grant for users with pending required actions
    (e.g., UPDATE_PASSWORD, VERIFY_EMAIL) with "Account is not fully set up".
    We fetch the user, clear requiredActions, and PUT back.
    """
    resp = kc_request("GET", f"/admin/realms/{realm}/users/{user_id}", token)
    resp.raise_for_status()
    user_data = resp.json()
    user_data["requiredActions"] = []

    resp = kc_request("PUT", f"/admin/realms/{realm}/users/{user_id}", token, user_data)
    resp.raise_for_status()


def create_all_users(token: str) -> dict[str, dict[str, str]]:
    """Create users in all realms. Returns {realm: {username: user_id}}."""
    print("[4/8] Creating users in realms...")
    user_ids: dict[str, dict[str, str]] = {}

    for realm in REALMS:
        print(f"  Realm: {realm}")
        user_ids[realm] = {}
        for username, config in USERS.items():
            user_ids[realm][username] = create_user(
                token, realm, username, config["password"]
            )
    print()
    return user_ids


# Import REALMS here to avoid circular imports
from .config import REALMS