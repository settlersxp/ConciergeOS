#!/usr/bin/env python3
"""
test_oidc_config.py - Unit tests for OIDC configuration consistency and reachability.

Validates that:
1. The oidc_issuer_url in oidc-main.toml uses the public HTTPS domain
2. The docker-compose.yaml --oidc-issuer-url flag matches the TOML config
3. Both configs are consistent with each other
4. The Keycloak OIDC discovery endpoint is reachable via the public domain
5. The discovery endpoint returns HTTPS URLs (not internal Docker hostnames)
6. The oauth2-proxy /oauth2/sign_in endpoint redirects to Keycloak (not internal hostname)

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

DOCKER_DIR = os.path.dirname(os.path.abspath(__file__))
TOML_PATH = os.path.join(DOCKER_DIR, "oidc-main.toml")
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
def toml_content() -> str:
    """Read oidc-main.toml once per session."""
    with open(TOML_PATH, "r") as f:
        return f.read()


@pytest.fixture(scope="session")
def compose_content() -> str:
    """Read docker-compose.yaml once per session."""
    with open(COMPOSE_PATH, "r") as f:
        return f.read()


@pytest.fixture(scope="session")
def toml_issuer_url(toml_content: str) -> str | None:
    """Extract oidc_issuer_url from the TOML config."""
    match = re.search(r'oidc_issuer_url\s*=\s*"([^"]+)"', toml_content)
    return match.group(1) if match else None


@pytest.fixture(scope="session")
def compose_issuer_url(compose_content: str) -> str | None:
    """Extract --oidc-issuer-url from the docker-compose.yaml command."""
    match = re.search(r'--oidc-issuer-url\s*=\s*(https?://[^\s]+)', compose_content)
    if match:
        url = match.group(1)
        url = re.sub(r'\$\{OIDC_REALM:-production\}', 'production', url)
        url = re.sub(r'\$\{OIDC_REALM\}', 'production', url)
        return url
    return None


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


class TestTOMLIssuerURL:

    def test_issuer_url_exists(self, toml_issuer_url: str | None):
        assert toml_issuer_url is not None, "oidc_issuer_url not found in oidc-main.toml"

    def test_issuer_url_is_https_public(self, toml_issuer_url: str | None):
        assert toml_issuer_url is not None
        assert toml_issuer_url.startswith("https://out-customer.com"), \
            f"Must start with https://out-customer.com, got: {toml_issuer_url}"

    def test_issuer_url_no_internal_hostname(self, toml_issuer_url: str | None):
        assert toml_issuer_url is not None
        assert "keycloak:" not in toml_issuer_url, \
            f"Must NOT contain internal Docker hostname, got: {toml_issuer_url}"
        assert "localhost" not in toml_issuer_url, \
            f"Must NOT contain localhost, got: {toml_issuer_url}"

    def test_issuer_url_matches_public(self, toml_issuer_url: str | None):
        assert toml_issuer_url == PUBLIC_ISSUER_URL


class TestComposeIssuerURL:

    def test_issuer_url_exists(self, compose_issuer_url: str | None):
        assert compose_issuer_url is not None, \
            "--oidc-issuer-url not found in docker-compose.yaml"

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


class TestConfigConsistency:

    def test_toml_and_compose_urls_match(
        self,
        toml_issuer_url: str | None,
        compose_issuer_url: str | None,
    ):
        assert toml_issuer_url is not None
        assert compose_issuer_url is not None
        assert toml_issuer_url == compose_issuer_url, \
            f"TOML: {toml_issuer_url} != Compose: {compose_issuer_url}"

    def test_ssl_insecure_skip_verify_enabled(self, toml_content: str):
        match = re.search(r'ssl_insecure_skip_verify\s*=\s*(\S+)', toml_content)
        assert match is not None, "ssl_insecure_skip_verify not found in oidc-main.toml"
        assert match.group(1).lower() == "true", \
            f"ssl_insecure_skip_verify must be true, got {match.group(1)}"


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

    def test_sign_in_redirects_to_keycloak(self):
        """
        Hitting /oauth2/sign_in must redirect to Keycloak's authorization
        endpoint. The redirect Location must be a public URL.
        """
        sign_in_url = f"{PUBLIC_BASE}/oauth2/sign_in"

        resp = requests.get(sign_in_url, timeout=10, verify=False, allow_redirects=False)

        # Expect a 302 redirect
        assert resp.status_code == 302, \
            f"Expected 302 redirect from /oauth2/sign_in, got {resp.status_code}"

        location = resp.headers.get("Location", "")
        assert location, "Redirect Location header is empty"

    def test_sign_in_redirect_no_internal_hostname(self):
        """
        The redirect Location must NOT contain internal Docker hostnames.
        """
        sign_in_url = f"{PUBLIC_BASE}/oauth2/sign_in"

        resp = requests.get(sign_in_url, timeout=10, verify=False, allow_redirects=False)
        location = resp.headers.get("Location", "")

        forbidden = ["keycloak:", "localhost:8080", "172.", "192.168."]
        for pattern in forbidden:
            assert pattern not in location, \
                f"Redirect contains internal hostname '{pattern}': {location}"

    def test_sign_in_redirect_points_to_auth_endpoint(self):
        """
        The redirect Location must point to Keycloak's authorization endpoint.
        """
        sign_in_url = f"{PUBLIC_BASE}/oauth2/sign_in"

        resp = requests.get(sign_in_url, timeout=10, verify=False, allow_redirects=False)
        location = resp.headers.get("Location", "")

        assert "/protocol/openid-connect/auth" in location or "/auth/realms/" in location, \
            f"Redirect must point to Keycloak auth endpoint: {location}"

    def test_sign_in_redirect_is_public_https(self):
        """
        The redirect Location must start with https://out-customer.com.
        """
        sign_in_url = f"{PUBLIC_BASE}/oauth2/sign_in"

        resp = requests.get(sign_in_url, timeout=10, verify=False, allow_redirects=False)
        location = resp.headers.get("Location", "")

        assert location.startswith("https://out-customer.com"), \
            f"Redirect must start with https://out-customer.com: {location}"