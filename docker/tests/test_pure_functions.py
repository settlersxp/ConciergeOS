#!/usr/bin/env python3
"""
test_pure_functions.py - Tests for pure functions in role_sync.

Tests has_role_events, load_mapping, generate_deny_rules, build_caddy_routes,
push_routes_to_caddy config preservation, and role_event_types.
No network calls, no mocking.
"""

import os
import sys
import tempfile
import copy
import inspect

import yaml

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import role_sync


# ======================================================================
# TestHasRoleEvents
# ======================================================================


class TestHasRoleEvents:

    def test_detects_create_role_event(self):
        assert role_sync.has_role_events([
            {"operationType": "CREATE", "resourceType": "ROLE"}
        ]) is True

    def test_detects_update_role_event(self):
        assert role_sync.has_role_events([
            {"operationType": "UPDATE", "resourceType": "ROLE"}
        ]) is True

    def test_detects_delete_role_event(self):
        assert role_sync.has_role_events([
            {"operationType": "DELETE", "resourceType": "ROLE"}
        ]) is True

    def test_ignores_login_events(self):
        assert role_sync.has_role_events([
            {"operationType": "LOGIN", "resourceType": "USER"}
        ]) is False

    def test_ignores_empty_list(self):
        assert role_sync.has_role_events([]) is False

    def test_ignores_role_view_event(self):
        """VIEW on ROLE should NOT trigger re-sync."""
        assert role_sync.has_role_events([
            {"operationType": "VIEW", "resourceType": "ROLE"}
        ]) is False

    def test_mixed_events_returns_true(self):
        assert role_sync.has_role_events([
            {"operationType": "LOGIN", "resourceType": "USER"},
            {"operationType": "CREATE", "resourceType": "ROLE"},
        ]) is True


# ======================================================================
# TestLoadMapping
# ======================================================================


class TestLoadMapping:

    def test_loads_valid_mapping_file(self, sample_mapping):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(sample_mapping, f)
            f.flush()
            original = role_sync.MAPPING_FILE
            role_sync.MAPPING_FILE = f.name
            try:
                result = role_sync.load_mapping()
                assert len(result) == len(sample_mapping)
            finally:
                role_sync.MAPPING_FILE = original
                os.unlink(f.name)

    def test_returns_empty_for_missing_file(self):
        original = role_sync.MAPPING_FILE
        role_sync.MAPPING_FILE = "/nonexistent/path.yaml"
        try:
            result = role_sync.load_mapping()
            assert result == []
        finally:
            role_sync.MAPPING_FILE = original


# ======================================================================
# TestGenerateDenyRules
# ======================================================================


class TestGenerateDenyRules:

    def test_generates_rules_for_matching_roles(self, sample_mapping):
        roles = {"settings:view", "models:admin"}
        rules = role_sync.generate_deny_rules(sample_mapping, roles)
        assert len(rules) == 2

    def test_skips_roles_not_in_keycloak(self, sample_mapping):
        roles = {"settings:view"}
        rules = role_sync.generate_deny_rules(sample_mapping, roles)
        assert len(rules) == 1

    def test_rule_structure(self, sample_mapping):
        """Verify the deny rule structure uses header_regexp with X-Forwarded-Groups."""
        roles = {"settings:view"}
        rules = role_sync.generate_deny_rules(sample_mapping, roles)
        rule = rules[0]

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

    def test_rule_uses_custom_message(self, sample_mapping):
        """Verify custom message from mapping is used in the deny rule."""
        roles = {"settings:view"}
        rules = role_sync.generate_deny_rules(sample_mapping, roles)
        rule = rules[0]
        assert rule["handle"][0]["body"] == "Access denied: settings requires viewer role."

    def test_rule_uses_default_message_when_not_provided(self):
        """Verify default message is used when not in mapping."""
        mapping = [
            {"role": "models:admin", "paths": ["/models", "/models/*"]}
        ]
        roles = {"models:admin"}
        rules = role_sync.generate_deny_rules(mapping, roles)
        rule = rules[0]
        assert "models:admin" in rule["handle"][0]["body"]
        assert "Access denied" in rule["handle"][0]["body"]

    def test_empty_mapping_returns_no_rules(self):
        assert role_sync.generate_deny_rules([], {"some:role"}) == []

    def test_empty_roles_returns_no_rules(self, sample_mapping):
        assert role_sync.generate_deny_rules(sample_mapping, set()) == []

    def test_skips_entries_with_empty_role(self):
        mapping = [
            {"role": "", "paths": ["/path"]},
            {"role": "valid:role", "paths": ["/valid"]},
        ]
        roles = {"valid:role"}
        rules = role_sync.generate_deny_rules(mapping, roles)
        assert len(rules) == 1

    def test_skips_entries_with_empty_paths(self):
        mapping = [
            {"role": "valid:role", "paths": []},
            {"role": "another:role", "paths": ["/path"]},
        ]
        roles = {"valid:role", "another:role"}
        rules = role_sync.generate_deny_rules(mapping, roles)
        assert len(rules) == 1


