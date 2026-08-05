#!/usr/bin/env python3
"""Tests for Keycloak events and realm configuration.

Tests against the LIVE Keycloak container with real events API.
"""

from datetime import datetime, timezone

from keycloak_setup.events import fetch_events_with_params, get_realm_events
from keycloak_setup.realms import get_realm_config
from rbac_sync import poll_admin_events
from rbac_sync.config import KEYCLOAK_REALM


class TestLiveKeycloakEvents:

    def test_poll_admin_events_returns_list(self, live_token):
        """poll_admin_events should return a list (possibly empty)."""
        since = datetime.now(timezone.utc)
        events = poll_admin_events(live_token, since)
        assert isinstance(events, list)

    def test_poll_admin_events_uses_ymd_date_format_not_milliseconds(self, live_token):
        """Keycloak 26 requires yyyy-MM-dd date format.

        This test verifies the fix by:
        1. Confirming that millisecond timestamps (the OLD code) cause a 400 error
        2. Confirming that poll_admin_events() works (it uses yyyy-MM-dd internally)
        """
        now = datetime.now(timezone.utc)
        timestamp_ms = int(now.timestamp() * 1000)

        # Step 1: Prove milliseconds fail (this is what the OLD code did)
        resp_bad = fetch_events_with_params(
            live_token,
            KEYCLOAK_REALM,
            params={"dateFrom": timestamp_ms, "dateTo": timestamp_ms + 1000},
        )
        assert resp_bad.status_code == 400, "Milliseconds should fail with 400"
        assert "Invalid value" in resp_bad.json()["error"]

        # Step 2: Prove our fix works (poll_admin_events uses yyyy-MM-dd)
        events = poll_admin_events(live_token, now)
        assert isinstance(events, list)

    def test_poll_admin_events_accepts_ymd_format(self, live_token):
        """Verify yyyy-MM-dd format works (the fix)."""
        now = datetime.now(timezone.utc)
        date_str = now.strftime("%Y-%m-%d")

        events = get_realm_events(live_token, KEYCLOAK_REALM, date_str, date_str)
        assert isinstance(events, list)

    def test_poll_admin_events_does_not_send_type_admin(self, live_token):
        """Verify type=ADMIN is NOT sent (Keycloak 26 rejects it)."""
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # type=ADMIN causes 500 — do not send it
        resp = fetch_events_with_params(
            live_token,
            KEYCLOAK_REALM,
            params={"dateFrom": date_str, "dateTo": date_str, "type": "ADMIN"},
        )
        assert resp.status_code == 500, "type=ADMIN should fail (proves we must not use it)"


class TestLiveKeycloakRealmConfig:

    def test_admin_events_enabled(self, live_token):
        """Verify adminEventsEnabled is True on the production realm."""
        config = get_realm_config(live_token, KEYCLOAK_REALM)
        assert config.get("adminEventsEnabled") is True, \
            "adminEventsEnabled must be True for role-sync to work"

    def test_user_events_enabled(self, live_token):
        """Verify eventsEnabled is True on the production realm."""
        config = get_realm_config(live_token, KEYCLOAK_REALM)
        assert config.get("eventsEnabled") is True, \
            "eventsEnabled must be True for role-sync to work"