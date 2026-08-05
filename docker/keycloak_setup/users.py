#!/usr/bin/env python3
"""User management for Keycloak setup.

Handles creation and configuration of Keycloak users.
"""

import logging

import requests

from keycloak_common import kc_request

from .config import USERS

logger = logging.getLogger(__name__)


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
        logger.info("    ⏭ User %s already exists", username)
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

    logger.info("    ✓ User %s created", username)
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
    logger.info("[4/8] Creating users in realms...")
    user_ids: dict[str, dict[str, str]] = {}

    for realm in REALMS:
        logger.info("  Realm: %s", realm)
        user_ids[realm] = {}
        for username, config in USERS.items():
            user_ids[realm][username] = create_user(
                token, realm, username, config["password"]
            )
    logger.info("")
    return user_ids


# Import REALMS here to avoid circular imports
from .config import REALMS


# ------------------------------------------------------------------
# User Query & Deletion
# ------------------------------------------------------------------


def get_users_by_username(token: str, realm: str, username: str) -> list[dict]:
    """Search users by username in a realm.

    Args:
        token: Keycloak admin token
        realm: Realm name
        username: Username to search for

    Returns:
        List of user dictionaries matching the username
    """
    resp = kc_request(
        "GET",
        f"/admin/realms/{realm}/users",
        token,
        params={"username": username, "max": 1},
    )
    resp.raise_for_status()
    return resp.json()


def delete_user(token: str, realm: str, user_id: str) -> requests.Response:
    """Delete a user by ID. Returns the raw Response.

    Args:
        token: Keycloak admin token
        realm: Realm name
        user_id: User ID to delete

    Returns:
        Raw requests.Response object
    """
    return kc_request(
        "DELETE",
        f"/admin/realms/{realm}/users/{user_id}",
        token,
    )


def create_test_user(
    token: str,
    realm: str,
    username: str,
    password: str = "TestPass123!",
) -> requests.Response:
    """Create a test user in a realm. Returns the raw Response.

    Args:
        token: Keycloak admin token
        realm: Realm name
        username: Username for the new user
        password: Password for the new user

    Returns:
        Raw requests.Response object
    """
    return kc_request(
        "POST",
        f"/admin/realms/{realm}/users",
        token,
        {
            "username": username,
            "enabled": True,
            "email": f"{username}@conciergeos.local",
            "credentials": [
                {"type": "password", "value": password, "temporary": False}
            ],
            "emailVerified": True,
            "requiredActions": [],
        },
    )
