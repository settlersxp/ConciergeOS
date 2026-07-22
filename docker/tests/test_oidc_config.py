#!/usr/bin/env python3
"""
test_oidc_config.py - Unit tests for OIDC configuration consistency and reachability.

Validates that:
1. The OAUTH2_PROXY_OIDC_ISSUER_URL in docker-compose.yaml uses the public HTTPS domain
2. The configuration is consistent with the public Keycloak endpoint
3. The Keycloak OIDC discovery endpoint is reachable via the public domain
4. The discovery endpoint returns HTTPS URLs (not internal Docker hostnames)
5. The oauth2-proxy /oauth2/start endpoint redirects to Keycloak (not internal hostname)

These tests make REAL HTTP calls — no mocking. The Docker stack must be running.

Usage:
    cd docker && python3 -m pytest test_oidc_config.py -v
"""

import json
import os
import re
import ssl
from typing import Any

import pytest
import requests

DOCKER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COMPOSE_PATH = os.path.join(DOCKER_DIR, "docker-compose.yaml")

PUBLIC_ISSUER_URL = "https://out-customer.com/auth/realms/production"
PUBLIC_BASE = "https://out-customer.com"
HOST = "localhost"
PORT = 8080

# SSL context for self-signed Caddy CA
SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE


# ======================================================================
# Fixtures
# ======================================================================


@pytest.fixture(scope="session")
def compose_content() -> str:
    """Read docker-compose.yaml once per session."""
    with open(COMPOSE_PATH, "r") as f:
        return f.read()


@pytest.fixture(scope="session")
def compose_issuer_url(compose_content: str) -> str | None:
    """Extract OAUTH2_PROXY_OIDC_ISSUER_URL from the docker-compose.yaml environment."""
    # Match the env var line like: - OAUTH2_PROXY_OIDC_ISSUER_URL=${APP_DOMAIN:-https://out-customer.com}/auth/realms/${OIDC_REALM:-production}
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
    match = re.search(
        r'OAUTH2_PROXY_SSL_INSECURE_SKIP_VERIFY\s*=\s*(\S+)',
        compose_content,
    )
    return match.group(1).strip('"\'') if match else None


@pytest.fixture(scope="session")
def compose_session_store_type(compose_content: str) -> str | None:
    """Extract OAUTH2_PROXY_SESSION_STORE_TYPE from docker-compose.yaml."""
    match = re.search(
        r'OAUTH2_PROXY_SESSION_STORE_TYPE\s*=\s*(\S+)',
        compose_content,
    )
    return match.group(1).strip('"\'') if match else None


@pytest.fixture(scope="session")
def compose_redis_connection_url(compose_content: str) -> str | None:
    """Extract OAUTH2_PROXY_REDIS_CONNECTION_URL from docker-compose.yaml."""
    match = re.search(
        r'OAUTH2_PROXY_REDIS_CONNECTION_URL\s*=\s*(\S+)',
        compose_content,
    )
    return match.group(1).strip('"\'') if match else None


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
# Static Config Tests  (no network)
# ======================================================================


class TestComposeIssuerURL:

    def test_issuer_url_exists(self, compose_issuer_url: str | None):
        assert compose_issuer_url is not None, \
            "OAUTH2_PROXY_OIDC_ISSUER_URL not found in docker-compose.yaml"

    def test_issuer_url_is_https_public(self, compose_issuer_url: str | None):
        assert compose_issuer_url is not None
        assert compose_issuer_url.startswith("https://out-customer.com"), \
            f"Must start with https://out-customer.com, got: {compose_issuer_url}"

    def test_issuer_url_no_internal_hostname(self, compose_issuer_url: str | None):
        assert compose_issuer_url is not None
        assert "keycloak:" not in compose_issuer_url, \
            f"Must NOT contain internal Docker hostname, got: {compose_issuer_url}"
        assert "localhost" not in compose_issuer_url, \
            f"Must NOT contain localhost, got: {compose_issuer_url}"

    def test_issuer_url_matches_public(self, compose_issuer_url: str | None):
        assert compose_issuer_url == PUBLIC_ISSUER_URL


