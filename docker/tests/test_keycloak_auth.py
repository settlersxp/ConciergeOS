#!/usr/bin/env python3
"""
test_keycloak_auth.py - Tests for Keycloak authentication and role fetching.

Tests against the LIVE Keycloak container with real authentication.
"""

from keycloak_setup.auth import authenticate
from keycloak_setup.realms import get_realm_config
from keycloak_setup.roles import list_roles
from settings import settings


class TestLiveKeycloakAuth:

    def test_authenticate_returns_valid_token(self):
        """Authenticate against live Keycloak and verify we get a token."""
        token = authenticate()
        assert isinstance(token, str)
        assert len(token) > 100  # JWT tokens are long

    def test_authenticate_token_works_for_api(self, live_token):
        """Verify the token can access the admin API."""
        data = get_realm_config(live_token, settings.KEYCLOAK_REALM)
        assert data["realm"] == settings.KEYCLOAK_REALM


class TestLiveKeycloakRoles:

    def test_fetch_all_roles_returns_roles(self, live_token):
        """Fetch roles from live Keycloak — should return at least our defined roles."""
        roles = list_roles(live_token, settings.KEYCLOAK_REALM)
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
        roles = list_roles(live_token, settings.KEYCLOAK_REALM)
        assert "uma_authorization" in roles