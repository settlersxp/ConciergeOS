#!/usr/bin/env python3
"""
test_sync_flow.py - Integration tests for the full sync flow and role lifecycle.

Tests the full sync flow (live Keycloak + pure logic) and end-to-end role
lifecycle: create -> sync -> validate -> delete -> sync -> validate.

The sync flow now uses Keycloak role attributes (paths, menus) instead of
an external YAML mapping file.
"""

import os
import sys
import time

import requests

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import role_sync
import keycloak_setup


# ======================================================================
# Integration: Full Sync Flow (live Keycloak + pure logic)
# ======================================================================


class TestFullSyncFlow:

    def test_full_sync_with_live_keycloak(self, live_token):
        """Run initial_sync against live Keycloak (Caddy push may or may not be available)."""
        roles_with_attrs = role_sync.fetch_all_roles_with_attrs(live_token)
        assert isinstance(roles_with_attrs, dict)
        assert len(roles_with_attrs) > 0, "Should have at least one role in Keycloak"

        deny_rules = role_sync.generate_deny_rules(roles_with_attrs)
        assert isinstance(deny_rules, list)

        routes = role_sync.build_caddy_routes(deny_rules)
        assert isinstance(routes, list)
        roles_with_paths = sum(1 for r in roles_with_attrs.values() if r.get("paths"))
        assert len(routes) == roles_with_paths + 3
        assert routes[0]["terminal"] is True  # static
        assert "terminal" not in routes[-1]   # catch-all

    def test_poll_events_then_has_role_events(self, live_token):
        """Poll live events and run has_role_events on the result."""
        from datetime import datetime, timezone
        since = datetime.now(timezone.utc)
        events = role_sync.poll_admin_events(live_token, since)
        assert isinstance(events, list)
        result = role_sync.has_role_events(events)
        assert isinstance(result, bool)

    def test_deny_rule_count_matches_roles_with_paths(self, live_token):
        """Verify deny rules are only generated for roles that have 'paths' attribute."""
        roles_with_attrs = role_sync.fetch_all_roles_with_attrs(live_token)
        deny_rules = role_sync.generate_deny_rules(roles_with_attrs)
        roles_with_paths = sum(1 for r in roles_with_attrs.values() if r.get("paths"))
        assert len(deny_rules) == roles_with_paths

    def test_verify_caddy_routes_returns_list(self):
        """verify_caddy_routes should return a list from the live Caddy instance."""
        result = role_sync.verify_caddy_routes()
        assert isinstance(result, list)

    def test_fetch_roles_includes_role_attributes(self, live_token):
        """Verify that roles with paths/menus attributes are fetched correctly."""
        roles_with_attrs = role_sync.fetch_all_roles_with_attrs(live_token)

        setup_role_names = {
            "reservations:view",
            "reservations:edit",
            "settings:view",
            "prompts:edit",
            "prompt_groups:edit",
        }
        found_roles = set(roles_with_attrs.keys())
        intersection = setup_role_names & found_roles
        assert len(intersection) > 0, f"Expected some setup roles, found: {found_roles}"

        for role_name in intersection:
            attrs = roles_with_attrs[role_name]
            assert "paths" in attrs, f"{role_name} should have 'paths' attribute"
            assert "menus" in attrs, f"{role_name} should have 'menus' attribute"
            assert isinstance(attrs["paths"], list)
            assert isinstance(attrs["menus"], list)

    def test_get_menus_for_roles(self, live_token):
        """Test menu aggregation from role attributes."""
        from role_sync import get_menus_for_roles
        roles_with_attrs = role_sync.fetch_all_roles_with_attrs(live_token)
        for role_name in list(roles_with_attrs.keys())[:1]:
            menus = get_menus_for_roles({role_name}, roles_with_attrs)
            assert isinstance(menus, list)

    def test_get_menus_for_full_access(self, live_token):
        """Test that full-access role gets all menus."""
        from role_sync import get_menus_for_roles
        roles_with_attrs = role_sync.fetch_all_roles_with_attrs(live_token)
        menus = get_menus_for_roles({"full-access"}, roles_with_attrs)
        all_menus: set[str] = set()
        for attrs in roles_with_attrs.values():
            for m in attrs.get("menus", []):
                all_menus.add(m)
        assert set(menus) == all_menus


# ======================================================================
# Helper: create role with attributes via direct Keycloak API
# ======================================================================


