#!/usr/bin/env python3
"""Summary and main entry point for Keycloak setup.

Handles printing setup summaries and orchestrating the full setup process.
"""

import argparse
import logging

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

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Summary Printing
# ------------------------------------------------------------------


def print_summary(admin_user: str, admin_pass: str, actual_secret: str) -> None:
    """Print a summary of the setup."""
    logger.info("=== Setup Complete ===")
    logger.info("")
    logger.info("Realms created: %s", ", ".join(REALMS))
    logger.info("")
    logger.info("Roles created:")
    for role_name, description in get_roles().items():
        logger.info("  %s: %s", role_name, description)
    for composite_name, sub_roles in get_composite_roles().items():
        logger.info("  %s: (composite of %d roles)", composite_name, len(sub_roles))
    logger.info("")
    logger.info("Users per realm:")
    for username, config in USERS.items():
        role_list = ", ".join(config["roles"])
        logger.info("  %s (password: %s) → roles: %s", username, config["password"], role_list)
    logger.info("")
    logger.info("Client: %s (confidential, PKCE enabled)", CLIENT_ID)
    logger.info("Client Secret: %s", actual_secret)
    logger.info("Redirect URIs:")
    logger.info("  App1:     %s/app1/oauth2/callback", settings.APP_DOMAIN)
    logger.info("  App2:     %s/app2/oauth2/callback", settings.APP_DOMAIN)
    logger.info("")
    logger.info("Client: %s (confidential, Client Credentials Grant)", CLIENT_API_ID)
    logger.info("Client Secret: %s", get_client_api_secret())
    logger.info("  Grant Type: client_credentials (machine-to-machine)")
    logger.info("  Service Accounts: enabled")
    logger.info("")
    logger.info("Keycloak Admin Console:")
    logger.info("  URL: %s/admin", settings.KEYCLOAK_URL)
    logger.info("  Login: %s / %s", admin_user, admin_pass)
    logger.info("")
    logger.info("Access Control (Role-Based):")
    logger.info("  - Roles are extracted from access token by oauth2-proxy")
    logger.info("  - X-Forwarded-Groups header contains 'role:<name>' values")
    logger.info("  - Caddy enforces path-level access via header_regexp rules")
    logger.info("  - Role sync service auto-propagates role changes to Caddy")
    logger.info("")


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

    logger.info("=== Keycloak Setup for ConciergeOS ===")
    logger.info("Connecting to: %s", settings.KEYCLOAK_URL)
    logger.info("")

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
    logger.info("[7.5/8] Client secrets (set env vars)...")
    update_oidc_configs(actual_secret, client_api_secret)
    logger.info("")

    # 8. Summary
    print_summary(admin_user, admin_pass, actual_secret)


if __name__ == "__main__":
    main()