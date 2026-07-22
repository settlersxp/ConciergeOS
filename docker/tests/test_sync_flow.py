#!/usr/bin/env python3
"""
test_sync_flow.py - Integration tests for the full sync flow and role lifecycle.

Tests the full sync flow (live Keycloak + pure logic) and end-to-end role
lifecycle: create -> sync -> validate -> delete -> sync -> validate.
"""

import os
import sys
import tempfile
import time

import requests
import yaml

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import role_sync
import keycloak_setup


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