def _create_role_with_attrs(base_url: str, token: str, realm: str, role_name: str,
                            paths: list[str], menus: list[str]) -> None:
    """Create a role in Keycloak with custom paths/menus attributes.

    keycloak_setup.create_role only creates the role without attributes.
    This helper creates the role and then PUTs the attributes back.
    """
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # Step 1: Create role (or skip if exists)
    resp = requests.get(
        f"{base_url}/admin/realms/{realm}/roles/{role_name}",
        headers=headers,
    )
    if resp.status_code != 200:
        resp = requests.post(
            f"{base_url}/admin/realms/{realm}/roles",
            headers=headers,
            json={"name": role_name, "description": f"Test role: {role_name}"},
        )
        resp.raise_for_status()

    # Step 2: PUT role with attributes
    resp = requests.get(
        f"{base_url}/admin/realms/{realm}/roles/{role_name}",
        headers=headers,
    )
    resp.raise_for_status()
    role_data = resp.json()
    role_data["attributes"] = {
        "paths": paths,
        "menus": menus,
    }
    resp = requests.put(
        f"{base_url}/admin/realms/{realm}/roles/{role_name}",
        headers=headers,
        json=role_data,
    )
    resp.raise_for_status()


# ======================================================================
# Integration: Live Create -> Sync -> Validate / Delete -> Sync -> Validate
# ======================================================================


