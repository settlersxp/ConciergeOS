#!/usr/bin/env python3
"""Keycloak Setup Package for ConciergeOS.

This package provides a modular library for provisioning Keycloak realms,
users, roles, and client configurations.

Usage:
    # Run the full setup
    python -m keycloak_setup

    # Or import individual modules for custom workflows
    from keycloak_setup.realms import create_realms
    from keycloak_setup.roles import create_all_roles
    from keycloak_setup.users import create_all_users
    from keycloak_setup.assignments import assign_all_users_to_roles
    from keycloak_setup.clients import create_all_clients
    from keycloak_setup.claims import configure_all_role_claims
    from keycloak_setup.env_update import update_oidc_configs
    from keycloak_setup.summary import print_summary
"""

from .assignments import assign_all_users_to_roles, assign_user_to_roles
from .claims import configure_all_role_claims, configure_role_claim
from .clients import (
    create_all_client_apis,
    create_all_clients,
    create_client,
    create_client_api,
    get_actual_client_secret,
    get_client_api_secret,
)
from .config import (
    APP_DOMAIN,
    CLIENT_API_ID,
    CLIENT_ID,
    COMPOSITE_ROLES,
    DOMAIN_WILD_CARD,
    LOCAL_REDIRECT_URI,
    LOCAL_WEB_ORIGIN,
    OIDC_APP1_REDIRECT_URI,
    OIDC_APP2_REDIRECT_URI,
    POST_LOGOUT_URI,
    REALMS,
    ROLES,
    USERS,
)
from .env_update import update_oidc_configs
from .realms import create_realms
from .roles import (
    create_all_roles,
    create_composite_role,
    create_role,
    create_role_with_attributes,
    update_role_attributes,
    sync_role_to_keycloak,
    print_summary as print_role_sync_summary,
)
from .summary import print_summary
from .users import create_all_users, create_user

__all__ = [
    # Main orchestration functions
    "create_realms",
    "create_all_roles",
    "create_all_users",
    "assign_all_users_to_roles",
    "create_all_clients",
    "create_all_client_apis",
    "configure_all_role_claims",
    "update_oidc_configs",
    "print_summary",
    # Individual entity functions
    "create_role",
    "create_composite_role",
    "create_role_with_attributes",
    "update_role_attributes",
    "sync_role_to_keycloak",
    "create_user",
    "assign_user_to_roles",
    "create_client",
    "create_client_api",
    "configure_role_claim",
    # Role sync summary (renamed to avoid conflict with other print_summary)
    "print_role_sync_summary",
    # Configuration exports
    "REALMS",
    "ROLES",
    "COMPOSITE_ROLES",
    "USERS",
    "CLIENT_ID",
    "CLIENT_API_ID",
    "APP_DOMAIN",
    "OIDC_APP1_REDIRECT_URI",
    "OIDC_APP2_REDIRECT_URI",
    "POST_LOGOUT_URI",
    "LOCAL_REDIRECT_URI",
    "LOCAL_WEB_ORIGIN",
    "DOMAIN_WILD_CARD",
    # Secret accessors
    "get_actual_client_secret",
    "get_client_api_secret",
]