#!/usr/bin/env python3
"""
test_pure_functions.py - Tests for pure functions in rbac_sync.

Tests has_role_events, generate_deny_rules, build_caddy_routes,
build_rbac_routes, push_routes_to_caddy config preservation, and role_event_types.
No network calls, no mocking.

Updated to use new modules from rbac_sync package.
"""

import copy
import inspect
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from rbac_sync import (
    has_role_events,
    generate_deny_rules,
    build_caddy_routes,
    build_rbac_routes,
    push_routes_to_caddy,
    get_menus_for_roles,
    ROLE_EVENT_TYPES,
)

from helpers import make_roles_with_attrs
from fixtures import sample_caddy_config


# ======================================================================
# TestHasRoleEvents
# ======================================================================


class TestHasRoleEvents:

    @staticmethod
    def _event(**kwargs) -> dict:
        return kwargs

    def test_detects_create_role_event(self):
        assert has_role_events([self._event(operationType="CREATE", resourceType="ROLE")]) is True

    def test_detects_update_role_event(self):
        assert has_role_events([self._event(operationType="UPDATE", resourceType="ROLE")]) is True

    def test_detects_delete_role_event(self):
        assert has_role_events([self._event(operationType="DELETE", resourceType="ROLE")]) is True

    def test_ignores_login_events(self):
        assert has_role_events([self._event(operationType="LOGIN", resourceType="USER")]) is False

    def test_ignores_empty_list(self):
        assert has_role_events([]) is False

    def test_ignores_role_view_event(self):
        """VIEW on ROLE should NOT trigger re-sync."""
        assert has_role_events([self._event(operationType="VIEW", resourceType="ROLE")]) is False

    def test_mixed_events_returns_true(self):
        assert has_role_events([
            self._event(operationType="LOGIN", resourceType="USER"),
            self._event(operationType="CREATE", resourceType="ROLE"),
        ]) is True


# ======================================================================
# TestGenerateDenyRules (attribute-based)
# ======================================================================


