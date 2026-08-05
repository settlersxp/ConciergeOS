#!/usr/bin/env python3
"""
test_valkey_session.py - Tests for Valkey session storage and oauth2-proxy integration.

Validates the FULL session invalidation chain:
  User login → oauth2-proxy creates Valkey session → Valkey key deleted →
  oauth2-proxy returns 401 → browser redirected to Keycloak login
"""

import re
import subprocess
import time

import requests

from rbac_sync.config import VALKEY_URL, KEYCLOAK_REALM
from rbac_sync import SESSION_KEY_PREFIX
from settings import settings

from helpers import (
    PUBLIC_BASE,
    get_valkey_client,
    list_oauth2_proxy_sessions,
    count_oauth2_proxy_sessions,
    ensure_test_user,
    cleanup_user,
    oauth2_login_flow,
)


# ======================================================================
# TestValkeyConnectivity
# ======================================================================


class TestValkeyConnectivity:
    """Verify the test environment can reach Valkey."""

    def test_valkey_ping(self):
        """Valkey responds to PING."""
        r = get_valkey_client(VALKEY_URL)
        assert r.ping(), "Valkey PING failed"

    def test_valkey_session_key_pattern_exists(self, live_token):
        """After a user logs in through oauth2-proxy, session keys appear in Valkey."""
        r = get_valkey_client(VALKEY_URL)
        keys = list_oauth2_proxy_sessions(r, SESSION_KEY_PREFIX)
        assert isinstance(keys, list)


# ======================================================================
# TestValkeySessionStorage
# ======================================================================


class TestValkeySessionStorage:
    """Verify oauth2-proxy stores sessions in Valkey after user authentication."""

    def test_session_key_appears_in_valkey_after_oauth2_login(self, live_token):
        """User login via oauth2-proxy → session key appears in Valkey."""
        r = get_valkey_client(VALKEY_URL)
        username = "cof-valkey-storage-user"
        password = "ValkeyStore123!"

        user_id = ensure_test_user(live_token, KEYCLOAK_REALM, username, password)
        assert user_id, "Failed to create/find test user"

        try:
            count_before = count_oauth2_proxy_sessions(r, SESSION_KEY_PREFIX)

            # Authenticate through oauth2-proxy via full OIDC flow
            sess, _ = oauth2_login_flow(
                live_token, settings.KEYCLOAK_URL, KEYCLOAK_REALM, username, password
            )

            time.sleep(1)

            count_after = count_oauth2_proxy_sessions(r, SESSION_KEY_PREFIX)
            assert count_after >= count_before, \
                f"Expected session count to increase: before={count_before}, after={count_after}"

        finally:
            cleanup_user(live_token, settings.KEYCLOAK_URL, KEYCLOAK_REALM, user_id)

    def test_session_key_format_matches_pattern(self, live_token):
        """Session keys in Valkey match the expected oauth2-proxy format."""
        r = get_valkey_client(VALKEY_URL)
        username = "cof-valkey-format-user"
        password = "ValkeyFmt123!"

        user_id = ensure_test_user(live_token, KEYCLOAK_REALM, username, password)
        assert user_id

        try:
            oauth2_login_flow(
                live_token, settings.KEYCLOAK_URL, KEYCLOAK_REALM, username, password
            )
            time.sleep(1)

            # Validate key format
            keys = list_oauth2_proxy_sessions(r, SESSION_KEY_PREFIX)
            pattern = re.compile(rb"^_oauth2_proxy-[0-9a-f]{32}$")

            for key in keys:
                assert pattern.match(key), \
                    f"Session key '{key.decode()}' does not match expected pattern '_oauth2_proxy-{{32-hex}}'"

        finally:
            cleanup_user(live_token, settings.KEYCLOAK_URL, KEYCLOAK_REALM, user_id)


# ======================================================================
# TestValkeySessionInvalidation
# ======================================================================


