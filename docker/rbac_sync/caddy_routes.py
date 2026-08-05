"""Caddy Route Generation module.

Handles generating Caddy deny rules from Keycloak role attributes
and pushing routes to both the main Caddy (internal-server) and
the RBAC gateway (caddy-rbac) via their Admin APIs.
"""

import json
import logging
from pathlib import Path

import requests

from .config import CADDY_ADMIN_URL, CADDY_RBAC_ADMIN_URL, RBAC_ROUTES_FILE

logger = logging.getLogger(__name__)

# Paths that are API endpoints (go through the RBAC gateway).
# These are the paths from rbac_routes.json that start with /api/.
_API_PATH_PREFIXES = ("/api/",)


def _is_api_path(path: str) -> bool:
    """Return True if *path* is a backend API path.

    API paths are enforced by the caddy-rbac gateway (sits between
    oauth2-proxy and the backend).  All other paths are enforced
    by the main Caddy internal-server.
    """
    return any(path.startswith(prefix) for prefix in _API_PATH_PREFIXES)


def _load_fallback_roles() -> dict[str, dict[str, list[str]]]:
    """Load role path/menus from rbac_routes.json as fallback.

    Returns:
        Dictionary mapping role names to their attributes (paths, menus)
    """
    fallback: dict[str, dict[str, list[str]]] = {}
    path = Path(RBAC_ROUTES_FILE)
    if path.exists():
        try:
            with open(path) as f:
                entries = json.load(f)
            for entry in entries:
                role = entry.get("role", "")
                paths = entry.get("paths", [])
                # Extract menu hints from message if available
                message = entry.get("message", "")
                fallback[role] = {"paths": paths, "menus": []}
            logger.info("Loaded %d role(s) from fallback file %s", len(fallback), RBAC_ROUTES_FILE)
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning("Failed to parse %s: %s", RBAC_ROUTES_FILE, e)
    else:
        logger.debug("Fallback file not found: %s", RBAC_ROUTES_FILE)
    return fallback


def generate_deny_rules(roles_with_attrs: dict[str, dict[str, list[str]]]) -> tuple[list[dict], list[dict]]:
    """Generate Caddy deny rules from role attributes fetched from Keycloak.

    Each role's 'paths' attribute is used to create a deny rule.
    If Keycloak roles lack path attributes, falls back to rbac_routes.json.
    Rules are split into two lists:
      - frontend rules → pushed to the main Caddy internal-server
      - API rules      → pushed to the caddy-rbac gateway

    Args:
        roles_with_attrs: Dictionary mapping role names to their attributes

    Returns:
        Tuple of (frontend_deny_rules, api_deny_rules)
    """
    # Check if any roles have paths from Keycloak
    has_keycloak_paths = any(attrs.get("paths") for attrs in roles_with_attrs.values())

    if not has_keycloak_paths:
        # Fall back to rbac_routes.json
        fallback = _load_fallback_roles()
        if fallback:
            roles_with_attrs = {**roles_with_attrs, **fallback}
        else:
            logger.warning("No path attributes in Keycloak and no fallback file found")

    frontend_rules: list[dict] = []
    api_rules: list[dict] = []

    for role_name, attrs in roles_with_attrs.items():
        paths = attrs.get("paths", [])
        if not paths:
            continue

        message = f"Access denied: this resource requires the {role_name} role."

        # Split paths into frontend vs API
        frontend_paths = [p for p in paths if not _is_api_path(p)]
        api_paths = [p for p in paths if _is_api_path(p)]

        # Build frontend deny rule (if there are frontend paths)
        if frontend_paths:
            rule = {
                "handle": [
                    {
                        "handler": "static_response",
                        "status_code": "403",
                        "body": message,
                    }
                ],
                "match": [
                    {
                        "path": frontend_paths,
                        "not": [
                            {
                                "header_regexp": {
                                    "X-Forwarded-Groups": {
                                        "pattern": f".*role:{role_name}.*"
                                    }
                                }
                            }
                        ],
                    }
                ],
                "terminal": True,
            }
            frontend_rules.append(rule)
            logger.info(
                "Generated frontend deny rule for role '%s' on %d path(s): %s",
                role_name, len(frontend_paths), frontend_paths
            )

        # Build API deny rule (if there are API paths)
        if api_paths:
            rule = {
                "handle": [
                    {
                        "handler": "static_response",
                        "status_code": "403",
                        "body": message,
                    }
                ],
                "match": [
                    {
                        "path": api_paths,
                        "not": [
                            {
                                "header_regexp": {
                                    "X-Forwarded-Groups": {
                                        "pattern": f".*role:{role_name}.*"
                                    }
                                }
                            }
                        ],
                    }
                ],
                "terminal": True,
            }
            api_rules.append(rule)
            logger.info(
                "Generated API deny rule for role '%s' on %d path(s): %s",
                role_name, len(api_paths), api_paths
            )

    return frontend_rules, api_rules


def get_menus_for_roles(
    role_names: set[str],
    roles_with_attrs: dict[str, dict[str, list[str]]],
) -> list[str]:
    """Aggregate menu items for a set of role names.

    Args:
        role_names: Set of role names to aggregate menus for
        roles_with_attrs: Dictionary mapping role names to their attributes

    Returns:
        Sorted list of unique menu items
    """
    menus: set[str] = set()
    for role_name in role_names:
        attrs = roles_with_attrs.get(role_name, {})
        for menu in attrs.get("menus", []):
            menus.add(menu)
    return sorted(menus)