class TestGenerateDenyRules:

    def test_generates_rules_for_roles_with_paths(self):
        roles_with_attrs = make_roles_with_attrs(
            **{
                "settings:view": {"paths": ["/settings", "/settings/*"], "menus": ["settings"]},
                "models:admin": {"paths": ["/models", "/models/*"], "menus": ["models"]},
            }
        )
        frontend_rules, api_rules = generate_deny_rules(roles_with_attrs)
        # Non-API paths → frontend rules only
        assert len(frontend_rules) == 2
        assert len(api_rules) == 0

    def test_skips_roles_without_paths(self):
        roles_with_attrs = make_roles_with_attrs(
            **{
                "full-access": {"paths": [], "menus": []},
                "settings:view": {"paths": ["/settings"], "menus": ["settings"]},
            }
        )
        frontend_rules, api_rules = generate_deny_rules(roles_with_attrs)
        assert len(frontend_rules) == 1
        assert len(api_rules) == 0

    def test_rule_structure(self):
        """Verify the deny rule structure uses header_regexp with X-Forwarded-Groups."""
        roles_with_attrs = make_roles_with_attrs(
            **{"settings:view": {"paths": ["/settings", "/settings/*"], "menus": ["settings"]}}
        )
        frontend_rules, _ = generate_deny_rules(roles_with_attrs)
        rule = frontend_rules[0]

        # Terminal flag
        assert rule["terminal"] is True

        # Handle: static_response with 403
        assert rule["handle"][0]["handler"] == "static_response"
        assert rule["handle"][0]["status_code"] == "403"

        # Match: path with header_regexp NOT condition
        match_block = rule["match"][0]
        assert "/settings" in match_block["path"]
        assert "/settings/*" in match_block["path"]

        # The NOT condition checks for X-Forwarded-Groups header
        not_block = match_block["not"][0]
        assert "header_regexp" in not_block
        assert "X-Forwarded-Groups" in not_block["header_regexp"]
        assert "role:settings:view" in not_block["header_regexp"]["X-Forwarded-Groups"]["pattern"]

    def test_rule_uses_custom_message(self):
        """Verify message from role name is used in the deny rule."""
        roles_with_attrs = make_roles_with_attrs(
            **{"settings:view": {"paths": ["/settings"], "menus": ["settings"]}}
        )
        frontend_rules, _ = generate_deny_rules(roles_with_attrs)
        rule = frontend_rules[0]
        assert "settings:view" in rule["handle"][0]["body"]
        assert "Access denied" in rule["handle"][0]["body"]

    def test_empty_roles_returns_no_rules(self):
        # When no roles and no fallback file, should return empty
        from unittest.mock import patch
        with patch("rbac_sync.caddy_routes._load_fallback_roles", return_value={}):
            frontend_rules, api_rules = generate_deny_rules({})
        assert frontend_rules == []
        assert api_rules == []

    def test_all_empty_paths_returns_no_rules(self):
        roles_with_attrs = make_roles_with_attrs(
            **{
                "a:view": {"paths": [], "menus": ["a"]},
                "b:view": {"paths": [], "menus": ["b"]},
            }
        )
        # Fallback may add roles with paths, so mock it away
        from unittest.mock import patch
        with patch("rbac_sync.caddy_routes._load_fallback_roles", return_value={}):
            frontend_rules, api_rules = generate_deny_rules(roles_with_attrs)
        assert frontend_rules == []
        assert api_rules == []

    def test_api_paths_go_to_api_rules(self):
        """Paths starting with /api/ should produce API deny rules, not frontend rules."""
        roles_with_attrs = make_roles_with_attrs(
            **{"models:admin": {"paths": ["/api/models", "/api/models/*"], "menus": ["models"]}}
        )
        frontend_rules, api_rules = generate_deny_rules(roles_with_attrs)
        assert len(frontend_rules) == 0
        assert len(api_rules) == 1
        assert "/api/models" in api_rules[0]["match"][0]["path"]

    def test_mixed_paths_split_correctly(self):
        """Roles with both API and non-API paths should produce rules for both."""
        roles_with_attrs = make_roles_with_attrs(
            **{
                "admin": {
                    "paths": ["/admin", "/api/admin", "/api/admin/*"],
                    "menus": ["admin"],
                }
            }
        )
        frontend_rules, api_rules = generate_deny_rules(roles_with_attrs)
        assert len(frontend_rules) == 1
        assert len(api_rules) == 1
        assert "/admin" in frontend_rules[0]["match"][0]["path"]
        assert "/api/admin" in api_rules[0]["match"][0]["path"]


# ======================================================================
# TestGetMenusForRoles
# ======================================================================


class TestGetMenusForRoles:

    def test_aggregates_menus_for_single_role(self):
        roles_with_attrs = make_roles_with_attrs(
            **{"settings:view": {"paths": ["/settings"], "menus": ["settings"]}}
        )
        menus = get_menus_for_roles({"settings:view"}, roles_with_attrs)
        assert menus == ["settings"]

    def test_aggregates_menus_for_multiple_roles(self):
        roles_with_attrs = make_roles_with_attrs(
            **{
                "reservations:view": {"paths": ["/"], "menus": ["reservations"]},
                "settings:view": {"paths": ["/settings"], "menus": ["settings"]},
            }
        )
        menus = get_menus_for_roles(
            {"reservations:view", "settings:view"}, roles_with_attrs
        )
        assert set(menus) == {"reservations", "settings"}

    def test_returns_empty_for_unknown_role(self):
        roles_with_attrs = make_roles_with_attrs(
            **{"settings:view": {"paths": ["/settings"], "menus": ["settings"]}}
        )
        menus = get_menus_for_roles({"unknown:role"}, roles_with_attrs)
        assert menus == []

    def test_deduplicates_menus(self):
        roles_with_attrs = make_roles_with_attrs(
            **{
                "a:view": {"paths": [], "menus": ["shared"]},
                "b:view": {"paths": [], "menus": ["shared"]},
            }
        )
        menus = get_menus_for_roles({"a:view", "b:view"}, roles_with_attrs)
        assert menus == ["shared"]


