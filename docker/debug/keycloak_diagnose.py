#!/usr/bin/env python3
"""Keycloak Diagnostic Script.

Lists all realms, users, groups, and clients in the Keycloak instance.
Usage: python keycloak_diagnose.py [keycloak_host] [keycloak_port]
Example: python keycloak_diagnose.py localhost 8080
"""

import os
import sys

import requests


def get_base_url(host: str, port: int) -> str:
    return f"http://{host}:{port}/auth"


def authenticate(base_url: str, username: str, password: str) -> str:
    """Authenticate as admin to the master realm and return access token."""
    print("[*] Authenticating as admin...")
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


def list_realms(base_url: str, token: str) -> list[str]:
    """List all realms."""
    resp = requests.get(
        f"{base_url}/admin/realms",
        headers={"Authorization": f"Bearer {token}"},
    )
    resp.raise_for_status()
    realms = resp.json()
    return [r["realm"] for r in realms]


def list_users(base_url: str, token: str, realm: str) -> list[dict]:
    """List all users in a realm."""
    resp = requests.get(
        f"{base_url}/admin/realms/{realm}/users",
        params={"first": 0, "max": 100},
        headers={"Authorization": f"Bearer {token}"},
    )
    resp.raise_for_status()
    return resp.json()


def list_groups(base_url: str, token: str, realm: str) -> list[dict]:
    """List all groups in a realm."""
    resp = requests.get(
        f"{base_url}/admin/realms/{realm}/groups",
        params={"first": 0, "max": 100},
        headers={"Authorization": f"Bearer {token}"},
    )
    resp.raise_for_status()
    return resp.json()


def list_clients(base_url: str, token: str, realm: str) -> list[dict]:
    """List all clients in a realm."""
    resp = requests.get(
        f"{base_url}/admin/realms/{realm}/clients",
        headers={"Authorization": f"Bearer {token}"},
    )
    resp.raise_for_status()
    return resp.json()


def get_user_groups(base_url: str, token: str, realm: str, user_id: str) -> list[dict]:
    """Get groups for a specific user."""
    resp = requests.get(
        f"{base_url}/admin/realms/{realm}/users/{user_id}/groups",
        params={"first": 0, "max": 100},
        headers={"Authorization": f"Bearer {token}"},
    )
    resp.raise_for_status()
    return resp.json()


def main() -> None:
    host = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("KEYCLOAK_HOST", "keycloak")
    port = int(sys.argv[2]) if len(sys.argv) > 2 else int(os.environ.get("KEYCLOAK_PORT", "8080"))

    base_url = get_base_url(host, port)
    admin_user = os.environ.get("KC_ADMIN_USER", "admin")
    admin_pass = os.environ.get("KC_ADMIN_PASS", "admin")

    print(f"=== Keycloak Diagnostic ===")
    print(f"Connecting to: {base_url}\n")

    # Authenticate
    token = authenticate(base_url, admin_user, admin_pass)

    # List realms
    realms = list_realms(base_url, token)
    print(f"=== Realms ({len(realms)}) ===")
    for r in realms:
        print(f"  - {r}")
    print()

    for realm in realms:
        print(f"=== Realm: {realm} ===")

        # Users
        users = list_users(base_url, token, realm)
        print(f"\n  Users ({len(users)}):")
        for user in users:
            username = user.get("username", "unknown")
            user_id = user.get("id", "")
            email = user.get("email", "N/A")
            enabled = user.get("enabled", False)
            print(f"    - {username} (id: {user_id[:12]}..., email: {email}, enabled: {enabled})")

            # Get user groups
            groups = get_user_groups(base_url, token, realm, user_id)
            if groups:
                group_names = [g["name"] for g in groups]
                print(f"      Groups: {', '.join(group_names)}")

        # Groups
        groups = list_groups(base_url, token, realm)
        print(f"\n  Groups ({len(groups)}):")
        for group in groups:
            group_name = group.get("name", "unknown")
            group_id = group.get("id", "")
            print(f"    - {group_name} (id: {group_id[:12]}...)")

        # Clients
        clients = list_clients(base_url, token, realm)
        print(f"\n  Clients ({len(clients)}):")
        for client in clients:
            client_id = client.get("clientId", "unknown")
            client_uuid = client.get("id", "")
            public = client.get("publicClient", True)
            standard_flow = client.get("standardFlowEnabled", False)
            redirect_uris = client.get("redirectUris", [])
            print(f"    - {client_id} (id: {client_uuid[:12]}..., public: {public}, standardFlow: {standard_flow})")
            if redirect_uris:
                for uri in redirect_uris:
                    print(f"      Redirect URI: {uri}")

            # Check PKCE settings
            attrs = client.get("attributes", {})
            pkce_method = attrs.get("pkce.code.challenge.method", "not set")
            print(f"      PKCE Challenge Method: {pkce_method}")

        print(f"\n{'=' * 40}\n")


if __name__ == "__main__":
    main()