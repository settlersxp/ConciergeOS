#!/usr/bin/env python3
"""
test_oidc_config.py - Unit tests for OIDC configuration consistency.

Validates that:
1. The oidc_issuer_url in oidc-main.toml uses HTTP for internal Docker communication
2. The docker-compose.yaml --oidc-issuer-url flag matches the TOML config
3. The Keycloak OIDC discovery endpoint is reachable
4. The issuer URL protocol matches what Keycloak actually serves

Usage:
    python3 docker/test_oidc_config.py
"""

import json
import os
import re
import sys
import urllib.request

DOCKER_DIR = os.path.dirname(os.path.abspath(__file__))
TOML_PATH = os.path.join(DOCKER_DIR, "oidc-main.toml")
COMPOSE_PATH = os.path.join(DOCKER_DIR, "docker-compose.yaml")

PUBLIC_ISSUER_URL = "https://out-customer.com/auth/realms/production"
HOST = "localhost"
PORT = "8080"


def read_file(path: str) -> str:
    with open(path, "r") as f:
        return f.read()


def extract_toml_issuer_url(content: str) -> str | None:
    """Extract oidc_issuer_url from the TOML config."""
    match = re.search(r'oidc_issuer_url\s*=\s*"([^"]+)"', content)
    return match.group(1) if match else None


def extract_compose_issuer_url(content: str) -> str | None:
    """Extract --oidc-issuer-url from the docker-compose.yaml command."""
    match = re.search(r'--oidc-issuer-url\s*=\s*(https?://[^\s]+)', content)
    if match:
        # Replace environment variable references with default
        url = match.group(1)
        url = re.sub(r'\$\{OIDC_REALM:-production\}', 'production', url)
        url = re.sub(r'\$\{OIDC_REALM\}', 'production', url)
        return url
    return None


def test_toml_issuer_url_matches_public() -> bool:
    """
    Test: oidc_issuer_url in oidc-main.toml must match the public issuer URL
    returned by Keycloak's OIDC discovery endpoint (https://out-customer.com/auth/realms/production).
    The internal network uses HTTP, but the issuer must match the discovery response.
    The ssl_insecure_skip_verify=true handles self-signed certs via host-gateway.
    """
    content = read_file(TOML_PATH)
    url = extract_toml_issuer_url(content)

    if url is None:
        print(f"FAIL: test_toml_issuer_url_matches_public - Could not find oidc_issuer_url in {TOML_PATH}")
        return False

    if url != PUBLIC_ISSUER_URL:
        print(f"FAIL: test_toml_issuer_url_matches_public - Issuer URL does not match public URL:")
        print(f"      Expected: {PUBLIC_ISSUER_URL}")
        print(f"      Got:      {url}")
        return False

    print(f"PASS: test_toml_issuer_url_matches_public - {url}")
    return True


def test_compose_issuer_url_matches_public() -> bool:
    """
    Test: --oidc-issuer-url in docker-compose.yaml must match the public issuer URL
    returned by Keycloak's OIDC discovery endpoint.
    """
    content = read_file(COMPOSE_PATH)
    url = extract_compose_issuer_url(content)

    if url is None:
        print(f"FAIL: test_compose_issuer_url_matches_public - Could not find --oidc-issuer-url in {COMPOSE_PATH}")
        return False

    if url != PUBLIC_ISSUER_URL:
        print(f"FAIL: test_compose_issuer_url_matches_public - Issuer URL does not match public URL:")
        print(f"      Expected: {PUBLIC_ISSUER_URL}")
        print(f"      Got:      {url}")
        return False

    print(f"PASS: test_compose_issuer_url_matches_public - {url}")
    return True


def test_toml_and_compose_urls_consistent() -> bool:
    """
    Test: The issuer URLs in TOML and docker-compose should be consistent
    (both should point to the same internal Keycloak URL).
    """
    toml_content = read_file(TOML_PATH)
    compose_content = read_file(COMPOSE_PATH)
    
    toml_url = extract_toml_issuer_url(toml_content)
    compose_url = extract_compose_issuer_url(compose_content)
    
    if toml_url is None or compose_url is None:
        print("FAIL: test_toml_and_compose_urls_consistent - Could not extract both URLs")
        return False
    
    if toml_url != compose_url:
        print(f"FAIL: test_toml_and_compose_urls_consistent - URLs differ:")
        print(f"      TOML:        {toml_url}")
        print(f"      Compose:     {compose_url}")
        return False
    
    print(f"PASS: test_toml_and_compose_urls_consistent - Both use: {toml_url}")
    return True


def test_discovery_endpoint_reachable() -> bool:
    """
    Test: The OIDC discovery endpoint should be reachable from the host.
    This tests that Keycloak is up and serving the configuration.
    """
    discovery_url = f"http://{HOST}:{PORT}/auth/realms/production/.well-known/openid-configuration"
    
    try:
        req = urllib.request.Request(discovery_url)
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            
            # Verify the issuer is the expected external URL
            issuer = data.get("issuer", "")
            if "out-customer.com" in issuer:
                print(f"PASS: test_discovery_endpoint_reachable - issuer: {issuer}")
                return True
            else:
                print(f"FAIL: test_discovery_endpoint_reachable - Unexpected issuer: {issuer}")
                return False
    except Exception as e:
        print(f"FAIL: test_discovery_endpoint_reachable - {e}")
        print(f"      URL: {discovery_url}")
        return False


def test_discovery_returns_https_public_urls() -> bool:
    """
    Test: The OIDC discovery response should return HTTPS URLs pointing to
    the public domain (out-customer.com), since Caddy terminates SSL externally.
    """
    discovery_url = f"http://{HOST}:{PORT}/auth/realms/production/.well-known/openid-configuration"
    
    try:
        req = urllib.request.Request(discovery_url)
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            
            # Check that key endpoints use https://out-customer.com
            endpoints = [
                "issuer",
                "authorization_endpoint",
                "token_endpoint",
                "userinfo_endpoint",
                "jwks_uri",
            ]
            
            all_https = True
            for ep in endpoints:
                url = data.get(ep, "")
                if not url.startswith("https://out-customer.com"):
                    print(f"FAIL: test_discovery_returns_https_public_urls - {ep} is not https://out-customer.com: {url}")
                    all_https = False
            
            if all_https:
                print(f"PASS: test_discovery_returns_https_public_urls - All endpoints use https://out-customer.com")
                return True
            return False
    except Exception as e:
        print(f"FAIL: test_discovery_returns_https_public_urls - {e}")
        return False


def main():
    print("=" * 70)
    print("OIDC Configuration Tests")
    print("=" * 70)
    
    tests = [
        test_toml_issuer_url_matches_public,
        test_compose_issuer_url_matches_public,
        test_toml_and_compose_urls_consistent,
        test_discovery_endpoint_reachable,
        test_discovery_returns_https_public_urls,
    ]
    
    results = []
    for test_fn in tests:
        print()
        try:
            results.append(test_fn())
        except Exception as e:
            print(f"ERROR: {test_fn.__name__} raised exception: {e}")
            results.append(False)
    
    print()
    print("=" * 70)
    passed = sum(results)
    total = len(results)
    print(f"Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("All tests PASSED.")
        sys.exit(0)
    else:
        print(f"{total - passed} test(s) FAILED.")
        sys.exit(1)


if __name__ == "__main__":
    main()