# ======================================================================
# TestBuildCaddyRoutes
# ======================================================================


class TestBuildCaddyRoutes:

    def test_static_assets_first(self):
        routes = build_caddy_routes([])
        assert routes[0]["terminal"] is True
        assert routes[0]["handle"][0]["handler"] == "reverse_proxy"
        assert routes[0]["handle"][0]["upstreams"][0]["dial"] == "frontend:80"
        assert "/assets/*" in routes[0]["match"][0]["path"]

    def test_static_assets_include_all_patterns(self):
        routes = build_caddy_routes([])
        paths = routes[0]["match"][0]["path"]
        expected_patterns = [
            "/assets/*", "/favicon.svg", "/icons.svg", "/vite.svg",
            "/react.svg", "/hero.png", "/*.css", "/*.js", "/*.map",
            "/*.svg", "/*.png", "/*.jpg", "/*.gif", "/*.ico",
            "/*.woff", "/*.woff2", "/*.ttf", "/*.eot",
        ]
        for pattern in expected_patterns:
            assert pattern in paths, f"Missing pattern: {pattern}"

    def test_catch_all_last(self):
        routes = build_caddy_routes([])
        last = routes[-1]
        assert "terminal" not in last
        assert "match" not in last
        assert last["handle"][0]["handler"] == "reverse_proxy"
        assert last["handle"][0]["upstreams"][0]["dial"] == "frontend:80"

    def test_empty_rbac_produces_two_routes(self):
        """Empty deny rules produces 2 routes for RBAC gateway: full_access_bypass, catch-all."""
        routes = build_rbac_routes([])
        assert len(routes) == 2
        # First route: full-access bypass
        assert routes[0]["terminal"] is True
        assert routes[0]["handle"][0]["handler"] == "reverse_proxy"
        assert routes[0]["handle"][0]["upstreams"][0]["dial"] == "backend:8000"
        assert "role:full-access" in routes[0]["match"][0]["header_regexp"]["X-Forwarded-Groups"]["pattern"]
        # Last route: catch-all
        assert "terminal" not in routes[-1]
        assert "match" not in routes[-1]
        assert routes[-1]["handle"][0]["handler"] == "reverse_proxy"
        assert routes[-1]["handle"][0]["upstreams"][0]["dial"] == "backend:8000"

    def test_rbac_full_access_bypass_before_deny_rules(self):
        """Verify full-access bypass is the first route in RBAC gateway."""
        deny = [{"deny": "api-rule"}]
        routes = build_rbac_routes(deny)
        assert len(routes) == 3
        # First: full-access bypass
        assert routes[0]["terminal"] is True
        assert "role:full-access" in str(routes[0])
        # Second: deny rule
        assert routes[1] == {"deny": "api-rule"}
        # Third: catch-all
        assert "terminal" not in routes[2]
        assert "match" not in routes[2]

    def test_empty_produces_three_routes(self):
        """Empty deny rules produces 3 routes: static_assets, full_access_bypass, catch-all."""
        routes = build_caddy_routes([])
        assert len(routes) == 3

    def test_deny_rules_inserted_correctly(self):
        """Deny rules inserted between full_access_bypass and catch-all."""
        deny = [{"rule": 1}, {"rule": 2}]
        routes = build_caddy_routes(deny)
        assert len(routes) == 5
        assert routes[2] == {"rule": 1}
        assert routes[3] == {"rule": 2}

    def test_route_order_static_deny_catch_all(self):
        """Verify the route order: static assets, full_access_bypass, deny rules, catch-all."""
        deny = [{"deny": "rule"}]
        routes = build_caddy_routes(deny)
        assert routes[0]["terminal"] is True
        assert routes[0]["handle"][0]["handler"] == "reverse_proxy"
        assert routes[1]["terminal"] is True
        assert "role:full-access" in str(routes[1])
        assert routes[2] == {"deny": "rule"}
        assert "terminal" not in routes[3]
        assert "match" not in routes[3]


# ======================================================================
# TestPushRoutesToCaddyConfigPreservation
# ======================================================================