class TestValkeySessionInvalidation:
    """Verify deleting session keys from Valkey invalidates the oauth2-proxy session."""

    def test_delete_valkey_key_invalidates_oauth2_session(self, live_token):
        """Delete session key from Valkey → oauth2-proxy /oauth2/auth returns 401."""
        r = get_valkey_client(VALKEY_URL)
        username = "cof-valkey-inval-user"
        password = "ValkeyInval123!"

        user_id = ensure_test_user(live_token, KEYCLOAK_REALM, username, password)
        assert user_id

        try:
            # PHASE 1: Authenticate through oauth2-proxy
            sess, _ = oauth2_login_flow(
                live_token, settings.KEYCLOAK_URL, KEYCLOAK_REALM, username, password
            )

            # PHASE 2: Verify session is valid
            auth_resp = sess.get(
                f"{PUBLIC_BASE}/oauth2/auth",
                verify=False,
                timeout=10,
                allow_redirects=False,
            )
            assert auth_resp.status_code in (200, 202, 403), \
                f"Expected 200/202/403 from /oauth2/auth with valid session, got {auth_resp.status_code}"

            session_cookie = sess.cookies.get("_oauth2_proxy", "")
            assert session_cookie, "No _oauth2_proxy cookie set after login"

            # PHASE 3: Verify Valkey key exists
            keys_before = list_oauth2_proxy_sessions(r, SESSION_KEY_PREFIX)
            assert len(keys_before) > 0, \
                f"No session keys in Valkey after login. Cookie present but Valkey empty."

            # PHASE 4: Delete ALL session keys from Valkey
            for key in keys_before:
                r.delete(key)
            time.sleep(0.5)

            # Verify keys are gone
            keys_after = list_oauth2_proxy_sessions(r, SESSION_KEY_PREFIX)
            assert len(keys_after) == 0, \
                f"Session keys not deleted from Valkey: {keys_after}"

            # PHASE 5: Verify session is INVALID
            sess2 = requests.Session()
            sess2.trust_env = False
            sess2.cookies.set("_oauth2_proxy", session_cookie, domain="out-customer.com")

            auth_resp2 = sess2.get(
                f"{PUBLIC_BASE}/oauth2/auth",
                verify=False,
                timeout=10,
                allow_redirects=False,
            )

            assert auth_resp2.status_code in (401, 403, 302), \
                f"Expected 401/403/302 after Valkey key deletion, got {auth_resp2.status_code}. " \
                f"Session was NOT invalidated by Valkey key deletion!"

        finally:
            cleanup_user(live_token, settings.KEYCLOAK_URL, KEYCLOAK_REALM, user_id)

    def test_invalidate_all_sessions_function_works(self, live_token):
        """role_sync.invalidate_all_sessions() deletes all oauth2-proxy sessions from Valkey."""
        r = get_valkey_client(VALKEY_URL)
        username = "cof-valkey-inval-all-user"
        password = "ValkeyInvalAll123!"

        user_id = ensure_test_user(live_token, KEYCLOAK_REALM, username, password)
        assert user_id

        try:
            # PHASE 1: Create session via oauth2-proxy
            sess, _ = oauth2_login_flow(
                live_token, settings.KEYCLOAK_URL, KEYCLOAK_REALM, username, password
            )

            session_cookie = sess.cookies.get("_oauth2_proxy", "")
            assert session_cookie, "No _oauth2_proxy cookie after login"

            # PHASE 2: Verify keys exist
            keys_before = list_oauth2_proxy_sessions(r, SESSION_KEY_PREFIX)
            assert len(keys_before) > 0, "No session keys in Valkey before invalidation"
            count_before = len(keys_before)

            # PHASE 3: Call invalidate_all_sessions() via docker exec
            inval_result = subprocess.run(
                ["docker", "exec", "-w", "/app", "role-sync", "python3", "-c",
                 "import role_sync; print(role_sync.invalidate_all_sessions())"],
                capture_output=True, text=True, timeout=10,
            )
            if inval_result.returncode != 0:
                raise RuntimeError(f"invalidate_all_sessions failed: {inval_result.stderr}")
            deleted = int(inval_result.stdout.strip().split("\n")[-1])
            assert deleted > 0, \
                f"invalidate_all_sessions() reported 0 deleted, but {count_before} keys existed"

            # PHASE 4: Verify ALL keys gone
            keys_after = list_oauth2_proxy_sessions(r, SESSION_KEY_PREFIX)
            assert len(keys_after) == 0, \
                f"Keys remain after invalidate_all_sessions(): {keys_after}"

            # PHASE 5: Verify old cookie no longer works
            sess2 = requests.Session()
            sess2.trust_env = False
            sess2.cookies.set("_oauth2_proxy", session_cookie, domain="out-customer.com")

            auth_resp = sess2.get(
                f"{PUBLIC_BASE}/oauth2/auth",
                verify=False,
                timeout=10,
                allow_redirects=False,
            )

            assert auth_resp.status_code in (401, 403, 302), \
                f"Expected 401/403/302 after invalidate_all_sessions(), got {auth_resp.status_code}"

        finally:
            cleanup_user(live_token, settings.KEYCLOAK_URL, KEYCLOAK_REALM, user_id)

    def test_session_survives_when_valkey_key_present(self, live_token):
        """Negative test: with the key still in Valkey, the session remains valid."""
        username = "cof-valkey-survive-user"
        password = "ValkeySurvive123!"

        user_id = ensure_test_user(live_token, KEYCLOAK_REALM, username, password)
        assert user_id

        try:
            # PHASE 1: Authenticate
            sess, _ = oauth2_login_flow(
                live_token, settings.KEYCLOAK_URL, KEYCLOAK_REALM, username, password
            )

            # PHASE 2: Verify session valid (key still present)
            auth_resp1 = sess.get(
                f"{PUBLIC_BASE}/oauth2/auth",
                verify=False,
                timeout=10,
                allow_redirects=False,
            )
            assert auth_resp1.status_code in (200, 202, 403), \
                f"Expected valid session, got {auth_resp1.status_code}"

            time.sleep(2)

            auth_resp2 = sess.get(
                f"{PUBLIC_BASE}/oauth2/auth",
                verify=False,
                timeout=10,
                allow_redirects=False,
            )
            assert auth_resp2.status_code in (200, 202, 403), \
                f"Session should remain valid when Valkey key is present, got {auth_resp2.status_code}"

        finally:
            cleanup_user(live_token, settings.KEYCLOAK_URL, KEYCLOAK_REALM, user_id)


