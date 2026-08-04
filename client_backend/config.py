"""Configuration for the client backend service.

Reads environment variables with sensible defaults that work both inside
Docker (container names) and locally (localhost).
"""

import os


class Settings:
    """Environment-based configuration for the client backend."""

    # -- Keycloak --
    @property
    def KEYCLOAK_URL(self) -> str:
        """Keycloak base URL (e.g. http://keycloak:8080/auth)."""
        return os.environ.get("KEYCLOAK_URL", "http://keycloak:8080/auth")

    @property
    def KEYCLOAK_REALM(self) -> str:
        """Keycloak realm name."""
        return os.environ.get("KEYCLOAK_REALM", "production")

    @property
    def KEYCLOAK_ADMIN_USER(self) -> str:
        """Keycloak admin username for Admin API access."""
        return os.environ.get("KEYCLOAK_ADMIN_USER", "admin")

    @property
    def KEYCLOAK_ADMIN_PASSWORD(self) -> str:
        """Keycloak admin password for Admin API access."""
        return os.environ.get("KEYCLOAK_ADMIN_PASSWORD", "admin")

    # -- Client Credentials --
    @property
    def CLIENT_API_CLIENT_ID(self) -> str:
        """The OAuth2 client_id registered in Keycloak for this service."""
        return os.environ.get("CLIENT_API_CLIENT_ID", "client-api")

    @property
    def CLIENT_API_CLIENT_SECRET(self) -> str:
        """The OAuth2 client_secret for this service. Must be set."""
        secret = os.environ.get("CLIENT_API_CLIENT_SECRET", "")
        if not secret:
            raise ValueError(
                "CLIENT_API_CLIENT_SECRET is not set. "
                "Run the Keycloak setup to generate it, then set the env var."
            )
        return secret

    # -- Backend (target service) --
    @property
    def BACKEND_URL(self) -> str:
        """URL of the main backend service to call."""
        return os.environ.get("BACKEND_URL", "http://backend:8000")


# Singleton instance
settings = Settings()