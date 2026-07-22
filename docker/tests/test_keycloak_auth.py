#!/usr/bin/env python3
"""
test_keycloak_auth.py - Tests for Keycloak authentication and role fetching.

Tests against the LIVE Keycloak container with real authentication.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import role_sync
import requests


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