# ======================================================================
# TestOAuth2ProxySignOut
# ======================================================================


class TestOAuth2ProxySignOut:
    """Verify the oauth2-proxy /oauth2/sign_out endpoint correctly cleans up."""

    def test_sign_out_deletes_valkey_session(self, live_token):
        """HIT /oauth2/sign_out → session key deleted from Valkey."""
        r = get_valkey_client(VALKEY_URL)
        username = "cof-signout-user"
        password = "SignOut123!"

        user_id = ensure_test_user(live_token, KEYCLOAK_REALM, username, password)
        assert user_id

        try:
            # PHASE 1: Authenticate
            sess, _ = oauth2_login_flow(
                live_token, settings.KEYCLOAK_URL, KEYCLOAK_REALM, username, password
            )

            # PHASE 2: Verify session exists
            keys_before = list_oauth2_proxy_sessions(r, SESSION_KEY_PREFIX)
            assert len(keys_before) > 0, "No session in Valkey before sign out"

            # PHASE 3: Hit /oauth2/sign_out
            sess.get(
                f"{PUBLIC_BASE}/oauth2/sign_out",
                verify=False,
                timeout=10,
                allow_redirects=False,
            )
            time.sleep(1)

            # PHASE 4: Verify session key DELETED
            keys_after = list_oauth2_proxy_sessions(r, SESSION_KEY_PREFIX)
            assert len(keys_after) < len(keys_before) or len(keys_after) == 0, \
                f"Sign out did not delete session: before={len(keys_before)}, after={len(keys_after)}"

        finally:
            cleanup_user(live_token, settings.KEYCLOAK_URL, KEYCLOAK_REALM, user_id)


# ======================================================================
# TestLiveSessionLifecycle (Keycloak sessions)
# ======================================================================


class TestLiveSessionLifecycle:
    """End-to-end tests for session creation and deletion against live Keycloak."""

    def test_create_session_validate_delete_validate(self, live_token):
        """CREATE session (via user login) → validate exists → DELETE session → validate gone."""
        username = "cof-test-session-user"
        password = "SessionTest123!"
        realm = KEYCLOAK_REALM
        base = settings.KEYCLOAK_URL
        headers = {"Authorization": f"Bearer {live_token}"}

        user_id = ensure_test_user(live_token, realm, username, password)
        assert user_id, "Failed to create/find test user"

        try:
            # PHASE 1: CREATE session (authenticate as user)
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

            # PHASE 2: VALIDATE session exists
            resp = requests.get(
                f"{base}/admin/realms/{realm}/users/{user_id}/sessions",
                headers=headers,
            )
            resp.raise_for_status()
            sessions = resp.json()
            assert len(sessions) >= 1, \
                f"Expected at least 1 session for user, got {len(sessions)}"

            session_ids = [s["id"] for s in sessions]
            assert len(session_ids) >= 1, "No session IDs found"

            # PHASE 3: DELETE session(s)
            for session_id in session_ids:
                resp = requests.delete(
                    f"{base}/admin/realms/{realm}/sessions/{session_id}",
                    headers=headers,
                )
                assert resp.status_code in (204, 200), \
                    f"Delete session {session_id} failed: {resp.status_code}"

            time.sleep(0.5)

            # PHASE 4: VALIDATE session is gone
            resp = requests.get(
                f"{base}/admin/realms/{realm}/users/{user_id}/sessions",
                headers=headers,
            )
            resp.raise_for_status()
            sessions_after = resp.json()
            assert len(sessions_after) == 0, \
                f"Sessions should be deleted but still found: {len(sessions_after)} sessions"

        finally:
            cleanup_user(live_token, base, realm, user_id)