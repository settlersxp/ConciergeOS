#!/usr/bin/env python3
"""
conftest.py - Shared fixtures for role_sync integration tests.

All test files in this directory import these fixtures.
Run with: cd docker && python3 -m pytest tests/ -v
"""

import os
import sys

import pytest
import requests

# Load shared settings to ensure consistent defaults
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from settings import settings

# Set env vars from shared settings (only if not already set)
os.environ.setdefault("KEYCLOAK_URL", settings.KEYCLOAK_URL)
os.environ.setdefault("KEYCLOAK_REALM", settings.KEYCLOAK_REALM)
os.environ.setdefault("KEYCLOAK_ADMIN_USER", settings.KEYCLOAK_ADMIN_USER)
os.environ.setdefault("KEYCLOAK_ADMIN_PASSWORD", settings.KEYCLOAK_ADMIN_PASSWORD)
os.environ.setdefault("CADDY_ADMIN_URL", settings.CADDY_ADMIN_URL)
os.environ.setdefault("SYNC_INTERVAL", str(settings.SYNC_INTERVAL))
os.environ.setdefault("VALKEY_URL", settings.VALKEY_URL)
os.environ.setdefault("SESSION_COOKIE_NAME", settings.SESSION_COOKIE_NAME)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rbac_sync.config import (
    KEYCLOAK_URL,
    KEYCLOAK_REALM,
    VALKEY_URL,
)
from settings import settings


# ======================================================================
# Fixtures
# ======================================================================


@pytest.fixture(scope="session")
def live_token():
    """Authenticate against the live Keycloak instance once per session."""
    resp = requests.post(
        f"{KEYCLOAK_URL}/realms/master/protocol/openid-connect/token",
        data={
            "grant_type": "password",
            "client_id": "admin-cli",
            "username": settings.KEYCLOAK_ADMIN_USER,
            "password": settings.KEYCLOAK_ADMIN_PASSWORD,
        },
    )
    resp.raise_for_status()
    token = resp.json().get("access_token")
    assert token, "No access_token from Keycloak"
    return token


@pytest.fixture
def sample_caddy_config():
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


# ======================================================================
# Fixtures: Live Keycloak role lifecycle (create + cleanup with attributes)
# ======================================================================


@pytest.fixture(autouse=True)
def _clear_sync_checkpoint(monkeypatch, pytestconfig):
    """Clear the Valkey sync timestamp and disable sync_is_current() so initial_sync() never skips.

    This fixture does two things:
    1. Deletes the role_sync:sync_ts key from Valkey
    2. Monkeypatches rbac_sync.sync_is_current to always return False

    This ensures that every call to initial_sync() in tests will actually
    rebuild the routes from scratch, which is required for tests that call
    initial_sync() multiple times within the same test (e.g., create -> sync ->
    validate -> delete -> sync -> validate).

    NOTE: The monkeypatch is skipped for test_event_persistence.py because those
    tests directly assert on sync_is_current() behavior.
    """
    import valkey as valkey_lib
    try:
        r = valkey_lib.from_url(VALKEY_URL)
        r.delete("role_sync:sync_ts")
    except Exception:
        pass

    # Only monkeypatch sync_is_current for non-event-persistence tests
    current_test = os.environ.get("PYTEST_CURRENT_TEST", "")
    if "test_event_persistence" not in current_test:
        from rbac_sync import session_management
        monkeypatch.setattr(session_management, "sync_is_current", lambda: False)


@pytest.fixture
def live_test_role(live_token):
    """Create a real role in Keycloak with paths/menus attributes for integration testing.

    Yields the role name after creation, and guarantees cleanup.
    Attributes are stored directly in Keycloak (no external YAML mapping needed).
    """
    role_name = "test:cof-integration-role"
    realm = KEYCLOAK_REALM
    base = KEYCLOAK_URL
    headers = {"Authorization": f"Bearer {live_token}", "Content-Type": "application/json"}

    # ── CREATE role in Keycloak with attributes ───────────────────
    # Step 1: Create role (idempotent)
    resp = requests.get(
        f"{base}/admin/realms/{realm}/roles/{role_name}",
        headers=headers,
    )
    if resp.status_code != 200:
        resp = requests.post(
            f"{base}/admin/realms/{realm}/roles",
            headers=headers,
            json={"name": role_name, "description": "CI integration test role"},
        )
        resp.raise_for_status()

    # Step 2: Fetch and update with attributes
    resp = requests.get(
        f"{base}/admin/realms/{realm}/roles/{role_name}",
        headers=headers,
    )
    resp.raise_for_status()
    role_data = resp.json()
    role_data["attributes"] = {
        "paths": ["/test-cof", "/test-cof/*"],
        "menus": ["test-cof"],
    }
    resp = requests.put(
        f"{base}/admin/realms/{realm}/roles/{role_name}",
        headers=headers,
        json=role_data,
    )
    resp.raise_for_status()

    yield role_name

    # ── CLEANUP: delete role from Keycloak ───────────────────────
    try:
        resp = requests.delete(
            f"{base}/admin/realms/{realm}/roles/{role_name}",
            headers=headers,
        )
        # 204 = success, 404 = already gone
        assert resp.status_code in (204, 404), \
            f"Failed to delete role {role_name}: {resp.status_code}"
    except Exception:
        pass