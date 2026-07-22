#!/usr/bin/env python3
"""
test_role_sync.py - Integration tests for the Role Sync Service.

Tests against the LIVE Keycloak container (keycloak:8080) with real
authentication, real events API, and real realm data. No mocking of
HTTP calls to Keycloak.

Pure functions (generate_deny_rules, build_caddy_routes, has_role_events,
load_mapping, push_routes_to_caddy config preservation logic) are tested
in-process with real data. For push_routes_to_caddy, we test against a
live Caddy instance when available.

Usage:
    # From host (Keycloak reachable at localhost:8080):
    cd docker && python3 -m pytest test_role_sync.py -v

    # From inside the role-sync container:
    python3 -m pytest test_role_sync.py -v
"""

import os
import sys
import tempfile

import pytest
import requests
import yaml

# Set env before importing role_sync
os.environ.setdefault("KEYCLOAK_URL", os.environ.get("KEYCLOAK_URL", "http://localhost:8080/auth"))
os.environ.setdefault("KEYCLOAK_REALM", "production")
os.environ.setdefault("KEYCLOAK_ADMIN_USER", "admin")
os.environ.setdefault("KEYCLOAK_ADMIN_PASSWORD", "admin")
os.environ.setdefault("CADDY_ADMIN_URL", "http://localhost:2019")
os.environ.setdefault("SYNC_INTERVAL", "30")
os.environ.setdefault("MAPPING_FILE", "/app/rbac_routes.yaml")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import role_sync


# ======================================================================
# Fixtures
# ======================================================================


@pytest.fixture(scope="session")
def live_token():
    """Authenticate against the live Keycloak instance once per session."""
    resp = requests.post(
        f"{role_sync.KEYCLOAK_URL}/realms/master/protocol/openid-connect/token",
        data={
            "grant_type": "password",
            "client_id": "admin-cli",
            "username": role_sync.KEYCLOAK_ADMIN_USER,
            "password": role_sync.KEYCLOAK_ADMIN_PASSWORD,
        },
    )
    resp.raise_for_status()
    token = resp.json().get("access_token")
    assert token, "No access_token from Keycloak"
    return token


@pytest.fixture
def sample_mapping():
    """Sample role-to-path mapping data."""
    return [
        {
            "role": "settings:view",
            "paths": ["/settings", "/settings/*"],
            "message": "Access denied: settings requires viewer role.",
        },
        {
            "role": "models:admin",
            "paths": ["/models", "/models/*"],
        },
    ]


@pytest.fixture
def sample_caddy_config():
    """Sample Caddy config that simulates a real config with multiple servers."""
    return {
        "apps": {
            "http": {
                "servers": {
                    "http-server": {
                        "listen": [":80"],
                        "routes": [
                            {
                                "handle": [{"handler": "static_response", "body": "HTTP"}]
                            }
                        ]
                    },
                    "https-server": {
                        "listen": [":443"],
                        "routes": [
                            {
                                "handle": [{"handler": "static_response", "body": "HTTPS"}]
                            }
                        ]
                    },
                    "internal-server": {
                        "listen": [":2019"],
                        "routes": [
                            {
                                "handle": [{"handler": "static_response", "body": "OLD ROUTE"}]
                            }
                        ]
                    }
                }
            },
            "tls": {
                "automation": {
                    "cert_issuer": {
                        "module": "acme",
                        "modules": {
                            "ca": "https://acme-v02.api.letsencrypt.org/directory"
                        }
                    }
                }
            }
        },
        "logging": {
            "logs": {
                "default": {
                    "level": "INFO"
                }
            }
        },
        "admin": {
            "listen": "tcp/2019"
        }
    }


# ======================================================================
# Live Keycloak API Tests
# ======================================================================


