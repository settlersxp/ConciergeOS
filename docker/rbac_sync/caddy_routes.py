"""Caddy Route Generation module.

Handles generating Caddy deny rules from Keycloak role attributes
and pushing routes to Caddy via the Admin API.
"""

import logging

import requests

from .config import CADDY_ADMIN_URL

logger = logging.getLogger(__name__)


def generate_deny_rules(roles_with_attrs: dict[str, dict[str, list[str]]]) -> list[dict]:
    """Generate Caddy deny rules from role attributes fetched from Keycloak.

    Each role's 'paths' attribute is used to create a deny rule.

    Args:
        roles_with_attrs: Dictionary mapping role names to their attributes

    Returns:
        List of Caddy deny rule configurations
    """
    deny_rules = []

    for role_name, attrs in roles_with_attrs.items():
        paths = attrs.get("paths", [])
        if not paths:
            continue

        message = f"Access denied: this resource requires the {role_name} role."

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
                    "path": paths,
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
        deny_rules.append(rule)
        logger.info(
            "Generated deny rule for role '%s' on %d path(s): %s",
            role_name, len(paths), paths
        )

    return deny_rules


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
        deny_rules: List of deny rules generated from role attributes

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


def push_routes_to_caddy(routes: list[dict]) -> bool:
    """Push the updated routes to Caddy via the Admin API.

    Args:
        routes: List of route configurations to push

    Returns:
        True if successful, False otherwise
    """
    resp = requests.get(
        f"{CADDY_ADMIN_URL}/config/",
        headers={"Content-Type": "application/json"},
    )
    if resp.status_code != 200:
        logger.error(
            "Failed to fetch current Caddy config: HTTP %d, response: %s",
            resp.status_code, resp.text
        )
        return False

    full_config = resp.json()
    logger.debug("Fetched current Caddy config from %s", CADDY_ADMIN_URL)

    apps = full_config.setdefault("apps", {})
    http_app = apps.setdefault("http", {})
    servers = http_app.setdefault("servers", {})
    internal = servers.setdefault("internal-server", {})
    internal["routes"] = routes

    resp = requests.patch(
        f"{CADDY_ADMIN_URL}/config",
        json=full_config,
        headers={"Content-Type": "application/json"},
    )

    if resp.status_code == 200:
        logger.info("Routes pushed to Caddy successfully (%d total routes)", len(routes))
        return True
    else:
        logger.error(
            "Failed to push routes to Caddy: HTTP %d, response: %s",
            resp.status_code, resp.text
        )
        return False


def verify_caddy_routes() -> list[dict]:
    """Read current routes from Caddy for verification/debugging.

    Returns:
        List of current routes, or empty list if failed
    """
    resp = requests.get(
        f"{CADDY_ADMIN_URL}/config/apps/http/servers/internal-server/routes"
    )
    if resp.status_code == 200:
        return resp.json()
    return []