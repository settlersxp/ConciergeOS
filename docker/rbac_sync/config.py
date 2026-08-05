"""Configuration constants for RBAC sync operations.

Centralizes all configuration values used across the rbac_sync package.
"""

from pathlib import Path

from settings import settings

# Path to the RBAC routes file (relative to docker directory)
RBAC_ROUTES_FILE = Path(__file__).parent.parent / "rbac_routes.json"

# Admin events we care about
ROLE_EVENT_TYPES = ["CREATE", "UPDATE", "DELETE"]
USER_EVENT_TYPES = ["DELETE"]
SESSION_EVENT_TYPES = ["DELETE"]

# Session configuration
SESSION_COOKIE_NAME = settings.SESSION_COOKIE_NAME
SESSION_KEY_PREFIX = SESSION_COOKIE_NAME + "-"  # e.g., "_oauth2_proxy-"

# Service URLs (loaded from shared settings module)
KEYCLOAK_URL = settings.KEYCLOAK_URL
KEYCLOAK_REALM = settings.KEYCLOAK_REALM
CADDY_ADMIN_URL = settings.CADDY_ADMIN_URL
VALKEY_URL = settings.VALKEY_URL

# Sync configuration
SYNC_INTERVAL = settings.SYNC_INTERVAL