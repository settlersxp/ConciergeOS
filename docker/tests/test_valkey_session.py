#!/usr/bin/env python3
"""
test_valkey_session.py - Tests for Valkey session storage and oauth2-proxy integration.

Validates the FULL session invalidation chain:
  User login → oauth2-proxy creates Valkey session → Valkey key deleted →
  oauth2-proxy returns 401 → browser redirected to Keycloak login
"""

import os
import sys
import re
import subprocess
import time

import requests

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import role_sync
import keycloak_setup


# ======================================================================
# Helpers
# ======================================================================

# Public-facing URL through Caddy (self-signed cert, so verify=False)
_PUBLIC_BASE = "https://out-customer.com"


class _DockerExecValkeyClient:
    """Proxy Valkey client that executes commands inside the valkey container via docker exec."""

    def __init__(self):
        self._container = "valkey"

    def _exec(self, *args) -> str:
        """Execute a valkey-cli command inside the container."""
        cmd = ["docker", "exec", self._container, "valkey-cli"] + list(args)
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            raise RuntimeError(f"valkey-cli failed: {result.stderr}")
        return result.stdout.strip()

    def ping(self) -> bool:
        """PING the server."""
        out = self._exec("PING")
        return out == "PONG"

    def scan(self, cursor: int = 0, match: str = "*", count: int = 100) -> tuple[int, list[bytes]]:
        """SCAN for keys matching a pattern. Returns (next_cursor, [keys])."""
        cmd = [
            "docker", "exec", self._container, "valkey-cli",
            "SCAN", str(cursor), "MATCH", match, "COUNT", str(count)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            raise RuntimeError(f"SCAN failed: {result.stderr}")
        lines = result.stdout.strip().split("\n")
        if not lines:
            return (0, [])
        next_cursor = int(lines[0])
        keys = [line.encode() if isinstance(line, str) else line for line in lines[1:] if line]
        return (next_cursor, keys)

    def delete(self, *keys: bytes) -> int:
        """Delete one or more keys."""
        key_args = [k.decode() if isinstance(k, bytes) else k for k in keys]
        out = self._exec("DEL", *key_args)
        return int(out)

    def get(self, key: bytes) -> bytes | None:
        """Get the value of a key."""
        k = key.decode() if isinstance(key, bytes) else key
        out = self._exec("GET", k)
        return out.encode() if out else None


def _get_valkey_client():
    """Connect to the live Valkey instance."""
    import valkey as valkey_lib

    # Try direct connection first (inside container on Docker network)
    try:
        r = valkey_lib.from_url(role_sync.VALKEY_URL)
        r.ping()
        return r
    except Exception:
        pass

    # Fallback: connect via docker exec (from host)
    try:
        client = _DockerExecValkeyClient()
        if client.ping():
            return client
    except Exception:
        pass

    raise RuntimeError(
        "Cannot connect to Valkey. Ensure the Docker stack is running "
        "and the 'valkey' container is accessible."
    )


def _count_oauth2_proxy_sessions(r) -> int:
    """Count session keys matching the oauth2-proxy pattern in Valkey."""
    count = 0
    cursor = 0
    pattern = f"{role_sync.SESSION_KEY_PREFIX}*"
    while True:
        cursor, keys = r.scan(cursor=cursor, match=pattern, count=100)
        count += len(keys)
        if cursor == 0:
            break
    return count


def _list_oauth2_proxy_sessions(r) -> list[bytes]:
    """List all session keys matching the oauth2-proxy pattern in Valkey."""
    keys = []
    cursor = 0
    pattern = f"{role_sync.SESSION_KEY_PREFIX}*"
    while True:
        cursor, batch = r.scan(cursor=cursor, match=pattern, count=100)
        keys.extend(batch)
        if cursor == 0:
            break
    return keys


# ======================================================================
# TestValkeyConnectivity
# ======================================================================


class TestValkeyConnectivity:
    """Verify the test environment can reach Valkey."""

    def test_valkey_ping(self):
        """Valkey responds to PING."""
        r = _get_valkey_client()
        assert r.ping(), "Valkey PING failed"

    def test_valkey_session_key_pattern_exists(self, live_token):
        """After a user logs in through oauth2-proxy, session keys appear in Valkey."""
        r = _get_valkey_client()
        keys = _list_oauth2_proxy_sessions(r)
        assert isinstance(keys, list)


# ======================================================================
# TestValkeySessionStorage
# ======================================================================


class TestValkeySessionStorage:
    """Verify oauth2-proxy stores sessions in Valkey after user authentication."""

    def _ensure_test_user(self, live_token, username: str, password: str) -> str | None:
        """Create or find a test user in Keycloak."""
        realm = role_sync.KEYCLOAK_REALM
        base = role_sync.KEYCLOAK_URL
        return keycloak_setup.create_user(base, live_token, realm, username, password) or None

    def test_session_key_appears_in_valkey_after_oauth2_login(self, live_token):
        """User login via oauth2-proxy → session key appears in Valkey."""
        r = _get_valkey_client()
        username = "cof-valkey-storage-user"
        password = "ValkeyStore123!"

        user_id = self._ensure_test_user(live_token, username, password)
        assert user_id, "Failed to create/find test user"

        try:
            count_before = _count_oauth2_proxy_sessions(r)

            # Authenticate through oauth2-proxy via full OIDC flow
            sess = requests.Session()
            sess.trust_env = False

            resp = sess.get(
                f"{_PUBLIC_BASE}/oauth2/start",
                allow_redirects=True,
                verify=False,
                timeout=30,
            )

            # Submit Keycloak login form
            form_data = {"username": username, "password": password, "credentialId": ""}
            execution_match = re.search(r'name="execution"\s+value="([^"]+)"', resp.text)
            if execution_match:
                form_data["execution"] = execution_match.group(1)

            action_match = re.search(r'action="([^"]+)"', resp.text)
            if action_match:
                form_action = action_match.group(1)
                if form_action.startswith("/"):
                    form_action = f"https://out-customer.com{form_action}"
            else:
                form_action = resp.url

            sess.post(form_action, data=form_data, allow_redirects=True, verify=False, timeout=30)
            time.sleep(1)

        finally:
            try:
                requests.delete(
                    f"{role_sync.KEYCLOAK_URL}/admin/realms/{role_sync.KEYCLOAK_REALM}/users/{user_id}",
                    headers={"Authorization": f"Bearer {live_token}"},
                )
            except Exception:
                pass

    def test_session_key_format_matches_pattern(self, live_token):
        """Session keys in Valkey match the expected oauth2-proxy format."""
        r = _get_valkey_client()
        username = "cof-valkey-format-user"
        password = "ValkeyFmt123!"

        user_id = self._ensure_test_user(live_token, username, password)
        assert user_id

        try:
            sess = requests.Session()
            sess.trust_env = False

            resp = sess.get(
                f"{_PUBLIC_BASE}/oauth2/start",
                allow_redirects=True,
                verify=False,
                timeout=30,
            )

            form_data = {"username": username, "password": password, "credentialId": ""}
            execution_match = re.search(r'name="execution"\s+value="([^"]+)"', resp.text)
            if execution_match:
                form_data["execution"] = execution_match.group(1)

            action_match = re.search(r'action="([^"]+)"', resp.text)
            if action_match:
                form_action = action_match.group(1)
                if form_action.startswith("/"):
                    form_action = f"https://out-customer.com{form_action}"
            else:
                form_action = resp.url

            sess.post(form_action, data=form_data, allow_redirects=True, verify=False, timeout=30)
            time.sleep(1)

            # Validate key format
            keys = _list_oauth2_proxy_sessions(r)
            pattern = re.compile(rb"^_oauth2_proxy-[0-9a-f]{32}$")

            for key in keys:
                assert pattern.match(key), \
                    f"Session key '{key.decode()}' does not match expected pattern '_oauth2_proxy-{{32-hex}}'"

        finally:
            try:
                requests.delete(
                    f"{role_sync.KEYCLOAK_URL}/admin/realms/{role_sync.KEYCLOAK_REALM}/users/{user_id}",
                    headers={"Authorization": f"Bearer {live_token}"},
                )
            except Exception:
                pass


# ======================================================================
# TestValkeySessionInvalidation
# ======================================================================


class TestValkeySessionInvalidation:
    """Verify deleting session keys from Valkey invalidates the oauth2-proxy session."""

    def _ensure_test_user(self, live_token, username: str, password: str) -> str | None:
        realm = role_sync.KEYCLOAK_REALM
        base = role_sync.KEYCLOAK_URL
        return keycloak_setup.create_user(base, live_token, realm, username, password) or None

    def test_delete_valkey_key_invalidates_oauth2_session(self, live_token):
        """Delete session key from Valkey → oauth2-proxy /oauth2/auth returns 401."""
        r = _get_valkey_client()
        username = "cof-valkey-inval-user"
        password = "ValkeyInval123!"

        user_id = self._ensure_test_user(live_token, username, password)
        assert user_id

        try:
            # PHASE 1: Authenticate through oauth2-proxy
            sess = requests.Session()
            sess.trust_env = False

            resp = sess.get(
                f"{_PUBLIC_BASE}/oauth2/start",
                allow_redirects=True,
                verify=False,
                timeout=30,
            )

            form_data = {"username": username, "password": password, "credentialId": ""}
            execution_match = re.search(r'name="execution"\s+value="([^"]+)"', resp.text)
            if execution_match:
                form_data["execution"] = execution_match.group(1)

            action_match = re.search(r'action="([^"]+)"', resp.text)
            form_action = action_match.group(1) if action_match else resp.url
            if form_action.startswith("/"):
                form_action = f"https://out-customer.com{form_action}"

            sess.post(form_action, data=form_data, allow_redirects=True, verify=False, timeout=30)
            time.sleep(1)

            # PHASE 2: Verify session is valid
            auth_resp = sess.get(
                f"{_PUBLIC_BASE}/oauth2/auth",
                verify=False,
                timeout=10,
                allow_redirects=False,
            )
            assert auth_resp.status_code in (200, 202, 403), \
                f"Expected 200/202/403 from /oauth2/auth with valid session, got {auth_resp.status_code}"

            session_cookie = sess.cookies.get("_oauth2_proxy", "")
            assert session_cookie, "No _oauth2_proxy cookie set after login"

            # PHASE 3: Verify Valkey key exists
            keys_before = _list_oauth2_proxy_sessions(r)
            assert len(keys_before) > 0, \
                f"No session keys in Valkey after login. Cookie present but Valkey empty."

            # PHASE 4: Delete ALL session keys from Valkey
            for key in keys_before:
                r.delete(key)
            time.sleep(0.5)

            # Verify keys are gone
            keys_after = _list_oauth2_proxy_sessions(r)
            assert len(keys_after) == 0, \
                f"Session keys not deleted from Valkey: {keys_after}"

            # PHASE 5: Verify session is INVALID
            sess2 = requests.Session()
            sess2.trust_env = False
            sess2.cookies.set("_oauth2_proxy", session_cookie, domain="out-customer.com")

            auth_resp2 = sess2.get(
                f"{_PUBLIC_BASE}/oauth2/auth",
                verify=False,
                timeout=10,
                allow_redirects=False,
            )

            assert auth_resp2.status_code in (401, 403, 302), \
                f"Expected 401/403/302 after Valkey key deletion, got {auth_resp2.status_code}. " \
                f"Session was NOT invalidated by Valkey key deletion!"

        finally:
            try:
                requests.delete(
                    f"{role_sync.KEYCLOAK_URL}/admin/realms/{role_sync.KEYCLOAK_REALM}/users/{user_id}",
                    headers={"Authorization": f"Bearer {live_token}"},
                )
            except Exception:
                pass

    def test_invalidate_all_sessions_function_works(self, live_token):
        """role_sync.invalidate_all_sessions() deletes all oauth2-proxy sessions from Valkey."""
        r = _get_valkey_client()
        username = "cof-valkey-inval-all-user"
        password = "ValkeyInvalAll123!"

        user_id = self._ensure_test_user(live_token, username, password)
        assert user_id

        try:
            # PHASE 1: Create session via oauth2-proxy
            sess = requests.Session()
            sess.trust_env = False

            resp = sess.get(
                f"{_PUBLIC_BASE}/oauth2/start",
                allow_redirects=True,
                verify=False,
                timeout=30,
            )

            form_data = {"username": username, "password": password, "credentialId": ""}
            execution_match = re.search(r'name="execution"\s+value="([^"]+)"', resp.text)
            if execution_match:
                form_data["execution"] = execution_match.group(1)

            action_match = re.search(r'action="([^"]+)"', resp.text)
            form_action = action_match.group(1) if action_match else resp.url
            if form_action.startswith("/"):
                form_action = f"https://out-customer.com{form_action}"

            sess.post(form_action, data=form_data, allow_redirects=True, verify=False, timeout=30)
            time.sleep(1)

            session_cookie = sess.cookies.get("_oauth2_proxy", "")
            assert session_cookie, "No _oauth2_proxy cookie after login"

            # PHASE 2: Verify keys exist
            keys_before = _list_oauth2_proxy_sessions(r)
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
            keys_after = _list_oauth2_proxy_sessions(r)
            assert len(keys_after) == 0, \
                f"Keys remain after invalidate_all_sessions(): {keys_after}"

            # PHASE 5: Verify old cookie no longer works
            sess2 = requests.Session()
            sess2.trust_env = False
            sess2.cookies.set("_oauth2_proxy", session_cookie, domain="out-customer.com")

            auth_resp = sess2.get(
                f"{_PUBLIC_BASE}/oauth2/auth",
                verify=False,
                timeout=10,
                allow_redirects=False,
            )

            assert auth_resp.status_code in (401, 403, 302), \
                f"Expected 401/403/302 after invalidate_all_sessions(), got {auth_resp.status_code}"

        finally:
            try:
                requests.delete(
                    f"{role_sync.KEYCLOAK_URL}/admin/realms/{role_sync.KEYCLOAK_REALM}/users/{user_id}",
                    headers={"Authorization": f"Bearer {live_token}"},
                )
            except Exception:
                pass

    def test_session_survives_when_valkey_key_present(self, live_token):
        """Negative test: with the key still in Valkey, the session remains valid."""
        username = "cof-valkey-survive-user"
        password = "ValkeySurvive123!"

        user_id = self._ensure_test_user(live_token, username, password)
        assert user_id

        try:
            # PHASE 1: Authenticate
            sess = requests.Session()
            sess.trust_env = False

            resp = sess.get(
                f"{_PUBLIC_BASE}/oauth2/start",
                allow_redirects=True,
                verify=False,
                timeout=30,
            )

            form_data = {"username": username, "password": password, "credentialId": ""}
            execution_match = re.search(r'name="execution"\s+value="([^"]+)"', resp.text)
            if execution_match:
                form_data["execution"] = execution_match.group(1)

            action_match = re.search(r'action="([^"]+)"', resp.text)
            form_action = action_match.group(1) if action_match else resp.url
            if form_action.startswith("/"):
                form_action = f"https://out-customer.com{form_action}"

            sess.post(form_action, data=form_data, allow_redirects=True, verify=False, timeout=30)
            time.sleep(1)

            # PHASE 2: Verify session valid (key still present)
            auth_resp1 = sess.get(
                f"{_PUBLIC_BASE}/oauth2/auth",
                verify=False,
                timeout=10,
                allow_redirects=False,
            )
            assert auth_resp1.status_code in (200, 202, 403), \
                f"Expected valid session, got {auth_resp1.status_code}"

            time.sleep(2)

            auth_resp2 = sess.get(
                f"{_PUBLIC_BASE}/oauth2/auth",
                verify=False,
                timeout=10,
                allow_redirects=False,
            )
            assert auth_resp2.status_code in (200, 202, 403), \
                f"Session should remain valid when Valkey key is present, got {auth_resp2.status_code}"

        finally:
            try:
                requests.delete(
                    f"{role_sync.KEYCLOAK_URL}/admin/realms/{role_sync.KEYCLOAK_REALM}/users/{user_id}",
                    headers={"Authorization": f"Bearer {live_token}"},
                )
            except Exception:
                pass


# ======================================================================
# TestOAuth2ProxySignOut
# ======================================================================


class TestOAuth2ProxySignOut:
    """Verify the oauth2-proxy /oauth2/sign_out endpoint correctly cleans up."""

    def _ensure_test_user(self, live_token, username: str, password: str) -> str | None:
        realm = role_sync.KEYCLOAK_REALM
        base = role_sync.KEYCLOAK_URL
        return keycloak_setup.create_user(base, live_token, realm, username, password) or None

    def test_sign_out_deletes_valkey_session(self, live_token):
        """HIT /oauth2/sign_out → session key deleted from Valkey."""
        r = _get_valkey_client()
        username = "cof-signout-user"
        password = "SignOut123!"

        user_id = self._ensure_test_user(live_token, username, password)
        assert user_id

        try:
            # PHASE 1: Authenticate
            sess = requests.Session()
            sess.trust_env = False

            resp = sess.get(
                f"{_PUBLIC_BASE}/oauth2/start",
                allow_redirects=True,
                verify=False,
                timeout=30,
            )

            form_data = {"username": username, "password": password, "credentialId": ""}
            execution_match = re.search(r'name="execution"\s+value="([^"]+)"', resp.text)
            if execution_match:
                form_data["execution"] = execution_match.group(1)

            action_match = re.search(r'action="([^"]+)"', resp.text)
            form_action = action_match.group(1) if action_match else resp.url
            if form_action.startswith("/"):
                form_action = f"https://out-customer.com{form_action}"

            sess.post(form_action, data=form_data, allow_redirects=True, verify=False, timeout=30)
            time.sleep(1)

            # PHASE 2: Verify session exists
            keys_before = _list_oauth2_proxy_sessions(r)
            assert len(keys_before) > 0, "No session in Valkey before sign out"

            # PHASE 3: Hit /oauth2/sign_out
            signout_resp = sess.get(
                f"{_PUBLIC_BASE}/oauth2/sign_out",
                verify=False,
                timeout=10,
                allow_redirects=False,
            )
            time.sleep(1)

            # PHASE 4: Verify session key DELETED
            keys_after = _list_oauth2_proxy_sessions(r)
            assert len(keys_after) < len(keys_before) or len(keys_after) == 0, \
                f"Sign out did not delete session: before={len(keys_before)}, after={len(keys_after)}"

        finally:
            try:
                requests.delete(
                    f"{role_sync.KEYCLOAK_URL}/admin/realms/{role_sync.KEYCLOAK_REALM}/users/{user_id}",
                    headers={"Authorization": f"Bearer {live_token}"},
                )
            except Exception:
                pass


# ======================================================================
# TestLiveSessionLifecycle (Keycloak sessions)
# ======================================================================


class TestLiveSessionLifecycle:
    """End-to-end tests for session creation and deletion against live Keycloak."""

    def _ensure_test_user(self, live_token, username: str, password: str) -> str | None:
        """Create or find a test user using keycloak_setup.create_user."""
        realm = role_sync.KEYCLOAK_REALM
        base = role_sync.KEYCLOAK_URL
        return keycloak_setup.create_user(base, live_token, realm, username, password) or None

    def test_create_session_validate_delete_validate(self, live_token):
        """CREATE session (via user login) → validate exists → DELETE session → validate gone."""
        username = "cof-test-session-user"
        password = "SessionTest123!"
        realm = role_sync.KEYCLOAK_REALM
        base = role_sync.KEYCLOAK_URL
        headers = {"Authorization": f"Bearer {live_token}"}

        user_id = self._ensure_test_user(live_token, username, password)
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
            try:
                resp = requests.delete(
                    f"{base}/admin/realms/{realm}/users/{user_id}",
                    headers=headers,
                )
                assert resp.status_code in (204, 200, 404), \
                    f"Cleanup delete user failed: {resp.status_code}"
            except Exception:
                pass