class TestLiveRoleLifecycleSync:
    """End-to-end tests: create a role with attributes in Keycloak, sync to Caddy, validate;
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
        """CREATE role with attributes -> sync -> validate deny rule exists in Caddy."""
        roles_with_attrs = role_sync.fetch_all_roles_with_attrs(live_token)
        assert live_test_role in roles_with_attrs, \
            f"Test role '{live_test_role}' should exist in Keycloak"

        role_attrs = roles_with_attrs[live_test_role]
        assert role_attrs.get("paths"), \
            f"Test role '{live_test_role}' should have 'paths' attribute"
        assert "/test-cof" in role_attrs["paths"], "/test-cof should be in role paths"

        success = role_sync.initial_sync()
        assert success, "initial_sync() should succeed"

        routes = role_sync.verify_caddy_routes()
        assert isinstance(routes, list)
        assert len(routes) > 0, "Caddy should have routes after sync"

        deny_rule = self._find_deny_rule_for_role(routes, live_test_role)
        assert deny_rule is not None, \
            f"Deny rule for role '{live_test_role}' should exist in Caddy routes"

        assert deny_rule.get("terminal") is True, "Deny rule must be terminal"
        handle = deny_rule.get("handle", [{}])[0]
        assert handle.get("handler") == "static_response", \
            "Deny rule handler must be static_response"
        assert handle.get("status_code") == "403", "Deny rule status_code must be 403"

        match_block = deny_rule.get("match", [{}])[0]
        paths = match_block.get("path", [])
        assert "/test-cof" in paths, "/test-cof should be in deny rule paths"
        assert "/test-cof/*" in paths, "/test-cof/* should be in deny rule paths"

        not_block = match_block.get("not", [{}])[0]
        header_regexp = not_block.get("header_regexp", {})
        assert "X-Forwarded-Groups" in header_regexp, \
            "Deny rule must check X-Forwarded-Groups header"
        pattern = header_regexp["X-Forwarded-Groups"].get("pattern", "")
        assert f"role:{live_test_role}" in pattern, \
            f"Pattern must contain 'role:{live_test_role}'"

    def test_delete_role_sync_and_validate(self, live_token, live_test_role):
        """DELETE role -> sync -> validate deny rule is removed from Caddy."""
        realm = role_sync.KEYCLOAK_REALM
        base = role_sync.KEYCLOAK_URL
        headers = {"Authorization": f"Bearer {live_token}"}

        roles_with_attrs = role_sync.fetch_all_roles_with_attrs(live_token)
        assert live_test_role in roles_with_attrs, \
            f"Test role '{live_test_role}' must exist before delete test"

        success = role_sync.initial_sync()
        assert success, "initial_sync() should succeed before deletion"

        routes_before = role_sync.verify_caddy_routes()
        deny_rule_before = self._find_deny_rule_for_role(routes_before, live_test_role)
        assert deny_rule_before is not None, \
            f"Deny rule for '{live_test_role}' must exist BEFORE deletion"

        resp = requests.delete(
            f"{base}/admin/realms/{realm}/roles/{live_test_role}",
            headers=headers,
        )
        assert resp.status_code in (204, 404), \
            f"DELETE role should succeed, got {resp.status_code}"

        roles_after = role_sync.fetch_all_roles_with_attrs(live_token)
        assert live_test_role not in roles_after, \
            f"Test role '{live_test_role}' should be deleted from Keycloak"

        success = role_sync.initial_sync()
        assert success, "initial_sync() should succeed after role deletion"

        routes_after = role_sync.verify_caddy_routes()
        deny_rule_after = self._find_deny_rule_for_role(routes_after, live_test_role)
        assert deny_rule_after is None, \
            f"Deny rule for '{live_test_role}' should be REMOVED from Caddy after deletion"

    def test_full_lifecycle_create_sync_validate_delete_sync_validate(self, live_token):
        """Complete end-to-end lifecycle in a single test:

        1. Create a new test role in Keycloak with paths/menus attributes
        2. Sync -> validate deny rule exists
        3. Delete the role from Keycloak
        4. Sync -> validate deny rule is removed
        """
        role_name = "test:cof-full-lifecycle"
        realm = role_sync.KEYCLOAK_REALM
        base = role_sync.KEYCLOAK_URL
        headers = {"Authorization": f"Bearer {live_token}"}

        try:
            # Phase 1: CREATE role with attributes
            _create_role_with_attrs(
                base, live_token, realm, role_name,
                paths=["/lifecycle-test", "/lifecycle-test/*"],
                menus=["lifecycle-test"],
            )

            # Verify role exists with attributes
            roles_with_attrs = role_sync.fetch_all_roles_with_attrs(live_token)
            assert role_name in roles_with_attrs
            assert roles_with_attrs[role_name].get("paths")

            # Phase 2: SYNC & VALIDATE (role present)
            success = role_sync.initial_sync()
            assert success, "initial_sync() after role creation should succeed"

            routes = role_sync.verify_caddy_routes()
            deny_rule = self._find_deny_rule_for_role(routes, role_name)
            assert deny_rule is not None, \
                f"Deny rule for '{role_name}' should exist after sync"
            assert deny_rule.get("terminal") is True
            assert deny_rule.get("handle", [{}])[0].get("status_code") == "403"

            # Phase 3: DELETE
            resp = requests.delete(
                f"{base}/admin/realms/{realm}/roles/{role_name}",
                headers=headers,
            )
            assert resp.status_code in (204, 404)

            # Verify role is gone
            roles_after = role_sync.fetch_all_roles_with_attrs(live_token)
            assert role_name not in roles_after

            time.sleep(0.5)

            # Phase 4: SYNC & VALIDATE (role removed)
            success = role_sync.initial_sync()
            assert success, "initial_sync() after role deletion should succeed"

            routes_after = role_sync.verify_caddy_routes()
            deny_rule_after = self._find_deny_rule_for_role(routes_after, role_name)
            assert deny_rule_after is None, \
                f"Deny rule for '{role_name}' should be removed after role deletion"

        finally:
            # Cleanup (idempotent)
            requests.delete(
                f"{base}/admin/realms/{realm}/roles/{role_name}",
                headers=headers,
            )


# ======================================================================
# Integration: Live User Lifecycle (create -> validate -> delete -> validate)
# ======================================================================


class TestLiveUserLifecycle:
    """End-to-end tests for user creation and deletion against live Keycloak."""

    def test_create_user_validate_delete_validate(self, live_token):
        """CREATE user -> validate exists -> DELETE user -> validate gone."""
        username = "cof-test-user-lifecycle"
        realm = role_sync.KEYCLOAK_REALM
        base = role_sync.KEYCLOAK_URL
        headers = {"Authorization": f"Bearer {live_token}"}

        # Phase 1: CREATE user via direct API
        resp = requests.post(
            f"{base}/admin/realms/{realm}/users",
            headers=headers,
            json={
                "username": username,
                "enabled": True,
                "email": f"{username}@conciergeos.local",
                "credentials": [{"type": "password", "value": "TestPass123!", "temporary": False}],
                "emailVerified": True,
                "requiredActions": [],
            },
        )
        assert resp.status_code in (201, 204), f"Create user failed: {resp.status_code} {resp.text}"
        user_id = resp.headers.get("Location", "").split("/")[-1]

        # Phase 2: VALIDATE user exists
        resp = requests.get(
            f"{base}/admin/realms/{realm}/users",
            params={"username": username, "max": 1},
            headers=headers,
        )
        resp.raise_for_status()
        users = resp.json()
        assert len(users) == 1, f"Expected 1 user, got {len(users)}"
        assert users[0]["username"] == username
        saved_user_id = users[0]["id"]

        # Phase 3: DELETE user
        resp = requests.delete(
            f"{base}/admin/realms/{realm}/users/{saved_user_id}",
            headers=headers,
        )
        assert resp.status_code in (204, 200), f"Delete user failed: {resp.status_code}"

        # Phase 4: VALIDATE user is gone
        resp = requests.get(
            f"{base}/admin/realms/{realm}/users",
            params={"username": username, "max": 1},
            headers=headers,
        )
        resp.raise_for_status()
        users_after = resp.json()
        assert len(users_after) == 0, \
            f"User '{username}' should be deleted but still found: {users_after}"