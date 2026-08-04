#!/usr/bin/env python3
"""Summary and main entry point for Keycloak setup.

Handles printing setup summaries and orchestrating the full setup process.
"""

import argparse

from keycloak_common import authenticate
from settings import settings

from .assignments import assign_all_users_to_roles
from .claims import configure_all_role_claims
from .clients import (
    create_all_client_apis,
    create_all_clients,
    get_actual_client_secret,
    get_client_api_secret,
)
from .config import CLIENT_API_ID, CLIENT_ID, REALMS, USERS, get_composite_roles, get_roles
from .env_update import update_oidc_configs
from .realms import create_realms
from .roles import create_all_roles
from .users import create_all_users


# ------------------------------------------------------------------
# Summary Printing
# ------------------------------------------------------------------


def print_summary(admin_user: str, admin_pass: str, actual_secret: str) -> None:
    """Print a summary of the setup."""
    print("=== Setup Complete ===")
    print()
    print(f"Realms created: {', '.join(REALMS)}")
    print()
    print("Roles created:")
    for role_name, description in get_roles().items():
        print(f"  {role_name}: {description}")
    for composite_name, sub_roles in get_composite_roles().items():
        print(f"  {composite_name}: (composite of {len(sub_roles)} roles)")
    print()
    print("Users per realm:")
    for username, config in USERS.items():
        role_list = ", ".join(config["roles"])
        print(f"  {username} (password: {config['password']}) → roles: {role_list}")
    print()
    print(f"Client: {CLIENT_ID} (confidential, PKCE enabled)")
    print(f"Client Secret: {actual_secret}")
    print("Redirect URIs:")
    print(f"  App1:     {settings.APP_DOMAIN}/app1/oauth2/callback")
    print(f"  App2:     {settings.APP_DOMAIN}/app2/oauth2/callback")
    print()
    print(f"Client: {CLIENT_API_ID} (confidential, Client Credentials Grant)")
    print(f"Client Secret: {get_client_api_secret()}")
    print("  Grant Type: client_credentials (machine-to-machine)")
    print("  Service Accounts: enabled")
    print()
    print(f"Keycloak Admin Console:")
    print(f"  URL: {settings.KEYCLOAK_URL}/admin")
    print(f"  Login: {admin_user} / {admin_pass}")
    print()
    print("Access Control (Role-Based):")
    print("  - Roles are extracted from access token by oauth2-proxy")
    print("  - X-Forwarded-Groups header contains 'role:<name>' values")
    print("  - Caddy enforces path-level access via header_regexp rules")
    print("  - Role sync service auto-propagates role changes to Caddy")
    print()


# ------------------------------------------------------------------
# Main Entry Point
# ------------------------------------------------------------------


def main() -> None:
    """Main entry point for Keycloak setup."""
    parser = argparse.ArgumentParser(
        description="Keycloak Setup for ConciergeOS. "
        "Provisions realms, users, roles, and client configuration."
    )
    parser.parse_args()

    admin_user = settings.KEYCLOAK_ADMIN_USER
    admin_pass = settings.KEYCLOAK_ADMIN_PASSWORD

    print("=== Keycloak Setup for ConciergeOS ===")
    print(f"Connecting to: {settings.KEYCLOAK_URL}")
    print()

    # 1. Authenticate (uses settings.KEYCLOAK_URL, KEYCLOAK_ADMIN_USER, KEYCLOAK_ADMIN_PASSWORD)
    token = authenticate()

    # 2. Create realms
    create_realms(token)

    # 3. Create roles (replaces groups)
    role_data = create_all_roles(token)

    # 4. Create users
    user_ids = create_all_users(token)

    # 5. Assign users to roles (replaces group assignment)
    assign_all_users_to_roles(token, user_ids, role_data)

    # 6. Create clients
    client_uuids = create_all_clients(token)

    # 6b. Create the client-api service client
    client_api_results = create_all_client_apis(token)

    # 7. Configure role claim (replaces groups claim)
    configure_all_role_claims(token, client_uuids)

    # 7.5 Display client secrets for env var configuration
    actual_secret = get_actual_client_secret()
    client_api_secret = get_client_api_secret()
    print("[7.5/8] Client secrets (set env vars)...")
    update_oidc_configs(actual_secret, client_api_secret)
    print()

    # 8. Summary
    print_summary(admin_user, admin_pass, actual_secret)


if __name__ == "__main__":
    main()