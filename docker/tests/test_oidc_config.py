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

from typing import Any

import pytest
import requests

from fixtures import (
    PUBLIC_BASE,
    PUBLIC_ISSUER_URL,
    compose_issuer_url,
    compose_ssl_insecure_skip_verify,
    compose_session_store_type,
    compose_redis_connection_url,
    discovery_config_public,
    discovery_config_direct,
)


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

    @pytest.mark.parametrize("endpoint_key", [
        "issuer",
        "authorization_endpoint",
        "token_endpoint",
        "userinfo_endpoint",
        "jwks_uri",
        "end_session_endpoint",
    ])
    def test_endpoint_is_public_https(
        self, discovery_config_public: dict[str, Any], endpoint_key: str
    ):
        """All discovery endpoints must start with https://out-customer.com."""
        url = discovery_config_public[endpoint_key]
        assert url.startswith("https://out-customer.com"), \
            f"{endpoint_key} must start with https://out-customer.com, got: {url}"

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

    def _get_redirect_location(self) -> str:
        """Hit /oauth2/start and return the redirect Location header."""
        resp = requests.get(
            f"{PUBLIC_BASE}/oauth2/start",
            timeout=10,
            verify=False,
            allow_redirects=False,
        )
        assert resp.status_code == 302, \
            f"Expected 302 redirect from /oauth2/start, got {resp.status_code}"
        return resp.headers.get("Location", "")

    def test_start_redirects_to_keycloak(self):
        """Hitting /oauth2/start must redirect (302) to Keycloak's authorization endpoint."""
        location = self._get_redirect_location()
        assert location, "Redirect Location header is empty"

    def test_start_redirect_no_internal_hostname(self):
        """The redirect Location must NOT contain internal Docker hostnames."""
        location = self._get_redirect_location()
        forbidden = ["keycloak:", "localhost:8080", "172.", "192.168."]
        for pattern in forbidden:
            assert pattern not in location, \
                f"Redirect contains internal hostname '{pattern}': {location}"

    def test_start_redirect_points_to_auth_endpoint(self):
        """The redirect Location must point to Keycloak's authorization endpoint."""
        location = self._get_redirect_location()
        assert "/protocol/openid-connect/auth" in location or "/auth/realms/" in location, \
            f"Redirect must point to Keycloak auth endpoint: {location}"

    def test_start_redirect_is_public_https(self):
        """The redirect Location must start with https://out-customer.com."""
        location = self._get_redirect_location()
        assert location.startswith("https://out-customer.com"), \
            f"Redirect must start with https://out-customer.com: {location}"