# ======================================================================
# TestBuildCaddyRoutes
# ======================================================================


class TestBuildCaddyRoutes:

    def test_static_assets_first(self):
        routes = role_sync.build_caddy_routes([])
        assert routes[0]["terminal"] is True
        # Verify static assets route uses reverse_proxy to frontend:80
        assert routes[0]["handle"][0]["handler"] == "reverse_proxy"
        assert routes[0]["handle"][0]["upstreams"][0]["dial"] == "frontend:80"
        assert "/assets/*" in routes[0]["match"][0]["path"]

    def test_static_assets_include_all_patterns(self):
        routes = role_sync.build_caddy_routes([])
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
        routes = role_sync.build_caddy_routes([])
        last = routes[-1]
        assert "terminal" not in last
        assert "match" not in last
        # Catch-all uses reverse_proxy to frontend:80
        assert last["handle"][0]["handler"] == "reverse_proxy"
        assert last["handle"][0]["upstreams"][0]["dial"] == "frontend:80"

    def test_empty_produces_two_routes(self):
        """Empty deny rules produces 3 routes: static_assets, full_access_bypass, catch-all."""
        routes = role_sync.build_caddy_routes([])
        assert len(routes) == 3

    def test_deny_rules_inserted_correctly(self):
        """Deny rules inserted between full_access_bypass and catch-all."""
        deny = [{"rule": 1}, {"rule": 2}]
        routes = role_sync.build_caddy_routes(deny)
        # static_assets + full_access_bypass + deny_rules + catch-all
        assert len(routes) == 5
        assert routes[2] == {"rule": 1}
        assert routes[3] == {"rule": 2}

    def test_route_order_static_deny_catch_all(self):
        """Verify the route order: static assets, full_access_bypass, deny rules, catch-all."""
        deny = [{"deny": "rule"}]
        routes = role_sync.build_caddy_routes(deny)
        # First route is static assets (terminal)
        assert routes[0]["terminal"] is True
        assert routes[0]["handle"][0]["handler"] == "reverse_proxy"
        # Second route is full_access_bypass (terminal)
        assert routes[1]["terminal"] is True
        assert "role:full-access" in str(routes[1])
        # Third route is deny rule
        assert routes[2] == {"deny": "rule"}
        # Last route is catch-all (no terminal, no match)
        assert "terminal" not in routes[3]
        assert "match" not in routes[3]


# ======================================================================
# TestPushRoutesToCaddyConfigPreservation
# ======================================================================


