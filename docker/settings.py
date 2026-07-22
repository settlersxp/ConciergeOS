#!/usr/bin/env python3
"""Shared settings for ConciergeOS Docker scripts.

Provides a single source of truth for environment variables used across
role_sync.py, keycloak_setup.py, and test fixtures.

Usage:
    from settings import settings
    print(settings.KEYCLOAK_URL)
"""

import os


class Settings:
    """Environment-based configuration with sensible defaults.

    All attributes are read from environment variables with fallback defaults.
    The defaults are designed to work in both Docker and local development:
    - Docker: services are reachable by container name (keycloak, caddy, valkey)
    - Local: services are reachable via localhost
    """

    # -- Keycloak --
    @property
    def KEYCLOAK_URL(self) -> str:
        return os.environ.get("KEYCLOAK_URL", "http://keycloak:8080/auth")

    @property
    def KEYCLOAK_REALM(self) -> str:
        return os.environ.get("KEYCLOAK_REALM", "production")

    @property
    def KEYCLOAK_ADMIN_USER(self) -> str:
        return os.environ.get("KEYCLOAK_ADMIN_USER", "admin")

    @property
    def KEYCLOAK_ADMIN_PASSWORD(self) -> str:
        return os.environ.get("KEYCLOAK_ADMIN_PASSWORD", "admin")

    # -- Caddy --
    @property
    def CADDY_ADMIN_URL(self) -> str:
        return os.environ.get("CADDY_ADMIN_URL", "http://caddy:2019")

    # -- Valkey --
    @property
    def VALKEY_URL(self) -> str:
        return os.environ.get("VALKEY_URL", "redis://valkey:6379/0")

    # -- Session --
    @property
    def SESSION_COOKIE_NAME(self) -> str:
        return os.environ.get("SESSION_COOKIE_NAME", "_oauth2_proxy")

    # -- Role Sync --
    @property
    def SYNC_INTERVAL(self) -> int:
        return int(os.environ.get("SYNC_INTERVAL", "10"))

    @property
    def MAPPING_FILE(self) -> str:
        return os.environ.get("MAPPING_FILE", "/app/rbac_routes.yaml")

    # -- App Domain (used by OIDC redirect URIs, Keycloak client config) --
    @property
    def APP_DOMAIN(self) -> str:
        return os.environ.get("APP_DOMAIN", "https://out-customer.com")

    # -- OIDC --
    @property
    def OIDC_REALM(self) -> str:
        return os.environ.get("OIDC_REALM", "production")

    @property
    def OIDC_CLIENT_ID(self) -> str:
        return os.environ.get("OIDC_CLIENT_ID", "concierge")

    # -- LLM / vLLM --
    @property
    def MODELS_ENDPOINT(self) -> str:
        return os.environ.get("MODELS_ENDPOINT", "http://localhost:8000/v1")

    @property
    def MODEL_NAME(self) -> str:
        return os.environ.get("MODEL_NAME", "")

    @property
    def VLLM_VERSION(self) -> str:
        return os.environ.get("VLLM_VERSION", "")

    @property
    def THINKING_ENABLED(self) -> bool:
        return os.environ.get("THINKING_ENABLED", "false").lower() in ("true", "1", "yes")

    @property
    def EXPECTED_FORMAT(self) -> str:
        return os.environ.get("EXPECTED_FORMAT", "auto")

    # -- Database --
    @property
    def DATABASE_URL(self) -> str:
        return os.environ.get("DATABASE_URL", "sqlite:////app/database.db")


# Singleton instance
settings = Settings()