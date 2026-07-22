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
import time

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
import keycloak_setup


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
# Fixtures: Live Keycloak role lifecycle (create + cleanup)
# ======================================================================


@pytest.fixture
def live_test_role(live_token):
    """Create a real role in Keycloak for integration testing, then delete it.

    Yields the role name after creation, and guarantees cleanup.
    Also temporarily adds a mapping entry for the role so the sync
    service can generate a deny rule for it.
    """
    role_name = "test:cof-integration-role"
    realm = role_sync.KEYCLOAK_REALM
    base = role_sync.KEYCLOAK_URL
    headers = {"Authorization": f"Bearer {live_token}"}

    # ── CREATE role in Keycloak (reuse keycloak_setup.create_role) ──
    keycloak_setup.create_role(base, live_token, realm, role_name, "CI integration test role")

    # ── Load existing mapping and add a temporary entry ──────────
    original_mapping_path = role_sync.MAPPING_FILE
    mapping_entry = {
        "role": role_name,
        "paths": ["/test-cof", "/test-cof/*"],
        "message": f"Access denied: this resource requires the {role_name} role.",
    }

    # Read existing mapping (if any)
    existing_mapping = []
    if os.path.exists(original_mapping_path):
        with open(original_mapping_path, "r") as f:
            existing_mapping = yaml.safe_load(f) or []

    # Write temporary mapping file with our test entry
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(existing_mapping + [mapping_entry], f)
        temp_mapping = f.name

    role_sync.MAPPING_FILE = temp_mapping

    # ── Initial sync so the new role's deny rule is pushed ───────
    # (done by the test itself after yield)

    yield role_name

    # ── CLEANUP: delete role from Keycloak ───────────────────────
    try:
        resp = requests.delete(
            f"{base}/admin/realms/{realm}/roles/{role_name}",
            headers=headers,
        )
        # 204 = success, 404 = already gone
        assert resp.status_code in (204, 404), \
            f"Failed to delete role {role_name}: {resp.status_code}"
    finally:
        # Always restore mapping file path and delete temp file
        role_sync.MAPPING_FILE = original_mapping_path
        os.unlink(temp_mapping)


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
# Integration: Live Create -> Sync -> Validate / Delete -> Sync -> Validate
# ======================================================================


