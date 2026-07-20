#!/usr/bin/env python3
"""Keycloak Setup Script for ConciergeOS.

Provisions realms, users, groups, and client configuration for ConciergeOS.
Usage: python keycloak_setup.py [keycloak_host] [keycloak_port]
Example: python keycloak_setup.py localhost 8080
"""

import argparse
import os
import sys

import requests


# ------------------------------------------------------------------
# Configuration
# ------------------------------------------------------------------

REALMS = ["testing", "production"]
GROUPS = ["single", "all"]
CLIENT_ID = "concierge"
CLIENT_SECRET = "changeme"
# oauth2-proxy redirect URIs (must match oidc-main.toml and oidc-settings.toml)
OIDC_MAIN_REDIRECT_URI = "https://out-customer.com/oauth2/callback"
OIDC_SETTINGS_REDIRECT_URI = "https://out-customer.com/settings/oauth2/callback"
POST_LOGOUT_URI = "https://out-customer.com/"

USERS = {
    "user1": {"password": "password1", "group": "single"},
    "user2": {"password": "password2", "group": "all"},
}


def get_base_url(host: str, port: int) -> str:
    return f"http://{host}:{port}/auth"


def authenticate(base_url: str, username: str, password: str) -> str:
    """Authenticate as admin to the master realm and return access token."""
    print("[1/8] Authenticating as admin...")
    resp = requests.post(
        f"{base_url}/realms/master/protocol/openid-connect/token",
        data={
            "grant_type": "password",
            "client_id": "admin-cli",
            "username": username,
            "password": password,
        },
    )
    resp.raise_for_status()
    token = resp.json().get("access_token")
    if not token:
        print("ERROR: Failed to authenticate to Keycloak admin.")
        sys.exit(1)
    print("  ✓ Authenticated\n")
    return token


def api_request(
    method: str,
    url: str,
    token: str,
    payload: dict | None = None,
) -> requests.Response:
    """Make an API request to Keycloak admin API."""
    return requests.request(
        method,
        url,
        json=payload or {},
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
    )


# ------------------------------------------------------------------
# 2. Create Realms
# ------------------------------------------------------------------


def create_realms(base_url: str, token: str) -> None:
    """Create realms: testing, production."""
    print("[2/8] Creating realms...")
    for realm in REALMS:
        resp = requests.get(
            f"{base_url}/admin/realms/{realm}",
            headers={"Authorization": f"Bearer {token}"},
        )
        if resp.status_code == 200:
            print(f"  ⏭ Realm {realm} already exists, skipping")
            continue
        resp = api_request("POST", f"{base_url}/admin/realms", token, {
            "realm": realm,
            "enabled": True,
        })
        resp.raise_for_status()
        print(f"  ✓ Realm {realm} created")
    print()


# ------------------------------------------------------------------
# 3. Create Groups
# ------------------------------------------------------------------


def create_group(base_url: str, token: str, realm: str, group_name: str) -> str:
    """Create a group in a realm. Returns the group ID."""
    # Search for existing group
    resp = requests.get(
        f"{base_url}/admin/realms/{realm}/groups",
        params={"first": 0, "max": 100, "q": group_name},
        headers={"Authorization": f"Bearer {token}"},
    )
    resp.raise_for_status()
    groups = resp.json()
    match = [g for g in groups if g["name"] == group_name]

    if match:
        print(f"    ⏭ Group {group_name} already exists")
        return match[0]["id"]

    resp = api_request(
        "POST",
        f"{base_url}/admin/realms/{realm}/groups",
        token,
        {"name": group_name},
    )
    resp.raise_for_status()
    group_id = resp.headers.get("Location", "").split("/")[-1]
    if not group_id:
        # Fallback: query by group name
        resp = requests.get(
            f"{base_url}/admin/realms/{realm}/groups",
            params={"first": 0, "max": 100, "q": group_name},
            headers={"Authorization": f"Bearer {token}"},
        )
        resp.raise_for_status()
        match = [g for g in resp.json() if g["name"] == group_name]
        if match:
            group_id = match[0]["id"]

    if not group_id:
        print(f"    ⚠ Could not extract group ID for {group_name}")
        return ""
    print(f"    ✓ Group {group_name} created (id: {group_id[:8]}...)")
    return group_id


