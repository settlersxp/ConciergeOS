#!/usr/bin/env python3
"""Configuration constants for Keycloak setup.

Centralizes all configuration values used across the keycloak_setup package.
"""

import os

from rbac_file import load_rbac_routes
from settings import settings


# ------------------------------------------------------------------
# Realm Configuration
# ------------------------------------------------------------------

REALMS = ["testing", "production"]

# ------------------------------------------------------------------
# Client Configuration
# ------------------------------------------------------------------

CLIENT_ID = settings.OIDC_CLIENT_ID

# Second client: service-to-service (Client Credentials Grant)
CLIENT_API_ID = "client-api"

# ------------------------------------------------------------------
# URL Configuration (derived from APP_DOMAIN)
# ------------------------------------------------------------------

APP_DOMAIN = settings.APP_DOMAIN  # e.g., "https://out-customer.com"
OIDC_APP1_REDIRECT_URI = f"{APP_DOMAIN}/app1/oauth2/callback"
OIDC_APP2_REDIRECT_URI = f"{APP_DOMAIN}/app2/oauth2/callback"
POST_LOGOUT_URI = f"{APP_DOMAIN}/"
LOCAL_REDIRECT_URI = "http://localhost:*/*"
LOCAL_WEB_ORIGIN = "http://localhost:*"
DOMAIN_WILD_CARD = f"{APP_DOMAIN}/*"

# ------------------------------------------------------------------
# Role Definitions (loaded from rbac_routes.json)
# ------------------------------------------------------------------


def _load_roles_from_mapping() -> dict[str, str]:
    """Load role definitions from the RBAC mapping file.

    Reads the RBAC routes file (YAML or JSON) via the Pydantic RBACRoutes
    model and extracts the role descriptions.

    Returns
    -------
    dict[str, str]
        {role_name: description} suitable for Keycloak role creation.

    Notes
    -----
    Tries the following locations in order:
    1. MAPPING_FILE environment variable (set by settings.MAPPING_FILE)
    2. rbac_routes.json relative to this script (local dev)
    """
    # Try the configured path first (works inside Docker containers)
    mapping_file = settings.MAPPING_FILE
    if not os.path.exists(mapping_file):
        # Fallback: look for rbac_routes.json next to this script (local dev)
        script_dir = os.path.dirname(os.path.abspath(__file__))
        fallback = os.path.join(script_dir, "..", "rbac_routes.json")
        if os.path.exists(fallback):
            mapping_file = fallback
        else:
            raise FileNotFoundError(
                f"RBAC mapping file not found. Searched:\n"
                f"  1. {settings.MAPPING_FILE} (MAPPING_FILE env var)\n"
                f"  2. {fallback} (next to this script)\n"
                "Set MAPPING_FILE to point to rbac_routes.json."
            )

    routes = load_rbac_routes(mapping_file)
    return routes.role_descriptions()


# Roles are loaded from rbac_routes.json — single source of truth.
# Note: ROLES is loaded lazily to allow imports even when the file is missing.
def get_roles() -> dict[str, str]:
    """Get role definitions, loading from YAML if available."""
    try:
        return _load_roles_from_mapping()
    except FileNotFoundError:
        # Return empty dict if file not found (for testing/development)
        return {}


# Composite role that inherits all granular roles defined in the mapping file.
def get_composite_roles() -> dict[str, list[str]]:
    """Get composite role definitions."""
    roles = get_roles()
    return {
        "full-access": list(roles.keys()),
    }


# Backward compatibility: ROLES and COMPOSITE_ROLES are now functions
# Use get_roles() and get_composite_roles() to access the actual data
ROLES = get_roles  # type: ignore[assignment]
COMPOSITE_ROLES = get_composite_roles  # type: ignore[assignment]

# ------------------------------------------------------------------
# User Definitions
# ------------------------------------------------------------------

USERS = {
    "user1": {
        "password": "password1",
        "roles": ["reservations:view", "guest-search:view"],
    },
    "user2": {
        "password": "password2",
        "roles": ["full-access"],
    },
}

# ------------------------------------------------------------------
# Global Secret Storage (updated during client creation)
# ------------------------------------------------------------------

_actual_client_secret = ""
_client_api_secret = ""