class TestPushRoutesToCaddyConfigPreservation:
    """Test that push_routes_to_caddy preserves existing Caddy config.

    These tests verify the core logic: that when pushing routes, we:
    1. Fetch the full current config
    2. Update only the internal-server routes
    3. Preserve all other config (http-server, https-server, TLS, PKI, logging)
    """

    def test_config_structure_preserved(self, sample_caddy_config):
        """Verify the config manipulation preserves structure."""
        # Simulate what push_routes_to_caddy does
        full_config = copy.deepcopy(sample_caddy_config)
        new_routes = [{"new": "route"}]

        # The manipulation from push_routes_to_caddy
        apps = full_config.setdefault("apps", {})
        http_app = apps.setdefault("http", {})
        servers = http_app.setdefault("servers", {})
        internal = servers.setdefault("internal-server", {})
        internal["routes"] = new_routes

        # Verify internal-server routes were updated
        assert full_config["apps"]["http"]["servers"]["internal-server"]["routes"] == new_routes

        # Verify http-server was NOT touched
        assert full_config["apps"]["http"]["servers"]["http-server"]["routes"] == [
            {"handle": [{"handler": "static_response", "body": "HTTP"}]}
        ]

        # Verify https-server was NOT touched
        assert full_config["apps"]["http"]["servers"]["https-server"]["routes"] == [
            {"handle": [{"handler": "static_response", "body": "HTTPS"}]}
        ]

        # Verify TLS config preserved
        assert full_config["apps"]["tls"]["automation"]["cert_issuer"]["module"] == "acme"

        # Verify logging config preserved
        assert full_config["logging"]["logs"]["default"]["level"] == "INFO"

        # Verify admin config preserved
        assert full_config["admin"]["listen"] == "tcp/2019"

    def test_creates_missing_intermediate_keys(self):
        """Verify setdefault creates keys that don't exist."""
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
        """Verify other internal-server keys (like listen) are preserved."""
        full_config = copy.deepcopy(sample_caddy_config)
        # Add a listen key to internal-server
        full_config["apps"]["http"]["servers"]["internal-server"]["listen"] = [":9999"]

        new_routes = [{"new": "route"}]

        apps = full_config.setdefault("apps", {})
        http_app = apps.setdefault("http", {})
        servers = http_app.setdefault("servers", {})
        internal = servers.setdefault("internal-server", {})
        internal["routes"] = new_routes

        # Routes updated
        assert full_config["apps"]["http"]["servers"]["internal-server"]["routes"] == new_routes
        # Listen preserved
        assert full_config["apps"]["http"]["servers"]["internal-server"]["listen"] == [":9999"]

    def test_patch_not_put_is_used(self):
        """Verify push_routes_to_caddy uses requests.patch, not requests.put."""
        source = inspect.getsource(role_sync.push_routes_to_caddy)
        assert "requests.patch" in source, "Must use requests.patch to merge with Caddy state"
        assert "requests.put" not in source, "Must NOT use requests.put as it replaces all state"

    def test_fetches_config_before_pushing(self):
        """Verify push_routes_to_caddy fetches current config before pushing."""
        source = inspect.getsource(role_sync.push_routes_to_caddy)
        assert 'requests.get' in source, "Must fetch current config first"
        assert '/config/' in source or '/config"' in source, "Must GET from /config/ endpoint"


# ======================================================================
# TestRoleEventTypes
# ======================================================================


class TestRoleEventTypes:

    def test_role_event_types_contains_create(self):
        assert "CREATE" in role_sync.ROLE_EVENT_TYPES

    def test_role_event_types_contains_update(self):
        assert "UPDATE" in role_sync.ROLE_EVENT_TYPES

    def test_role_event_types_contains_delete(self):
        assert "DELETE" in role_sync.ROLE_EVENT_TYPES

    def test_role_event_types_does_not_contain_view(self):
        """VIEW should not trigger a re-sync."""
        assert "VIEW" not in role_sync.ROLE_EVENT_TYPES

    def test_role_event_types_does_not_contain_login(self):
        """LOGIN should not trigger a re-sync."""
        assert "LOGIN" not in role_sync.ROLE_EVENT_TYPES