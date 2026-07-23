#!/usr/bin/env python3
"""
conftest.py - Shared fixtures for role_sync integration tests.

All test files in this directory import these fixtures.
Run with: cd docker && python3 -m pytest tests/ -v
"""

import os
import sys
import tempfile
import time

import pytest
import requests
import yaml

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
# Use a local-aware MAPPING_FILE: prefer the Docker path if it exists
# (inside containers), otherwise fall back to the rbac_routes.yaml next
# to the docker/ directory (local development).
_default_mapping = settings.MAPPING_FILE
if not os.path.exists(_default_mapping):
    _local_mapping = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "rbac_routes.yaml")
    if os.path.exists(_local_mapping):
        _default_mapping = _local_mapping
os.environ.setdefault("MAPPING_FILE", _default_mapping)
os.environ.setdefault("VALKEY_URL", settings.VALKEY_URL)
os.environ.setdefault("SESSION_COOKIE_NAME", settings.SESSION_COOKIE_NAME)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import role_sync
import keycloak_setup


# ======================================================================
# Fixtures
# ======================================================================


@pytest.fixture(scope="session")
def live_token():
    """Authenticate against the live Keycloak instance once per session."""
    resp = requests.post(
        f"{role_sync.KEYCLOAK_URL}/realms/master/protocol/openid-connect/token",
        data={
            "grant_type": "password",
            "client_id": "admin-cli",
            "username": role_sync.KEYCLOAK_ADMIN_USER,
            "password": role_sync.KEYCLOAK_ADMIN_PASSWORD,
        },
    )
    resp.raise_for_status()
    token = resp.json().get("access_token")
    assert token, "No access_token from Keycloak"
    return token


@pytest.fixture
def sample_mapping():
    """Sample role-to-path mapping data."""
    return [
        {
            "role": "settings:view",
            "paths": ["/settings", "/settings/*"],
            "message": "Access denied: settings requires viewer role.",
        },
        {
            "role": "models:admin",
            "paths": ["/models", "/models/*"],
        },
    ]


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
# Fixtures: Live Keycloak role lifecycle (create + cleanup)
# ======================================================================


@pytest.fixture(autouse=True)
def _clear_sync_checkpoint(monkeypatch, pytestconfig):
    """Clear the Valkey sync timestamp and disable sync_is_current() so initial_sync() never skips.

    This fixture does two things:
    1. Deletes the role_sync:sync_ts key from Valkey
    2. Monkeypatches role_sync.sync_is_current to always return False

    This ensures that every call to initial_sync() in tests will actually
    rebuild the routes from scratch, which is required for tests that call
    initial_sync() multiple times within the same test (e.g., create -> sync ->
    validate -> delete -> sync -> validate).

    NOTE: The monkeypatch is skipped for test_event_persistence.py because those
    tests directly assert on sync_is_current() behavior.
    """
    import valkey as valkey_lib
    try:
        r = valkey_lib.from_url(role_sync.VALKEY_URL)
        r.delete("role_sync:sync_ts")
    except Exception:
        pass

    # Only monkeypatch sync_is_current for non-event-persistence tests
    # (test_event_persistence.py tests sync_is_current() directly)
    current_test = os.environ.get("PYTEST_CURRENT_TEST", "")
    if "test_event_persistence" not in current_test:
        monkeypatch.setattr(role_sync, "sync_is_current", lambda: False)


@pytest.fixture
def live_test_role(live_token):
    """Create a real role in Keycloak for integration testing, then delete it.

    Yields the role name after creation, and guarantees cleanup.
    Also temporarily adds a mapping entry for the role so the sync
    service can generate a deny rule for it.
    """
    role_name = "test:cof-integration-role"
    realm = role_sync.KEYCLOAK_REALM
    base = role_sync.KEYCLOAK_URL
    headers = {"Authorization": f"Bearer {live_token}"}

    # ── CREATE role in Keycloak (reuse keycloak_setup.create_role) ──
    keycloak_setup.create_role(base, live_token, realm, role_name, "CI integration test role")

    # ── Load existing mapping and add a temporary entry ──────────
    original_mapping_path = role_sync.MAPPING_FILE
    mapping_entry = {
        "role": role_name,
        "paths": ["/test-cof", "/test-cof/*"],
        "message": f"Access denied: this resource requires the {role_name} role.",
    }

    # Read existing mapping (if any)
    existing_mapping = []
    if os.path.exists(original_mapping_path):
        with open(original_mapping_path, "r") as f:
            existing_mapping = yaml.safe_load(f) or []

    # Write temporary mapping file with our test entry
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(existing_mapping + [mapping_entry], f)
        temp_mapping = f.name

    role_sync.MAPPING_FILE = temp_mapping

    # ── Initial sync so the new role's deny rule is pushed ───────
    # (done by the test itself after yield)

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
    finally:
        # Always restore mapping file path and delete temp file
        role_sync.MAPPING_FILE = original_mapping_path
        os.unlink(temp_mapping)