def build_caddy_routes(deny_rules: list[dict]) -> list[dict]:
    """Build the full internal-server routes array.

    Combines static assets route, full access bypass, deny rules,
    and a catch-all route into a complete Caddy configuration.

    Args:
        deny_rules: List of frontend deny rules

    Returns:
        Complete list of Caddy routes in order
    """
    static_assets_route = {
        "handle": [
            {
                "handler": "reverse_proxy",
                "upstreams": [{"dial": "frontend:80"}],
            }
        ],
        "match": [
            {
                "path": [
                    "/assets/*",
                    "/favicon.svg",
                    "/icons.svg",
                    "/vite.svg",
                    "/react.svg",
                    "/hero.png",
                    "/*.css",
                    "/*.js",
                    "/*.map",
                    "/*.svg",
                    "/*.png",
                    "/*.jpg",
                    "/*.gif",
                    "/*.ico",
                    "/*.woff",
                    "/*.woff2",
                    "/*.ttf",
                    "/*.eot",
                ]
            }
        ],
        "terminal": True,
    }

    full_access_bypass_route = {
        "handle": [
            {
                "handler": "reverse_proxy",
                "upstreams": [{"dial": "frontend:80"}],
            }
        ],
        "match": [
            {
                "header_regexp": {
                    "X-Forwarded-Groups": {
                        "pattern": ".*role:full-access.*"
                    }
                }
            }
        ],
        "terminal": True,
    }

    catch_all_route = {
        "handle": [
            {
                "handler": "reverse_proxy",
                "upstreams": [{"dial": "frontend:80"}],
            }
        ],
    }

    return [static_assets_route, full_access_bypass_route] + deny_rules + [catch_all_route]


def build_rbac_routes(deny_rules: list[dict]) -> list[dict]:
    """Build the full caddy-rbac gateway routes array.

    Order: full-access bypass → deny rules → catch-all.
    The full-access bypass ensures users with the 'full-access' role
    can reach any API endpoint without being blocked by deny rules.

    Args:
        deny_rules: List of API deny rules

    Returns:
        Complete list of RBAC gateway routes in order
    """
    full_access_bypass_route = {
        "handle": [
            {
                "handler": "reverse_proxy",
                "upstreams": [{"dial": "backend:8000"}],
            }
        ],
        "match": [
            {
                "header_regexp": {
                    "X-Forwarded-Groups": {
                        "pattern": ".*role:full-access.*"
                    }
                }
            }
        ],
        "terminal": True,
    }

    catch_all_route = {
        "handle": [
            {
                "handler": "reverse_proxy",
                "upstreams": [{"dial": "backend:8000"}],
            }
        ],
    }

    return [full_access_bypass_route] + deny_rules + [catch_all_route]


def _push_routes_to_caddy(admin_url: str, routes: list[dict], server_name: str) -> bool:
    """Push routes to a specific Caddy instance.

    Args:
        admin_url: Caddy Admin API URL
        routes: List of route configurations to push
        server_name: Name of the Caddy server for logging

    Returns:
        True if successful, False otherwise
    """
    resp = requests.get(
        f"{admin_url}/config/",
        headers={"Content-Type": "application/json"},
    )
    if resp.status_code != 200:
        logger.error(
            "Failed to fetch current Caddy config from %s: HTTP %d, response: %s",
            admin_url, resp.status_code, resp.text
        )
        return False

    full_config = resp.json()
    logger.debug("Fetched current Caddy config from %s", admin_url)

    apps = full_config.setdefault("apps", {})
    http_app = apps.setdefault("http", {})
    servers = http_app.setdefault("servers", {})
    server = servers.setdefault(server_name, {})
    server["routes"] = routes

    resp = requests.patch(
        f"{admin_url}/config",
        json=full_config,
        headers={"Content-Type": "application/json"},
    )

    if resp.status_code == 200:
        logger.info(
            "Routes pushed to %s (%s) successfully (%d total routes)",
            server_name, admin_url, len(routes)
        )
        return True
    else:
        logger.error(
            "Failed to push routes to %s (%s): HTTP %d, response: %s",
            server_name, admin_url, resp.status_code, resp.text
        )
        return False


def push_routes_to_caddy(frontend_routes: list[dict], api_routes: list[dict]) -> bool:
    """Push the updated routes to both Caddy instances.

    Args:
        frontend_routes: Routes for the main Caddy internal-server
        api_routes: Routes for the caddy-rbac gateway

    Returns:
        True if both pushes succeed, False otherwise
    """
    success = True

    # Push frontend routes to main Caddy
    if not _push_routes_to_caddy(CADDY_ADMIN_URL, frontend_routes, "internal-server"):
        success = False

    # Push API routes to RBAC gateway (Caddy auto-names as srv0)
    if not _push_routes_to_caddy(CADDY_RBAC_ADMIN_URL, api_routes, "srv0"):
        success = False

    return success


def verify_caddy_routes() -> list[dict]:
    """Read current routes from the main Caddy for verification/debugging.

    Returns:
        List of current routes, or empty list if failed
    """
    resp = requests.get(
        f"{CADDY_ADMIN_URL}/config/apps/http/servers/internal-server/routes"
    )
    if resp.status_code == 200:
        return resp.json()
    return []


def verify_rbac_routes() -> list[dict]:
    """Read current routes from the RBAC gateway for verification/debugging.

    Returns:
        List of current routes, or empty list if failed
    """
    resp = requests.get(
        f"{CADDY_RBAC_ADMIN_URL}/config/apps/http/servers/srv0/routes"
    )
    if resp.status_code == 200:
        return resp.json()
    return []
