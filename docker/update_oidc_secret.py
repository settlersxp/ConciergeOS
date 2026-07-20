#!/usr/bin/env python3
"""Update the oauth2-proxy config files with the actual Keycloak client secret.

Usage: python update_oidc_secret.py [keycloak_host] [keycloak_port]
Example: python update_oidc_secret.py localhost 8080
"""

import argparse
import json
import os
import sys

import requests


CLIENT_ID = "concierge"
REALMS = ["testing", "production"]


def get_base_url(host: str, port: int) -> str:
    return f"http://{host}:{port}/auth"


def authenticate(base_url: str, username: str, password: str) -> str:
    """Authenticate as admin to the master realm and return access token."""
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
    return token


def get_client_secret(base_url: str, token: str, realm: str) -> str:
    """Get the existing client secret from Keycloak for the concierge client."""
    resp = requests.get(
        f"{base_url}/admin/realms/{realm}/clients",
        headers={"Authorization": f"Bearer {token}"},
    )
    resp.raise_for_status()
    clients = resp.json()
    match = [c for c in clients if c["clientId"] == CLIENT_ID]
    if not match:
        print(f"  ERROR: Client {CLIENT_ID} not found in {realm}")
        sys.exit(1)

    client_uuid = match[0]["id"]

    # Rotate/refresh the secret to get it back (POST generates new)
    resp = requests.post(
        f"{base_url}/admin/realms/{realm}/clients/{client_uuid}/client-secret",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
    )
    resp.raise_for_status()
    secret = resp.json().get("value", "")
    return secret


def update_toml_file(filepath: str, new_secret: str) -> None:
    """Update the client_secret field in a TOML config file."""
    if not os.path.exists(filepath):
        print(f"  WARNING: {filepath} not found, skipping")
        return

    with open(filepath, "r") as f:
        content = f.read()

    # Find and replace the client_secret line
    lines = content.split("\n")
    updated = False
    for i, line in enumerate(lines):
        if line.startswith("client_secret = "):
            lines[i] = f'client_secret = "{new_secret}"'
            updated = True
            break

    if not updated:
        print(f"  WARNING: client_secret not found in {filepath}")
        return

    with open(filepath, "w") as f:
        f.write("\n".join(lines))

    print(f"  ✓ Updated {filepath}")


def main():
    parser = argparse.ArgumentParser(
        description="Update oauth2-proxy config files with the actual Keycloak client secret."
    )
    parser.add_argument(
        "host",
        nargs="?",
        default=os.environ.get("KEYCLOAK_HOST", "localhost"),
        help="Keycloak host (default: localhost)",
    )
    parser.add_argument(
        "port",
        nargs="?",
        type=int,
        default=int(os.environ.get("KEYCLOAK_PORT", "8080")),
        help="Keycloak port (default: 8080)",
    )
    args = parser.parse_args()

    base_url = get_base_url(args.host, args.port)
    admin_user = os.environ.get("KC_ADMIN_USER", "admin")
    admin_pass = os.environ.get("KC_ADMIN_PASS", "admin")

    print("=== Updating OAuth2-Proxy Client Secret ===")
    print(f"Connecting to: {base_url}")

    # Authenticate
    token = authenticate(base_url, admin_user, admin_pass)
    print("✓ Authenticated\n")

    # Get the secret from the production realm (the one used by oidc-main)
    print("Getting client secret from production realm...")
    secret = get_client_secret(base_url, token, "production")
    print(f"  Secret: {secret}\n")

    # Update config files in the current directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Update oidc-main.toml
    main_config = os.path.join(script_dir, "oidc-main.toml")
    update_toml_file(main_config, secret)

    # Update oidc-settings.toml
    settings_config = os.path.join(script_dir, "oidc-settings.toml")
    update_toml_file(settings_config, secret)

    print(f"\n=== Done ===")
    print(f"Client secret updated to: {secret}")
    print("Restart the oauth2-proxy containers for the change to take effect:")
    print("  docker compose restart oidc-main oidc-settings")


if __name__ == "__main__":
    main()