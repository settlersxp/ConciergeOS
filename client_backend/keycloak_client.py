"""Keycloak OAuth2 Client — Client Credentials Grant Flow.

This module handles authentication with Keycloak using the **Client Credentials**
grant type, which is designed for machine-to-machine communication where no
user interaction is involved.

Key concepts:
 - The service presents its ``client_id`` + ``client_secret`` to Keycloak.
 - Keycloak issues an ``access_token`` (JWT) valid for a limited time.
 - The token is attached to outgoing API calls as a Bearer token.
 - When the token is close to expiring, it is automatically refreshed.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

import httpx

from .config import settings

logger = logging.getLogger(__name__)


@dataclass
class TokenData:
    """Holds the current OAuth2 token and metadata."""

    access_token: str
    token_type: str = "Bearer"
    expires_in: int = 0
    scope: str = ""

    # Computed at acquisition time
    _acquired_at: float = field(default_factory=time.time)

    @property
    def expires_at(self) -> float:
        """Unix timestamp when the token expires."""
        return self._acquired_at + self.expires_in

    @property
    def is_expired(self) -> bool:
        """Check if the token has expired (with a 30s safety margin)."""
        return time.time() >= (self.expires_at - 30)


class KeycloakClient:
    """Manages OAuth2 Client Credentials authentication with Keycloak.

    Usage:
        kc = KeycloakClient()
        token = kc.get_access_token()  # auto-refreshes if expired
        response = await kc.call_backend("GET", "/api/models")
    """

    def __init__(self) -> None:
        self._token: TokenData | None = None
        self._http_client: httpx.AsyncClient | None = None

    # ------------------------------------------------------------------
    # Token management
    # ------------------------------------------------------------------

    def _token_url(self) -> str:
        """Build the OAuth2 token endpoint URL.

        Example: http://keycloak:8080/auth/realms/production/protocol/openid-connect/token
        """
        return (
            f"{settings.KEYCLOAK_URL}/realms/{settings.KEYCLOAK_REALM}"
            f"/protocol/openid-connect/token"
        )

    async def _fetch_token(self) -> TokenData:
        """Request a new access token via the Client Credentials Grant.

        This is the core OAuth2 flow for service-to-service communication:
        1. POST to the token endpoint with client_id, client_secret, and
           grant_type=client_credentials.
        2. Keycloak validates the credentials and returns a JWT.
        3. The JWT can now be used to call protected APIs.
        """
        token_url = self._token_url()

        async with httpx.AsyncClient() as client:
            response = await client.post(
                token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": settings.CLIENT_API_CLIENT_ID,
                    "client_secret": settings.CLIENT_API_CLIENT_SECRET,
                },
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()

        token = TokenData(
            access_token=data["access_token"],
            token_type=data.get("token_type", "Bearer"),
            expires_in=data.get("expires_in", 300),
            scope=data.get("scope", ""),
        )
        logger.info(
            "Acquired token (expires in %ds, scope: %s)",
            token.expires_in,
            token.scope,
        )
        self._token = token
        return token

    async def get_access_token(self) -> TokenData:
        """Return a valid access token, refreshing if necessary."""
        if self._token is None or self._token.is_expired:
            return await self._fetch_token()
        return self._token

    async def refresh_token(self) -> TokenData:
        """Force-fetch a new token (ignores the cached one)."""
        logger.info("Forced token refresh")
        return await self._fetch_token()

    # ------------------------------------------------------------------
    # Token introspection (decode JWT payload without network call)
    # ------------------------------------------------------------------

    @staticmethod
    def _decode_jwt_payload(token: str) -> dict:
        """Minimally decode the JWT payload (middle segment) without crypto.

        This is for *inspection/debugging only* — it does NOT validate
        the signature.  In production you would validate the token
        server-side using Keycloak's public keys.
        """
        import base64
        import json

        try:
            payload_b64 = token.split(".")[1]
            # Add padding if missing
            payload_b64 += "=" * (-len(payload_b64) % 4)
            payload_json = base64.urlsafe_b64decode(payload_b64)
            return json.loads(payload_json)
        except Exception as exc:
            return {"error": str(exc)}

    def get_token_info(self) -> dict:
        """Return human-readable information about the current token."""
        if self._token is None:
            return {"status": "no token cached"}

        payload = self._decode_jwt_payload(self._token.access_token)
        return {
            "status": "expired" if self._token.is_expired else "valid",
            "token_type": self._token.token_type,
            "expires_in": self._token.expires_in,
            "expired": self._token.is_expired,
            "scope": self._token.scope,
            "payload": payload,
        }

    # ------------------------------------------------------------------
    # Helper: call the main backend with the bearer token
    # ------------------------------------------------------------------

    async def call_backend(
        self,
        method: str,
        path: str,
        *,
        json_body: dict | None = None,
    ) -> httpx.Response:
        """Make an authenticated request to the main backend service.

        The access token is attached as ``Authorization: Bearer <token>``
        so the upstream service can verify the caller's identity.
        """
        token = await self.get_access_token()

        async with httpx.AsyncClient() as client:
            response = await client.request(
                method=method,
                url=f"{settings.BACKEND_URL}{path}",
                headers={
                    "Authorization": f"{token.token_type} {token.access_token}",
                    "Content-Type": "application/json",
                },
                json=json_body,
                timeout=15,
            )
            response.raise_for_status()
            return response

# Singleton — shared across the FastAPI app
keycloak_client = KeycloakClient()