class TestComposeSessionConfig:

    def test_ssl_insecure_skip_verify_enabled(self, compose_ssl_insecure_skip_verify: str | None):
        assert compose_ssl_insecure_skip_verify is not None, \
            "OAUTH2_PROXY_SSL_INSECURE_SKIP_VERIFY not found in docker-compose.yaml"
        assert compose_ssl_insecure_skip_verify.lower() == "true", \
            f"OAUTH2_PROXY_SSL_INSECURE_SKIP_VERIFY must be true, got {compose_ssl_insecure_skip_verify}"

    def test_session_store_type_redis(self, compose_session_store_type: str | None):
        assert compose_session_store_type is not None, \
            "OAUTH2_PROXY_SESSION_STORE_TYPE not found in docker-compose.yaml"
        assert compose_session_store_type == "redis", \
            f"OAUTH2_PROXY_SESSION_STORE_TYPE must be redis, got {compose_session_store_type}"

    def test_redis_connection_url_set(self, compose_redis_connection_url: str | None):
        assert compose_redis_connection_url is not None, \
            "OAUTH2_PROXY_REDIS_CONNECTION_URL not found in docker-compose.yaml"
        assert compose_redis_connection_url.startswith("redis://"), \
            f"OAUTH2_PROXY_REDIS_CONNECTION_URL must start with redis://, got {compose_redis_connection_url}"


# ======================================================================
# Network Tests  (require running Docker stack)
# ======================================================================


class TestDiscoveryEndpointReachable:

    def test_reachable_via_public(self, discovery_config_public: dict[str, Any]):
        """Discovery endpoint reachable through Caddy → Keycloak proxy."""
        assert "issuer" in discovery_config_public

    def test_reachable_via_direct(self, discovery_config_direct: dict[str, Any]):
        """Discovery endpoint reachable directly on localhost:8080."""
        assert "issuer" in discovery_config_direct

    def test_public_and_direct_return_same_keys(
        self,
        discovery_config_public: dict[str, Any],
        discovery_config_direct: dict[str, Any],
    ):
        """Both endpoints return the same set of keys."""
        expected_keys = {
            "issuer",
            "authorization_endpoint",
            "token_endpoint",
            "userinfo_endpoint",
            "jwks_uri",
            "end_session_endpoint",
        }
        for key in expected_keys:
            assert key in discovery_config_public, f"Missing {key} in public response"
            assert key in discovery_config_direct, f"Missing {key} in direct response"


class TestDiscoveryReturnsPublicHTTPS:

    def test_issuer_is_public_https(self, discovery_config_public: dict[str, Any]):
        url = discovery_config_public["issuer"]
        assert url.startswith("https://out-customer.com"), \
            f"issuer must be https://out-customer.com, got: {url}"

    def test_authorization_endpoint_is_public_https(self, discovery_config_public: dict[str, Any]):
        url = discovery_config_public["authorization_endpoint"]
        assert url.startswith("https://out-customer.com"), \
            f"authorization_endpoint must be https://out-customer.com, got: {url}"

    def test_token_endpoint_is_public_https(self, discovery_config_public: dict[str, Any]):
        url = discovery_config_public["token_endpoint"]
        assert url.startswith("https://out-customer.com"), \
            f"token_endpoint must be https://out-customer.com, got: {url}"

    def test_userinfo_endpoint_is_public_https(self, discovery_config_public: dict[str, Any]):
        url = discovery_config_public["userinfo_endpoint"]
        assert url.startswith("https://out-customer.com"), \
            f"userinfo_endpoint must be https://out-customer.com, got: {url}"

    def test_jwks_uri_is_public_https(self, discovery_config_public: dict[str, Any]):
        url = discovery_config_public["jwks_uri"]
        assert url.startswith("https://out-customer.com"), \
            f"jwks_uri must be https://out-customer.com, got: {url}"

    def test_end_session_endpoint_is_public_https(self, discovery_config_public: dict[str, Any]):
        url = discovery_config_public["end_session_endpoint"]
        assert url.startswith("https://out-customer.com"), \
            f"end_session_endpoint must be https://out-customer.com, got: {url}"

    def test_all_endpoints_no_internal_hostnames(self, discovery_config_public: dict[str, Any]):
        """No endpoint in the discovery response contains internal Docker hostnames."""
        forbidden = ["keycloak:", "localhost", "127.0.0.1", "172.", "192.168."]
        for key, url in discovery_config_public.items():
            if not isinstance(url, str):
                continue
            for pattern in forbidden:
                assert pattern not in url, \
                    f"{key} contains internal hostname pattern '{pattern}': {url}"