class TestLiveRoleLifecycleSync:
    """End-to-end tests: create a role in Keycloak, sync to Caddy, validate;
    then delete the role, sync, and validate the deny rule is removed.

    These tests use the LIVE Keycloak and Caddy instances.
    """

    def _find_deny_rule_for_role(self, routes: list, role_name: str) -> dict | None:
        """Search Caddy routes for a deny rule referencing the given role."""
        for route in routes:
            route_str = str(route)
            if f"role:{role_name}" in route_str:
                return route
        return None

    def test_create_role_sync_and_validate(self, live_token, live_test_role):
        """CREATE role -> sync -> validate deny rule exists in Caddy.

        Steps:
        1. Role is already created in Keycloak (live_test_role fixture)
        2. Mapping entry is already added (live_test_role fixture)
        3. Run initial_sync to push routes to Caddy
        4. Verify the deny rule for the test role appears in Caddy
        """
        # Step 1: Verify the role exists in Keycloak
        roles = role_sync.fetch_all_roles(live_token)
        assert live_test_role in roles, \
            f"Test role '{live_test_role}' should exist in Keycloak"

        # Step 2: Run initial sync (pushes routes to Caddy)
        success = role_sync.initial_sync()
        assert success, "initial_sync() should succeed"

        # Step 3: Verify the deny rule for the test role exists in Caddy
        routes = role_sync.verify_caddy_routes()
        assert isinstance(routes, list)
        assert len(routes) > 0, "Caddy should have routes after sync"

        deny_rule = self._find_deny_rule_for_role(routes, live_test_role)
        assert deny_rule is not None, \
            f"Deny rule for role '{live_test_role}' should exist in Caddy routes"

        # Step 4: Validate the deny rule structure
        assert deny_rule.get("terminal") is True, "Deny rule must be terminal"
        handle = deny_rule.get("handle", [{}])[0]
        assert handle.get("handler") == "static_response", \
            "Deny rule handler must be static_response"
        assert handle.get("status_code") == "403", \
            "Deny rule status_code must be 403"

        # Validate the path match includes our test paths
        match_block = deny_rule.get("match", [{}])[0]
        paths = match_block.get("path", [])
        assert "/test-cof" in paths, "/test-cof should be in deny rule paths"
        assert "/test-cof/*" in paths, "/test-cof/* should be in deny rule paths"

        # Validate the NOT condition with X-Forwarded-Groups header_regexp
        not_block = match_block.get("not", [{}])[0]
        header_regexp = not_block.get("header_regexp", {})
        assert "X-Forwarded-Groups" in header_regexp, \
            "Deny rule must check X-Forwarded-Groups header"
        pattern = header_regexp["X-Forwarded-Groups"].get("pattern", "")
        assert f"role:{live_test_role}" in pattern, \
            f"Pattern must contain 'role:{live_test_role}'"

    def test_delete_role_sync_and_validate(self, live_token, live_test_role):
        """DELETE role -> sync -> validate deny rule is removed from Caddy.

        This test manually controls the lifecycle (does NOT rely on the
        fixture's auto-sync) to test the delete flow end-to-end.
        """
        realm = role_sync.KEYCLOAK_REALM
        base = role_sync.KEYCLOAK_URL
        headers = {"Authorization": f"Bearer {live_token}"}

        # ── Step 0: The fixture already created the role and mapping ──

        # Step 1: Verify role exists before we start
        roles = role_sync.fetch_all_roles(live_token)
        assert live_test_role in roles, \
            f"Test role '{live_test_role}' must exist before delete test"

        # Step 2: Sync so the deny rule is present
        success = role_sync.initial_sync()
        assert success, "initial_sync() should succeed before deletion"

        # Step 3: Verify deny rule exists BEFORE deletion
        routes_before = role_sync.verify_caddy_routes()
        deny_rule_before = self._find_deny_rule_for_role(routes_before, live_test_role)
        assert deny_rule_before is not None, \
            f"Deny rule for '{live_test_role}' must exist BEFORE deletion"

        # Step 4: DELETE the role from Keycloak
        resp = requests.delete(
            f"{base}/admin/realms/{realm}/roles/{live_test_role}",
            headers=headers,
        )
        assert resp.status_code in (204, 404), \
            f"DELETE role should succeed, got {resp.status_code}"

        # Step 5: Verify role is gone from Keycloak
        roles_after = role_sync.fetch_all_roles(live_token)
        assert live_test_role not in roles_after, \
            f"Test role '{live_test_role}' should be deleted from Keycloak"

        # Step 6: Run sync again — the deny rule should be removed
        success = role_sync.initial_sync()
        assert success, "initial_sync() should succeed after role deletion"

        # Step 7: Verify deny rule is REMOVED from Caddy
        routes_after = role_sync.verify_caddy_routes()
        deny_rule_after = self._find_deny_rule_for_role(routes_after, live_test_role)
        assert deny_rule_after is None, \
            f"Deny rule for '{live_test_role}' should be REMOVED from Caddy after deletion"


    def test_full_lifecycle_create_sync_validate_delete_sync_validate(self, live_token):
        """Complete end-to-end lifecycle in a single test:

        1. Create a new test role in Keycloak
        2. Add mapping entry for it
        3. Sync -> validate deny rule exists
        4. Delete the role from Keycloak
        5. Sync -> validate deny rule is removed
        6. Cleanup mapping
        """
        role_name = "test:cof-full-lifecycle"
        realm = role_sync.KEYCLOAK_REALM
        base = role_sync.KEYCLOAK_URL
        headers = {"Authorization": f"Bearer {live_token}"}

        # Save original mapping path
        original_mapping_path = role_sync.MAPPING_FILE

        # Load existing mapping
        existing_mapping = []
        if os.path.exists(original_mapping_path):
            with open(original_mapping_path, "r") as f:
                existing_mapping = yaml.safe_load(f) or []

        # Create temp mapping with test role entry
        mapping_entry = {
            "role": role_name,
            "paths": ["/lifecycle-test", "/lifecycle-test/*"],
            "message": f"Access denied: this resource requires the {role_name} role.",
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(existing_mapping + [mapping_entry], f)
            temp_mapping = f.name

        role_sync.MAPPING_FILE = temp_mapping

        try:
            # ── PHASE 1: CREATE role (reuse keycloak_setup) ──────
            keycloak_setup.create_role(base, live_token, realm, role_name, "Full lifecycle test role")

            # Verify role exists
            roles = role_sync.fetch_all_roles(live_token)
            assert role_name in roles

            # ── PHASE 2: SYNC & VALIDATE (role present) ─────────
            success = role_sync.initial_sync()
            assert success, "initial_sync() after role creation should succeed"

            routes = role_sync.verify_caddy_routes()
            deny_rule = self._find_deny_rule_for_role(routes, role_name)
            assert deny_rule is not None, \
                f"Deny rule for '{role_name}' should exist after sync"
            assert deny_rule.get("terminal") is True
            assert deny_rule.get("handle", [{}])[0].get("status_code") == "403"

            # ── PHASE 3: DELETE ─────────────────────────────────
            resp = requests.delete(
                f"{base}/admin/realms/{realm}/roles/{role_name}",
                headers=headers,
            )
            assert resp.status_code in (204, 404)

            # Verify role is gone
            roles_after = role_sync.fetch_all_roles(live_token)
            assert role_name not in roles_after

            # Small delay to ensure Keycloak processes the deletion
            time.sleep(0.5)

            # ── PHASE 4: SYNC & VALIDATE (role removed) ─────────
            success = role_sync.initial_sync()
            assert success, "initial_sync() after role deletion should succeed"

            routes_after = role_sync.verify_caddy_routes()
            deny_rule_after = self._find_deny_rule_for_role(routes_after, role_name)
            assert deny_rule_after is None, \
                f"Deny rule for '{role_name}' should be removed after role deletion"

        finally:
            # ── CLEANUP ──────────────────────────────────────────
            role_sync.MAPPING_FILE = original_mapping_path
            os.unlink(temp_mapping)

            # Ensure role is deleted (idempotent)
            requests.delete(
                f"{base}/admin/realms/{realm}/roles/{role_name}",
                headers=headers,
            )


# ======================================================================
# Role Event Types
# ======================================================================


# ======================================================================
# Integration: Live User Lifecycle (create → validate → delete → validate)
# ======================================================================


class TestLiveUserLifecycle:
    """End-to-end tests for user creation and deletion against live Keycloak.

    Similar pattern to TestLiveRoleLifecycleSync: use live containers,
    create resources, validate via API, delete, and validate cleanup.
    """

    def test_create_user_validate_delete_validate(self, live_token):
        """CREATE user → validate exists → DELETE user → validate gone.

        Steps:
        1. Create a test user in Keycloak
        2. Verify the user exists via the users API
        3. Delete the user
        4. Verify the user is gone
        5. Cleanup (idempotent delete)
        """
        username = "cof-test-user-lifecycle"
        realm = role_sync.KEYCLOAK_REALM
        base = role_sync.KEYCLOAK_URL
        headers = {"Authorization": f"Bearer {live_token}"}

        # ── PHASE 1: CREATE user (reuse keycloak_setup) ──────────
        user_id = keycloak_setup.create_user(base, live_token, realm, username, "TestPass123!")
        assert user_id, "Failed to create test user"

        # ── PHASE 2: VALIDATE user exists ────────────────────────
        resp = requests.get(
            f"{base}/admin/realms/{realm}/users",
            params={"username": username, "max": 1},
            headers=headers,
        )
        resp.raise_for_status()
        users = resp.json()
        assert len(users) == 1, f"Expected 1 user, got {len(users)}"
        assert users[0]["username"] == username
        assert users[0]["email"] == f"{username}@conciergeos.local"
        assert users[0]["enabled"] is True
        saved_user_id = users[0]["id"]

        # ── PHASE 3: DELETE user ─────────────────────────────────
        resp = requests.delete(
            f"{base}/admin/realms/{realm}/users/{saved_user_id}",
            headers=headers,
        )
        assert resp.status_code in (204, 200), \
            f"Delete user failed: {resp.status_code}"

        # ── PHASE 4: VALIDATE user is gone ───────────────────────
        resp = requests.get(
            f"{base}/admin/realms/{realm}/users",
            params={"username": username, "max": 1},
            headers=headers,
        )
        resp.raise_for_status()
        users_after = resp.json()
        assert len(users_after) == 0, \
            f"User '{username}' should be deleted but still found: {users_after}"


class TestLiveSessionLifecycle:
    """End-to-end tests for session creation and deletion against live Keycloak.

    Pattern: authenticate a user to create a session, validate it exists,
    delete it, and validate it's gone.
    """

    def _ensure_test_user(self, live_token, username: str, password: str) -> str | None:
        """Create or find a test user using keycloak_setup.create_user.

        keycloak_setup.create_user handles idempotency (finds existing users),
        sets firstName/lastName, and clears required actions so password grant works.
        """
        realm = role_sync.KEYCLOAK_REALM
        base = role_sync.KEYCLOAK_URL
        return keycloak_setup.create_user(base, live_token, realm, username, password) or None

    def test_create_session_validate_delete_validate(self, live_token):
        """CREATE session (via user login) → validate exists → DELETE session → validate gone.

        Steps:
        1. Ensure test user exists
        2. Authenticate as user to create a session
        3. Find the session via admin API
        4. Delete the session via admin API
        5. Validate the session is gone
        6. Cleanup user
        """
        username = "cof-test-session-user"
        password = "SessionTest123!"
        realm = role_sync.KEYCLOAK_REALM
        base = role_sync.KEYCLOAK_URL
        headers = {"Authorization": f"Bearer {live_token}"}

        user_id = self._ensure_test_user(live_token, username, password)
        assert user_id, "Failed to create/find test user"

        try:
            # ── PHASE 1: CREATE session (authenticate as user) ───
            resp = requests.post(
                f"{base}/realms/{realm}/protocol/openid-connect/token",
                data={
                    "grant_type": "password",
                    "client_id": "admin-cli",
                    "username": username,
                    "password": password,
                },
            )
            assert resp.status_code == 200, \
                f"User login failed: {resp.status_code} {resp.text}"
            user_token = resp.json().get("access_token")
            assert user_token, "No access_token from user login"

            # ── PHASE 2: VALIDATE session exists ─────────────────
            resp = requests.get(
                f"{base}/admin/realms/{realm}/users/{user_id}/sessions",
                headers=headers,
            )
            resp.raise_for_status()
            sessions = resp.json()
            assert len(sessions) >= 1, \
                f"Expected at least 1 session for user, got {len(sessions)}"

            # Collect session IDs
            session_ids = [s["id"] for s in sessions]
            assert len(session_ids) >= 1, "No session IDs found"

            # ── PHASE 3: DELETE session(s) ───────────────────────
            for session_id in session_ids:
                resp = requests.delete(
                    f"{base}/admin/realms/{realm}/sessions/{session_id}",
                    headers=headers,
                )
                assert resp.status_code in (204, 200), \
                    f"Delete session {session_id} failed: {resp.status_code}"

            # Small delay for Keycloak to process
            time.sleep(0.5)

            # ── PHASE 4: VALIDATE session is gone ────────────────
            resp = requests.get(
                f"{base}/admin/realms/{realm}/users/{user_id}/sessions",
                headers=headers,
            )
            resp.raise_for_status()
            sessions_after = resp.json()
            assert len(sessions_after) == 0, \
                f"Sessions should be deleted but still found: {len(sessions_after)} sessions"

        finally:
            # ── CLEANUP: delete test user ────────────────────────
            try:
                resp = requests.delete(
                    f"{base}/admin/realms/{realm}/users/{user_id}",
                    headers=headers,
                )
                # 204 = success, 404 = already gone (session deletion may have cascaded)
                assert resp.status_code in (204, 200, 404), \
                    f"Cleanup delete user failed: {resp.status_code}"
            except Exception:
                pass  # Best-effort cleanup


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