def create_all_groups(base_url: str, token: str) -> dict[str, dict[str, str]]:
    """Create groups in all realms. Returns {realm: {group_name: group_id}}."""
    print("[3/8] Creating groups in realms...")
    group_ids: dict[str, dict[str, str]] = {}

    for realm in REALMS:
        print(f"  Realm: {realm}")
        group_ids[realm] = {}
        for group_name in GROUPS:
            group_ids[realm][group_name] = create_group(
                base_url, token, realm, group_name
            )
    print()
    return group_ids


# ------------------------------------------------------------------
# 4. Create Users
# ------------------------------------------------------------------


def create_user(base_url: str, token: str, realm: str, username: str, password: str) -> str:
    """Create a user in a realm. Returns the user ID."""
    # Check if user exists
    resp = requests.get(
        f"{base_url}/admin/realms/{realm}/users",
        params={"username": username, "max": 1},
        headers={"Authorization": f"Bearer {token}"},
    )
    resp.raise_for_status()

    if resp.json():
        print(f"    ⏭ User {username} already exists")
        return resp.json()[0]["id"]

    resp = api_request(
        "POST",
        f"{base_url}/admin/realms/{realm}/users",
        token,
        {
            "username": username,
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
        },
    )
    resp.raise_for_status()

    # Extract user ID from Location header (HTTP 201 returns location)
    user_id = resp.headers.get("Location", "").split("/")[-1]
    if not user_id:
        # Fallback: query by username again
        resp = requests.get(
            f"{base_url}/admin/realms/{realm}/users",
            params={"username": username, "max": 1},
            headers={"Authorization": f"Bearer {token}"},
        )
        resp.raise_for_status()
        user_id = resp.json()[0]["id"]

    print(f"    ✓ User {username} created")
    return user_id


def create_all_users(base_url: str, token: str) -> dict[str, dict[str, str]]:
    """Create users in all realms. Returns {realm: {username: user_id}}."""
    print("[4/8] Creating users in realms...")
    user_ids: dict[str, dict[str, str]] = {}

    for realm in REALMS:
        print(f"  Realm: {realm}")
        user_ids[realm] = {}
        for username, config in USERS.items():
            user_ids[realm][username] = create_user(
                base_url, token, realm, username, config["password"]
            )
    print()
    return user_ids


# ------------------------------------------------------------------
# 5. Assign Users to Groups
# ------------------------------------------------------------------


