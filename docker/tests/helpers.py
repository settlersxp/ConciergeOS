#!/usr/bin/env python3
"""
helpers.py - Shared test utilities for the docker/tests suite.

Centralized helpers to eliminate duplication across test files.
"""

import re
import subprocess
import time
from typing import Any

import requests


# ======================================================================
# Constants
# ======================================================================

PUBLIC_BASE = "https://out-customer.com"


# ======================================================================
# Role Attributes Helper
# ======================================================================


def make_roles_with_attrs(**kwargs) -> dict[str, dict[str, list[str]]]:
    """Build a roles_with_attrs dict for testing.

    Usage:
        roles = make_roles_with_attrs(
            **{"settings:view": {"paths": ["/settings"], "menus": ["settings"]}}
        )
    """
    result: dict[str, dict[str, list[str]]] = {}
    for role_name, attrs in kwargs.items():
        result[role_name] = {
            "paths": attrs.get("paths", []),
            "menus": attrs.get("menus", []),
        }
    return result


# ======================================================================
# Caddy Route Helpers
# ======================================================================


def find_deny_rule_for_role(routes: list[dict[str, Any]], role_name: str) -> dict | None:
    """Search Caddy routes for a deny rule referencing the given role."""
    for route in routes:
        route_str = str(route)
        if f"role:{role_name}" in route_str:
            return route
    return None


# ======================================================================
# Valkey Client Helpers
# ======================================================================


class DockerExecValkeyClient:
    """Proxy Valkey client that executes commands inside the valkey container via docker exec."""

    def __init__(self, container: str = "valkey"):
        self._container = container

    def _exec(self, *args: str) -> str:
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


def get_valkey_client(VALKEY_URL: str):
    """Connect to the live Valkey instance.

    Tries direct connection first, falls back to docker exec.
    """
    import valkey as valkey_lib

    # Try direct connection first (inside container on Docker network)
    try:
        r = valkey_lib.from_url(VALKEY_URL)
        r.ping()
        return r
    except Exception:
        pass

    # Fallback: connect via docker exec (from host)
    try:
        client = DockerExecValkeyClient()
        if client.ping():
            return client
    except Exception:
        pass

    raise RuntimeError(
        "Cannot connect to Valkey. Ensure the Docker stack is running "
        "and the 'valkey' container is accessible."
    )


def count_oauth2_proxy_sessions(r, SESSION_KEY_PREFIX: str) -> int:
    """Count session keys matching the oauth2-proxy pattern in Valkey."""
    count = 0
    cursor = 0
    pattern = f"{SESSION_KEY_PREFIX}*"
    while True:
        cursor, keys = r.scan(cursor=cursor, match=pattern, count=100)
        count += len(keys)
        if cursor == 0:
            break
    return count


def list_oauth2_proxy_sessions(r, SESSION_KEY_PREFIX: str) -> list[bytes]:
    """List all session keys matching the oauth2-proxy pattern in Valkey."""
    keys = []
    cursor = 0
    pattern = f"{SESSION_KEY_PREFIX}*"
    while True:
        cursor, batch = r.scan(cursor=cursor, match=pattern, count=100)
        keys.extend(batch)
        if cursor == 0:
            break
    return keys


# ======================================================================
# Keycloak User Helpers
# ======================================================================


def ensure_test_user(live_token: str, KEYCLOAK_REALM: str,
                     username: str, password: str) -> str:
    """Create or find a test user in Keycloak.

    Returns the user_id if successful.
    """
    from keycloak_setup.users import create_user
    return create_user(live_token, KEYCLOAK_REALM, username, password)


def cleanup_user(live_token: str, KEYCLOAK_URL: str, KEYCLOAK_REALM: str, user_id: str) -> None:
    """Delete a user from Keycloak (idempotent)."""
    try:
        requests.delete(
            f"{KEYCLOAK_URL}/admin/realms/{KEYCLOAK_REALM}/users/{user_id}",
            headers={"Authorization": f"Bearer {live_token}"},
        )
    except Exception:
        pass


# ======================================================================
# OAuth2 Login Flow Helper
# ======================================================================


def oauth2_login_flow(live_token: str, KEYCLOAK_URL: str, KEYCLOAK_REALM: str,
                      username: str, password: str) -> tuple[requests.Session, str | None]:
    """Perform a full OAuth2 login flow through oauth2-proxy + Keycloak.

    Creates the test user, performs OIDC login via oauth2-proxy, and returns
    the authenticated requests.Session along with the user_id for cleanup.

    Returns:
        (session, user_id) - session is the authenticated requests.Session,
        user_id is needed for cleanup (may be None if user creation failed).
    """
    user_id = ensure_test_user(live_token, KEYCLOAK_REALM, username, password)

    sess = requests.Session()
    sess.trust_env = False

    # Step 1: Initiate OAuth2 flow
    resp = sess.get(
        f"{PUBLIC_BASE}/oauth2/start",
        allow_redirects=True,
        verify=False,
        timeout=30,
    )

    # Step 2: Submit Keycloak login form
    form_data = {"username": username, "password": password, "credentialId": ""}

    execution_match = re.search(r'name="execution"\s+value="([^"]+)"', resp.text)
    if execution_match:
        form_data["execution"] = execution_match.group(1)

    action_match = re.search(r'action="([^"]+)"', resp.text)
    if action_match:
        form_action = action_match.group(1)
        if form_action.startswith("/"):
            form_action = f"{PUBLIC_BASE}{form_action}"
    else:
        form_action = resp.url

    sess.post(form_action, data=form_data, allow_redirects=True, verify=False, timeout=30)
    time.sleep(1)

    return sess, user_id


# ======================================================================
# Docker Compose Config Helpers
# ======================================================================


def resolve_env_defaults(raw: str) -> str:
    """Resolve ${VAR:-default} and ${VAR} patterns to their default values."""
    raw = re.sub(r'\$\{[^}:]+:-([^}]+)\}', r'\1', raw)
    raw = re.sub(r'\$\{[^}]+\}', '', raw)
    return raw


def extract_compose_env_var(content: str, var_name: str) -> str | None:
    """Extract an environment variable value from docker-compose.yaml content.

    Resolves ${VAR:-default} patterns.
    """
    match = re.search(rf'{var_name}\s*=\s*(\S+)', content)
    if not match:
        return None
    raw = match.group(1).strip('"\'')
    return resolve_env_defaults(raw)


# ======================================================================
# Sample Data
# ======================================================================


def sample_events() -> list[dict[str, str]]:
    """Return a list of mock Keycloak admin events."""
    return [
        {"id": "evt-001", "operationType": "CREATE", "resourceType": "REALM_ROLE"},
        {"id": "evt-002", "operationType": "UPDATE", "resourceType": "ROLE"},
        {"id": "evt-003", "operationType": "LOGIN", "resourceType": "USER"},
    ]


def sample_rbac_json() -> list[dict[str, Any]]:
    """Sample RBAC routes JSON content for testing."""
    return [
        {
            "role": "test:role1",
            "paths": ["/test1", "/test1/*"],
            "menus": ["test1"],
            "message": "Access denied for test1",
        },
        {
            "role": "test:role2",
            "paths": ["/test2"],
            "menus": [],
            "message": "Access denied for test2",
        },
        {
            "role": "test:role3",
            "paths": ["/test3/a", "/test3/b", "/test3/c"],
            "menus": [],
            "message": "",
        },
    ]


def sample_caddy_config() -> dict[str, Any]:
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