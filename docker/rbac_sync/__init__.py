"""RBAC Sync Package for ConciergeOS.

This package provides modular functionality for synchronizing RBAC routes
between Keycloak, Caddy, and YAML configuration files.

Modules:
    - config: Configuration constants and settings
    - role_operations: Keycloak role CRUD operations
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

from .role_operations import (
    sync_all_roles,
    print_summary,
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
    push_routes_to_caddy,
    verify_caddy_routes,
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
    # Role Operations
    "sync_all_roles",
    "print_summary",
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
    "push_routes_to_caddy",
    "verify_caddy_routes",
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
]