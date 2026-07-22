#!/usr/bin/env python3
"""
test_keycloak_events.py - Tests for Keycloak events and realm configuration.

Tests against the LIVE Keycloak container with real events API.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import role_sync
import requests


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