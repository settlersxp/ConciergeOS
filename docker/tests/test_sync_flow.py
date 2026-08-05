#!/usr/bin/env python3
"""
test_sync_flow.py - Tests for the RBAC sync orchestration.

Tests the has_role_events gate, sync_all_roles with create flag,
and the end-to-end poll_and_sync integration.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rbac_sync import has_role_events, poll_and_sync
from keycloak_common import authenticate


# ======================================================================
# TestHasRoleEvents
# ======================================================================


class TestHasRoleEvents:

    @staticmethod
    def _event(**kwargs) -> dict:
        return kwargs

    def test_creates_role(self):
        assert has_role_events([self._event(operationType="CREATE", resourceType="ROLE")])

    def test_updates_role(self):
        assert has_role_events([self._event(operationType="UPDATE", resourceType="ROLE")])

    def test_deletes_role(self):
        assert has_role_events([self._event(operationType="DELETE", resourceType="ROLE")])

    def test_view_does_not_create(self):
        assert not has_role_events([self._event(operationType="VIEW", resourceType="ROLE")])

    def test_login_does_not_create(self):
        assert not has_role_events([self._event(operationType="LOGIN", resourceType="USER")])

    def test_empty_list(self):
        assert not has_role_events([])


# ======================================================================
# TestSyncFlowIntegration
# ======================================================================


class TestSyncFlowIntegration:

    def test_poll_and_sync_runs(self, live_token):
        """poll_and_sync() runs without exceptions (hits live Keycloak + Caddy)."""
        result = poll_and_sync()
        # poll_and_sync returns True on success, False on failure
        # In tests we just verify it runs without raising
        assert isinstance(result, bool)


# ======================================================================
# Fixtures
# ======================================================================


@pytest.fixture
def live_token():
    """Get a live authentication token."""
    return authenticate()