def assign_user_to_group(
    base_url: str,
    token: str,
    realm: str,
    user_id: str,
    group_id: str,
    username: str,
    group_name: str,
) -> None:
    """Assign a user to a group."""
    if not user_id or not group_id:
        print(f"    ⚠ Skipping {username} -> {group_name} (missing IDs)")
        return

    # Check if already assigned (Keycloak returns 200 if member, 404 if not)
    resp = requests.get(
        f"{base_url}/admin/realms/{realm}/users/{user_id}/groups/{group_id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    if resp.status_code == 200:
        print(f"    ⏭ {username} already in {group_name}")
        return

    resp = api_request(
        "PUT",
        f"{base_url}/admin/realms/{realm}/users/{user_id}/groups/{group_id}",
        token,
        {},
    )
    # PUT returns 204 No Content on success
    if resp.status_code in (200, 204):
        print(f"    ✓ {username} -> {group_name}")
    else:
        print(f"    ⚠ Could not assign {username} to {group_name}: {resp.status_code}")


def assign_all_users_to_groups(
    base_url: str,
    token: str,
    user_ids: dict[str, dict[str, str]],
    group_ids: dict[str, dict[str, str]],
) -> None:
    """Assign all users to their respective groups in all realms."""
    print("[5/8] Assigning users to groups...")

    for realm in REALMS:
        print(f"  Realm: {realm}")
        for username, config in USERS.items():
            group_name = config["group"]
            assign_user_to_group(
                base_url,
                token,
                realm,
                user_ids[realm][username],
                group_ids[realm][group_name],
                username,
                group_name,
            )
    print()


# ------------------------------------------------------------------
# 6. Create Client
# ------------------------------------------------------------------


def create_client(base_url: str, token: str, realm: str) -> str:
    """Create the conciergeos client in a realm. Returns the client UUID."""
    print(f"  Creating client: {CLIENT_ID} in {realm}...")

    # Check if client exists
    resp = requests.get(
        f"{base_url}/admin/realms/{realm}/clients",
        headers={"Authorization": f"Bearer {token}"},
    )
    resp.raise_for_status()
    clients = resp.json()
    match = [c for c in clients if c["clientId"] == CLIENT_ID]

    if match:
        print(f"    ⏭ Client {CLIENT_ID} already exists in {realm}")
        return match[0]["id"]

    resp = api_request(
        "POST",
        f"{base_url}/admin/realms/{realm}/clients",
        token,
        {
            "clientId": CLIENT_ID,
            "enabled": True,
            "publicClient": False,
            "standardFlowEnabled": True,
            "implicitFlowEnabled": False,
            "directAccessGrantsEnabled": True,
            "serviceAccountsEnabled": False,
            "redirectUris": [
                OIDC_MAIN_REDIRECT_URI,
                OIDC_SETTINGS_REDIRECT_URI,
                "https://out-customer.com/*",
                "http://localhost:*/*",
            ],
            "webOrigins": [
                "https://out-customer.com",
                "http://localhost:*",
            ],
            # postLogoutRedirectUris is NOT a top-level field in Keycloak 26's
            # ClientRepresentation - it's stored as a semicolon-separated attribute
            # (see OIDCConfigAttributes.POST_LOGOUT_REDIRECT_URIS = "post.logout.redirect.uris")
            "attributes": {
                "pkce.code.challenge.method": "S256",
                "post.logout.redirect.uris": "##".join([
                    POST_LOGOUT_URI,
                    "https://out-customer.com/*",
                    "http://localhost:*",
                ]),
            },
        },
    )
    resp.raise_for_status()

    # Extract client UUID from Location header
    client_uuid = resp.headers.get("Location", "").split("/")[-1]
    if not client_uuid:
        # Fallback: query again
        resp = requests.get(
            f"{base_url}/admin/realms/{realm}/clients",
            headers={"Authorization": f"Bearer {token}"},
        )
        resp.raise_for_status()
        match = [c for c in resp.json() if c["clientId"] == CLIENT_ID]
        client_uuid = match[0]["id"]

    # Generate client secret (Keycloak 26+ requires POST to /client-secret)
    resp = requests.post(
        f"{base_url}/admin/realms/{realm}/clients/{client_uuid}/client-secret",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
    )
    resp.raise_for_status()
    secret_value = resp.json().get("value", CLIENT_SECRET)
    print(f"    ✓ Client {CLIENT_ID} created in {realm} (secret: {secret_value})")
    return client_uuid


def create_all_clients(base_url: str, token: str) -> dict[str, str]:
    """Create clients in all realms. Returns {realm: client_uuid}."""
    print("[6/8] Creating clients in realms...")
    client_uuids: dict[str, str] = {}

    for realm in REALMS:
        client_uuids[realm] = create_client(base_url, token, realm)
    print()
    return client_uuids


# ------------------------------------------------------------------
# 7. Configure Client Scopes
# ------------------------------------------------------------------


def configure_groups_claim(base_url: str, token: str, realm: str, client_uuid: str) -> None:
    """Ensure groups claim is included in ID token."""
    print(f"  Configuring groups claim for {realm}...")

    # Get existing protocol mappers
    resp = requests.get(
        f"{base_url}/admin/realms/{realm}/clients/{client_uuid}/protocol-mappers/models",
        headers={"Authorization": f"Bearer {token}"},
    )
    resp.raise_for_status()
    mappers = resp.json()
    has_groups = any(m["name"] == "groups" for m in mappers)

    if has_groups:
        print("    ⏭ Groups mapper already exists")
        return

    resp = api_request(
        "POST",
        f"{base_url}/admin/realms/{realm}/clients/{client_uuid}/protocol-mappers/models",
        token,
            {
                "name": "groups",
                "protocol": "openid-connect",
                "protocolMapper": "oidc-group-membership-mapper",
                "config": {
                "claim.name": "groups",
                "id.token.claim": "true",
                "access.token.claim": "true",
                "userinfo.token.claim": "true",
                "multivalued": "true",
            },
        },
    )
    resp.raise_for_status()
    print("    ✓ Groups mapper created")


def configure_all_groups_claims(
    base_url: str,
    token: str,
    client_uuids: dict[str, str],
) -> None:
    """Configure groups claim for all realms."""
    print("[7/8] Configuring groups claim in ID token...")

    for realm in REALMS:
        configure_groups_claim(base_url, token, realm, client_uuids[realm])
    print()


# ------------------------------------------------------------------
# 8. Summary
# ------------------------------------------------------------------


def print_summary(base_url: str, admin_user: str, admin_pass: str) -> None:
    """Print a summary of the setup."""
    print("=== Setup Complete ===")
    print()
    print(f"Realms created: {', '.join(REALMS)}")
    print("Users per realm:")
    for username, config in USERS.items():
        print(f"  {username} (password: {config['password']}) -> group: {config['group']}")
    print()
    print(f"Client: {CLIENT_ID} (confidential, PKCE enabled)")
    print(f"Client Secret: {CLIENT_SECRET}")
    print("Redirect URIs:")
    print(f"  Main:     {OIDC_MAIN_REDIRECT_URI}")
    print(f"  Settings: {OIDC_SETTINGS_REDIRECT_URI}")
    print()
    print(f"Keycloak Admin Console:")
    print(f"  URL: {base_url}/admin")
    print(f"  Login: {admin_user} / {admin_pass}")
    print()
    print("Access Control:")
    print("  - Group 'single': access to /settings only")
    print("  - Group 'all': access to all pages")
    print()


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Keycloak Setup for ConciergeOS. "
        "Provisions realms, users, groups, and client configuration."
    )
    parser.add_argument(
        "host",
        nargs="?",
        default=os.environ.get("KEYCLOAK_HOST", "keycloak"),
        help="Keycloak host (default: from KEYCLOAK_HOST env var or 'keycloak')",
    )
    parser.add_argument(
        "port",
        nargs="?",
        type=int,
        default=int(os.environ.get("KEYCLOAK_PORT", "8080")),
        help="Keycloak port (default: from KEYCLOAK_PORT env var or 8080)",
    )
    args = parser.parse_args()

    base_url = get_base_url(args.host, args.port)
    admin_user = os.environ.get("KC_ADMIN_USER", "admin")
    admin_pass = os.environ.get("KC_ADMIN_PASS", "admin")

    print("=== Keycloak Setup for ConciergeOS ===")
    print(f"Connecting to: {base_url}")
    print()

    # 1. Authenticate
    token = authenticate(base_url, admin_user, admin_pass)

    # 2. Create realms
    create_realms(base_url, token)

    # 3. Create groups
    group_ids = create_all_groups(base_url, token)

    # 4. Create users
    user_ids = create_all_users(base_url, token)

    # 5. Assign users to groups
    assign_all_users_to_groups(base_url, token, user_ids, group_ids)

    # 6. Create clients
    client_uuids = create_all_clients(base_url, token)

    # 7. Configure groups claim
    configure_all_groups_claims(base_url, token, client_uuids)

    # 8. Summary
    print_summary(base_url, admin_user, admin_pass)


if __name__ == "__main__":
    main()