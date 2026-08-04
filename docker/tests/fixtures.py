#!/usr/bin/env python3
"""
fixtures.py - Shared pytest fixtures for the docker/tests suite.

All fixtures that don't need to be auto-discovered by pytest (i.e., not in conftest.py)
are defined here and imported by individual test files as needed.
"""

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

import pytest
import requests

from helpers import (
    sample_caddy_config as _sample_caddy_config,
    sample_events as _sample_events,
    sample_rbac_json as _sample_rbac_json,
    extract_compose_env_var,
)


# ======================================================================
# Paths
# ======================================================================

DOCKER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COMPOSE_PATH = os.path.join(DOCKER_DIR, "docker-compose.yaml")

PUBLIC_ISSUER_URL = "https://out-customer.com/auth/realms/production"
PUBLIC_BASE = "https://out-customer.com"
HOST = os.environ.get("OIDC_CONFIG_HOST", "keycloak")
PORT = int(os.environ.get("OIDC_CONFIG_PORT", "8080"))


# ======================================================================
# Sample Data Fixtures
# ======================================================================


@pytest.fixture
def sample_events():
    """Return a list of mock Keycloak admin events."""
    return _sample_events()


@pytest.fixture
def sample_rbac_json():
    """Sample RBAC routes JSON content for testing."""
    return _sample_rbac_json()


@pytest.fixture
def sample_caddy_config():
    """Sample Caddy config that simulates a real config with multiple servers."""
    return _sample_caddy_config()


@pytest.fixture
def json_file(sample_rbac_json):
    """Create a temporary JSON file with sample RBAC content."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(sample_rbac_json, f)
        f.flush()
        yield Path(f.name)
    os.unlink(f.name)


# ======================================================================
# Valkey Fixtures
# ======================================================================


@pytest.fixture()
def _valkey_flush():
    """Flush all role_sync:* keys from Valkey before and after each test.

    Gracefully skips if Valkey is unavailable (e.g., Docker not running).
    Only use this fixture on tests that actually touch Valkey.
    """
    import valkey as valkey_lib

    from rbac_sync.config import VALKEY_URL

    r = valkey_lib.from_url(VALKEY_URL)
    try:
        r.ping()
    except Exception:
        yield
        return

    # Flush before
    cursor = 0
    while True:
        cursor, keys = r.scan(cursor=cursor, match="role_sync:*", count=100)
        if keys:
            r.delete(*keys)
        if cursor == 0:
            break
    yield
    # Flush after
    cursor = 0
    while True:
        cursor, keys = r.scan(cursor=cursor, match="role_sync:*", count=100)
        if keys:
            r.delete(*keys)
        if cursor == 0:
            break


# ======================================================================
# Docker Compose Fixtures
# ======================================================================


@pytest.fixture(scope="session")
def compose_content() -> str:
    """Read docker-compose.yaml once per session."""
    with open(COMPOSE_PATH, "r") as f:
        return f.read()


@pytest.fixture(scope="session")
def compose_issuer_url(compose_content: str) -> str | None:
    """Extract OAUTH2_PROXY_OIDC_ISSUER_URL from the docker-compose.yaml environment."""
    match = re.search(
        r'OAUTH2_PROXY_OIDC_ISSUER_URL\s*=\s*(.+)',
        compose_content,
    )
    if match:
        url = match.group(1)
        # Resolve ${APP_DOMAIN:-https://out-customer.com}
        url = re.sub(r'\$\{APP_DOMAIN:-([^}]+)\}', r'\1', url)
        url = re.sub(r'\$\{APP_DOMAIN\}', 'https://out-customer.com', url)
        # Resolve ${OIDC_REALM:-production}
        url = re.sub(r'\$\{OIDC_REALM:-([^}]+)\}', r'\1', url)
        url = re.sub(r'\$\{OIDC_REALM\}', 'production', url)
        return url
    return None


@pytest.fixture(scope="session")
def compose_ssl_insecure_skip_verify(compose_content: str) -> str | None:
    """Extract OAUTH2_PROXY_SSL_INSECURE_SKIP_VERIFY from docker-compose.yaml."""
    return extract_compose_env_var(compose_content, "OAUTH2_PROXY_SSL_INSECURE_SKIP_VERIFY")


@pytest.fixture(scope="session")
def compose_session_store_type(compose_content: str) -> str | None:
    """Extract OAUTH2_PROXY_SESSION_STORE_TYPE from docker-compose.yaml."""
    return extract_compose_env_var(compose_content, "OAUTH2_PROXY_SESSION_STORE_TYPE")


@pytest.fixture(scope="session")
def compose_redis_connection_url(compose_content: str) -> str | None:
    """Extract OAUTH2_PROXY_REDIS_CONNECTION_URL from docker-compose.yaml."""
    return extract_compose_env_var(compose_content, "OAUTH2_PROXY_REDIS_CONNECTION_URL")


# ======================================================================
# OIDC Discovery Fixtures
# ======================================================================


@pytest.fixture(scope="session")
def discovery_config_public() -> dict[str, Any]:
    """Fetch the OIDC discovery config via the public HTTPS domain (Caddy proxy)."""
    url = f"{PUBLIC_BASE}/auth/realms/production/.well-known/openid-configuration"
    resp = requests.get(url, timeout=10, verify=False)
    resp.raise_for_status()
    return resp.json()


@pytest.fixture(scope="session")
def discovery_config_direct() -> dict[str, Any]:
    """Fetch the OIDC discovery config directly on localhost:8080."""
    url = f"http://{HOST}:{PORT}/auth/realms/production/.well-known/openid-configuration"
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    return resp.json()


# ======================================================================
# Test Role Fixtures
# ======================================================================


@pytest.fixture
def test_role_name():
    """Generate a unique test role name."""
    import time
    return f"test:cof-rbac-{int(time.time())}"