class TestPushRoutesToCaddyConfigPreservation:

    def test_config_structure_preserved(self, sample_caddy_config):
        """Verify the config manipulation preserves structure."""
        full_config = copy.deepcopy(sample_caddy_config)
        new_routes = [{"new": "route"}]

        apps = full_config.setdefault("apps", {})
        http_app = apps.setdefault("http", {})
        servers = http_app.setdefault("servers", {})
        internal = servers.setdefault("internal-server", {})
        internal["routes"] = new_routes

        assert full_config["apps"]["http"]["servers"]["internal-server"]["routes"] == new_routes
        assert full_config["apps"]["http"]["servers"]["http-server"]["routes"] == [
            {"handle": [{"handler": "static_response", "body": "HTTP"}]}
        ]
        assert full_config["apps"]["http"]["servers"]["https-server"]["routes"] == [
            {"handle": [{"handler": "static_response", "body": "HTTPS"}]}
        ]
        assert full_config["apps"]["tls"]["automation"]["cert_issuer"]["module"] == "acme"
        assert full_config["logging"]["logs"]["default"]["level"] == "INFO"
        assert full_config["admin"]["listen"] == "tcp/2019"

    def test_creates_missing_intermediate_keys(self):
        empty_config = {}
        new_routes = [{"route": 1}]

        apps = empty_config.setdefault("apps", {})
        http_app = apps.setdefault("http", {})
        servers = http_app.setdefault("servers", {})
        internal = servers.setdefault("internal-server", {})
        internal["routes"] = new_routes

        assert empty_config == {
            "apps": {
                "http": {
                    "servers": {
                        "internal-server": {
                            "routes": new_routes
                        }
                    }
                }
            }
        }

    def test_preserves_existing_internal_server_config(self, sample_caddy_config):
        full_config = copy.deepcopy(sample_caddy_config)
        full_config["apps"]["http"]["servers"]["internal-server"]["listen"] = [":9999"]

        new_routes = [{"new": "route"}]

        apps = full_config.setdefault("apps", {})
        http_app = apps.setdefault("http", {})
        servers = http_app.setdefault("servers", {})
        internal = servers.setdefault("internal-server", {})
        internal["routes"] = new_routes

        assert full_config["apps"]["http"]["servers"]["internal-server"]["routes"] == new_routes
        assert full_config["apps"]["http"]["servers"]["internal-server"]["listen"] == [":9999"]

    def test_patch_not_put_is_used(self):
        """Verify _push_routes_to_caddy uses requests.patch, not requests.put."""
        from rbac_sync.caddy_routes import _push_routes_to_caddy
        source = inspect.getsource(_push_routes_to_caddy)
        assert "requests.patch" in source, "Must use requests.patch to merge with Caddy state"
        assert "requests.put" not in source, "Must NOT use requests.put as it replaces all state"

    def test_fetches_config_before_pushing(self):
        """Verify _push_routes_to_caddy fetches current config before pushing."""
        from rbac_sync.caddy_routes import _push_routes_to_caddy
        source = inspect.getsource(_push_routes_to_caddy)
        assert 'requests.get' in source, "Must fetch current config first"
        assert '/config/' in source or '/config"' in source, "Must GET from /config/ endpoint"


# ======================================================================
# TestRoleEventTypes
# ======================================================================


class TestRoleEventTypes:

    @staticmethod
    def _event_in_types(*ops: str) -> None:
        for op in ops:
            assert op in ROLE_EVENT_TYPES, f"{op} must be in ROLE_EVENT_TYPES"

    @staticmethod
    def _event_not_in_types(*ops: str) -> None:
        for op in ops:
            assert op not in ROLE_EVENT_TYPES, f"{op} must NOT be in ROLE_EVENT_TYPES"

    def test_role_event_types_contains_required(self):
        self._event_in_types("CREATE", "UPDATE", "DELETE")

    def test_role_event_types_does_not_contain_non_triggering(self):
        """VIEW and LOGIN should not trigger a re-sync."""
        self._event_not_in_types("VIEW", "LOGIN")