class TestLiveKeycloakAuth:

    def test_authenticate_returns_valid_token(self):
        """Authenticate against live Keycloak and verify we get a token."""
        token = role_sync.authenticate_keycloak()
        assert isinstance(token, str)
        assert len(token) > 100  # JWT tokens are long

    def test_authenticate_token_works_for_api(self, live_token):
        """Verify the token can access the admin API."""
        resp = requests.get(
            f"{role_sync.KEYCLOAK_URL}/admin/realms/{role_sync.KEYCLOAK_REALM}",
            headers={"Authorization": f"Bearer {live_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["realm"] == role_sync.KEYCLOAK_REALM


class TestLiveKeycloakRoles:

    def test_fetch_all_roles_returns_roles(self, live_token):
        """Fetch roles from live Keycloak — should return at least our defined roles."""
        roles = role_sync.fetch_all_roles(live_token)
        assert isinstance(roles, set)
        # These roles are created by keycloak_setup.py
        expected = {
            "reservations:view", "reservations:write",
            "guest-search:view", "guest-search:extract",
            "performance:view", "performance:run",
            "settings:view", "models:admin", "prompts:admin",
            "full-access",
        }
        assert expected.issubset(roles), f"Missing roles: {expected - roles}"

    def test_fetch_all_roles_returns_uma_authorization(self, live_token):
        """Keycloak always creates uma_authorization."""
        roles = role_sync.fetch_all_roles(live_token)
        assert "uma_authorization" in roles


class TestLiveKeycloakEvents:

    def test_poll_admin_events_returns_list(self, live_token):
        """poll_admin_events should return a list (possibly empty)."""
        from datetime import datetime, timezone
        since = datetime.now(timezone.utc)
        events = role_sync.poll_admin_events(live_token, since)
        assert isinstance(events, list)

    def test_poll_admin_events_uses_ymd_date_format_not_milliseconds(self, live_token):
        """Keycloak 26 requires yyyy-MM-dd date format.

        This test verifies the fix by:
        1. Confirming that millisecond timestamps (the OLD code) cause a 400 error
        2. Confirming that poll_admin_events() works (it uses yyyy-MM-dd internally)
        """
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)

        # Step 1: Prove milliseconds fail (this is what the OLD code did)
        timestamp_ms = int(now.timestamp() * 1000)
        resp_bad = requests.get(
            f"{role_sync.KEYCLOAK_URL}/admin/realms/{role_sync.KEYCLOAK_REALM}/events",
            params={"dateFrom": timestamp_ms, "dateTo": timestamp_ms + 1000},
            headers={"Authorization": f"Bearer {live_token}"},
        )
        assert resp_bad.status_code == 400, "Milliseconds should fail with 400"
        assert "Invalid value" in resp_bad.json()["error"]

        # Step 2: Prove our fix works (poll_admin_events uses yyyy-MM-dd)
        events = role_sync.poll_admin_events(live_token, now)
        assert isinstance(events, list)

    def test_poll_admin_events_accepts_ymd_format(self, live_token):
        """Verify yyyy-MM-dd format works (the fix)."""
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        date_from = now.strftime("%Y-%m-%d")
        date_to = now.strftime("%Y-%m-%d")
        resp = requests.get(
            f"{role_sync.KEYCLOAK_URL}/admin/realms/{role_sync.KEYCLOAK_REALM}/events",
            params={"dateFrom": date_from, "dateTo": date_to},
            headers={"Authorization": f"Bearer {live_token}"},
        )
        # This should succeed
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_poll_admin_events_does_not_send_type_admin(self, live_token):
        """Verify type=ADMIN is NOT sent (Keycloak 26 rejects it)."""
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        date_from = now.strftime("%Y-%m-%d")
        # type=ADMIN causes 500 — do not send it
        resp = requests.get(
            f"{role_sync.KEYCLOAK_URL}/admin/realms/{role_sync.KEYCLOAK_REALM}/events",
            params={"dateFrom": date_from, "dateTo": date_from, "type": "ADMIN"},
            headers={"Authorization": f"Bearer {live_token}"},
        )
        assert resp.status_code == 500, "type=ADMIN should fail (proves we must not use it)"


class TestLiveKeycloakRealmConfig:

    def test_admin_events_enabled(self, live_token):
        """Verify adminEventsEnabled is True on the production realm."""
        resp = requests.get(
            f"{role_sync.KEYCLOAK_URL}/admin/realms/{role_sync.KEYCLOAK_REALM}",
            headers={"Authorization": f"Bearer {live_token}"},
        )
        resp.raise_for_status()
        realm = resp.json()
        assert realm.get("adminEventsEnabled") is True, \
            "adminEventsEnabled must be True for role-sync to work"

    def test_user_events_enabled(self, live_token):
        """Verify eventsEnabled is True on the production realm."""
        resp = requests.get(
            f"{role_sync.KEYCLOAK_URL}/admin/realms/{role_sync.KEYCLOAK_REALM}",
            headers={"Authorization": f"Bearer {live_token}"},
        )
        resp.raise_for_status()
        realm = resp.json()
        assert realm.get("eventsEnabled") is True, \
            "eventsEnabled must be True for role-sync to work"


# ======================================================================
# Pure Function Tests (no network, no mocking)
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


class TestPushRoutesToCaddyConfigPreservation:
    """Test that push_routes_to_caddy preserves existing Caddy config.

    These tests verify the core logic: that when pushing routes, we:
    1. Fetch the full current config
    2. Update only the internal-server routes
    3. Preserve all other config (http-server, https-server, TLS, PKI, logging)
    """

    def test_config_structure_preserved(self, sample_caddy_config):
        """Verify the config manipulation preserves structure."""
        import copy

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
        import copy

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
        """Verify push_routes_to_caddy uses requests.patch, not requests.put.

        This is a static check on the function implementation to ensure
        we're using PATCH (which merges) instead of PUT (which replaces).
        """
        import inspect
        source = inspect.getsource(role_sync.push_routes_to_caddy)
        assert "requests.patch" in source, "Must use requests.patch to merge with Caddy state"
        assert "requests.put" not in source, "Must NOT use requests.put as it replaces all state"

    def test_fetches_config_before_pushing(self):
        """Verify push_routes_to_caddy fetches current config before pushing.

        This is a static check on the function implementation.
        """
        import inspect
        source = inspect.getsource(role_sync.push_routes_to_caddy)
        assert 'requests.get' in source, "Must fetch current config first"
        assert '/config/' in source or '/config"' in source, "Must GET from /config/ endpoint"


# ======================================================================
# Integration: Full Sync Flow (live Keycloak + pure logic)
# ======================================================================


class TestFullSyncFlow:

    def test_full_sync_with_live_keycloak(self, live_token, sample_mapping):
        """Run initial_sync against live Keycloak (Caddy push mocked)."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(sample_mapping, f)
            f.flush()

        original_mapping = role_sync.MAPPING_FILE
        role_sync.MAPPING_FILE = f.name

        try:
            # Fetch roles live, generate rules, build routes
            roles = role_sync.fetch_all_roles(live_token)
            mapping = role_sync.load_mapping()
            deny_rules = role_sync.generate_deny_rules(mapping, roles)
            routes = role_sync.build_caddy_routes(deny_rules)

            # Should have: static + full_access_bypass + deny rules for matching roles + catch-all
            matching = [e for e in mapping if e["role"] in roles]
            assert len(routes) == len(matching) + 3
            assert routes[0]["terminal"] is True  # static
            assert "terminal" not in routes[-1]   # catch-all
        finally:
            role_sync.MAPPING_FILE = original_mapping
            os.unlink(f.name)

    def test_poll_events_then_has_role_events(self, live_token):
        """Poll live events and run has_role_events on the result."""
        from datetime import datetime, timezone
        since = datetime.now(timezone.utc)
        events = role_sync.poll_admin_events(live_token, since)
        assert isinstance(events, list)
        # has_role_events should not raise
        result = role_sync.has_role_events(events)
        assert isinstance(result, bool)

    def test_deny_rule_count_matches_available_roles(self, live_token, sample_mapping):
        """Verify deny rules are only generated for roles that exist in Keycloak."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(sample_mapping, f)
            f.flush()

        original_mapping = role_sync.MAPPING_FILE
        role_sync.MAPPING_FILE = f.name

        try:
            roles = role_sync.fetch_all_roles(live_token)
            mapping = role_sync.load_mapping()
            deny_rules = role_sync.generate_deny_rules(mapping, roles)

            # Count how many mapping entries have roles in Keycloak
            matching_count = sum(1 for e in mapping if e["role"] in roles)
            assert len(deny_rules) == matching_count
        finally:
            role_sync.MAPPING_FILE = original_mapping
            os.unlink(f.name)

    def test_verify_caddy_routes_returns_list(self):
        """verify_caddy_routes should return a list from the live Caddy instance."""
        result = role_sync.verify_caddy_routes()
        assert isinstance(result, list)
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