class TestAuthorizationEndpoint:

    def test_no_internal_hostname(self, discovery_config_public: dict[str, Any]):
        auth_url = discovery_config_public["authorization_endpoint"]
        forbidden = ["keycloak:", "localhost", "127.0.0.1", "172.", "192.168."]
        for pattern in forbidden:
            assert pattern not in auth_url, \
                f"authorization_endpoint contains '{pattern}': {auth_url}"

    def test_starts_with_public_domain(self, discovery_config_public: dict[str, Any]):
        auth_url = discovery_config_public["authorization_endpoint"]
        assert auth_url.startswith("https://out-customer.com"), \
            f"authorization_endpoint must start with https://out-customer.com, got: {auth_url}"

    def test_contains_openid_connect_auth_path(self, discovery_config_public: dict[str, Any]):
        auth_url = discovery_config_public["authorization_endpoint"]
        assert "/protocol/openid-connect/auth" in auth_url, \
            f"authorization_endpoint must contain /protocol/openid-connect/auth: {auth_url}"


class TestSignInRedirect:

    def test_start_redirects_to_keycloak(self):
        """
        Hitting /oauth2/start must redirect (302) to Keycloak's authorization
        endpoint. The redirect Location must be a public URL.

        Note: /oauth2/sign_in renders an HTML page (200) with a login button,
        whereas /oauth2/start directly initiates the OAuth2 flow with a 302.
        """
        start_url = f"{PUBLIC_BASE}/oauth2/start"

        resp = requests.get(start_url, timeout=10, verify=False, allow_redirects=False)

        # Expect a 302 redirect
        assert resp.status_code == 302, \
            f"Expected 302 redirect from /oauth2/start, got {resp.status_code}"

        location = resp.headers.get("Location", "")
        assert location, "Redirect Location header is empty"

    def test_start_redirect_no_internal_hostname(self):
        """
        The redirect Location must NOT contain internal Docker hostnames.
        """
        start_url = f"{PUBLIC_BASE}/oauth2/start"

        resp = requests.get(start_url, timeout=10, verify=False, allow_redirects=False)
        location = resp.headers.get("Location", "")

        forbidden = ["keycloak:", "localhost:8080", "172.", "192.168."]
        for pattern in forbidden:
            assert pattern not in location, \
                f"Redirect contains internal hostname '{pattern}': {location}"

    def test_start_redirect_points_to_auth_endpoint(self):
        """
        The redirect Location must point to Keycloak's authorization endpoint.
        """
        start_url = f"{PUBLIC_BASE}/oauth2/start"

        resp = requests.get(start_url, timeout=10, verify=False, allow_redirects=False)
        location = resp.headers.get("Location", "")

        assert "/protocol/openid-connect/auth" in location or "/auth/realms/" in location, \
            f"Redirect must point to Keycloak auth endpoint: {location}"

    def test_start_redirect_is_public_https(self):
        """
        The redirect Location must start with https://out-customer.com.
        """
        start_url = f"{PUBLIC_BASE}/oauth2/start"

        resp = requests.get(start_url, timeout=10, verify=False, allow_redirects=False)
        location = resp.headers.get("Location", "")

        assert location.startswith("https://out-customer.com"), \
            f"Redirect must start with https://out-customer.com: {location}"