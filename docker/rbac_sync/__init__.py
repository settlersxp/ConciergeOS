"""RBAC Sync Package for ConciergeOS.

This package provides modular functionality for synchronizing RBAC routes
between Keycloak, Caddy, and YAML configuration files.

Architecture:
    This package depends on keycloak_setup for all Keycloak CRUD operations.
    All Keycloak role/user management goes through keycloak_setup.roles,
    keycloak_setup.users, etc. — this package only handles sync orchestration,
    Caddy route generation, and session invalidation.

Modules:
    - config: Configuration constants and settings
    - role_operations: Adapter that bridges rbac_sync to keycloak_setup.roles
    - routes_persistence: Routes file parsing and persistence
    - caddy_routes: Caddy route generation and pushing
    - event_polling: Keycloak admin event polling
    - session_management: Valkey session invalidation and event persistence
    - sync_orchestrator: Main sync logic and service orchestration
"""

from .config import (
    KEYCLOAK_URL,
    KEYCLOAK_REALM,
    CADDY_ADMIN_URL,
    SYNC_INTERVAL,
    VALKEY_URL,
    SESSION_COOKIE_NAME,
    SESSION_KEY_PREFIX,
    RBAC_ROUTES_FILE,
    ROLE_EVENT_TYPES,
    USER_EVENT_TYPES,
    SESSION_EVENT_TYPES,
)

# ── Keycloak Setup Dependency ────────────────────────────────────────
# All Keycloak CRUD operations are delegated to keycloak_setup.
# This section re-exports the primitives used by rbac_sync for convenience.
from keycloak_setup.roles import (
    list_roles,
    list_roles_with_attrs,
    upsert_role_with_attributes,
    delete_role,
    sync_role_to_keycloak,
)

from .routes_persistence import (
    parse_rbac_routes,
    load_existing_rbac_routes,
    convert_keycloak_attrs_to_route_format,
    write_rbac_routes_file,
    sync_rbac_routes,
)

from .caddy_routes import (
    generate_deny_rules,
    get_menus_for_roles,
    build_caddy_routes,
    build_rbac_routes,
    push_routes_to_caddy,
    verify_caddy_routes,
    verify_rbac_routes,
)

from .event_polling import (
    poll_admin_events,
    has_role_events,
    has_user_delete_events,
)

from .session_management import (
    invalidate_all_sessions,
    load_sync_timestamp,
    save_sync_timestamp,
    sync_is_current,
    load_seen_ids,
    save_seen_ids,
    filter_new_events,
    collect_event_ids,
)

from .sync_orchestrator import (
    initial_sync,
    poll_and_sync,
    wait_for_dependencies,
    run_sync_service,
)

from .role_operations import (
    sync_all_roles,
)

__all__ = [
    # Config
    "KEYCLOAK_URL",
    "KEYCLOAK_REALM",
    "CADDY_ADMIN_URL",
    "SYNC_INTERVAL",
    "VALKEY_URL",
    "SESSION_COOKIE_NAME",
    "SESSION_KEY_PREFIX",
    "RBAC_ROUTES_FILE",
    "ROLE_EVENT_TYPES",
    "USER_EVENT_TYPES",
    "SESSION_EVENT_TYPES",
    # Keycloak Setup Dependency (re-exported from keycloak_setup.roles)
    "list_roles",
    "list_roles_with_attrs",
    "upsert_role_with_attributes",
    "delete_role",
    "sync_role_to_keycloak",
    # RBAC Persistence
    "parse_rbac_routes",
    "load_existing_rbac_routes",
    "convert_keycloak_attrs_to_route_format",
    "write_rbac_routes_file",
    "sync_rbac_routes",
    # Caddy Routes
    "generate_deny_rules",
    "get_menus_for_roles",
    "build_caddy_routes",
    "build_rbac_routes",
    "push_routes_to_caddy",
    "verify_caddy_routes",
    "verify_rbac_routes",
    # Event Polling
    "poll_admin_events",
    "has_role_events",
    "has_user_delete_events",
    # Session Management
    "invalidate_all_sessions",
    "load_sync_timestamp",
    "save_sync_timestamp",
    "sync_is_current",
    "load_seen_ids",
    "save_seen_ids",
    "filter_new_events",
    "collect_event_ids",
    # Sync Orchestrator
    "initial_sync",
    "poll_and_sync",
    "wait_for_dependencies",
    "run_sync_service",
    # Role Operations
    "sync_all_roles",
]
