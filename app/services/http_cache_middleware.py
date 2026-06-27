#!/usr/bin/env python3
"""
HTTP response cache middleware for FastAPI (ASGI-based).

Caches GET responses by normalized URI + query parameters.
Adds X-Cache header (HIT/MISS) to responses.

This uses Starlette's ASGI middleware approach to properly capture response bodies.

Usage:
    from app.services.http_cache_middleware import HttpCacheMiddleware
    app.add_middleware(HttpCacheMiddleware)
"""

import logging
import time

from starlette.requests import Request
from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger(__name__)


class _StreamingResponseCapture:
    """Captures response body from a streaming response."""

    def __init__(self):
        self.body_parts: list[bytes] = []
        self.status_code: int = 200
        self.headers_list: list[tuple[bytes, bytes]] = []

    def add_part(self, part: bytes) -> None:
        self.body_parts.append(part)

    @property
    def body(self) -> bytes:
        return b"".join(self.body_parts)


class HttpCacheMiddleware:
    """
    ASGI middleware that caches GET responses by URI + query parameters.

    - Only caches GET requests (safe, idempotent)
    - Bypasses cache if Cache-Control: no-cache header is present
    - Adds X-Cache header: "HIT" or "MISS"
    - Default TTL = 3600 seconds (1 hour)
    """

    def __init__(self, app: ASGIApp, ttl: int = 3600) -> None:
        self.app = app
        self._ttl = ttl
        from app.services.response_cache import _get_http_cache
        self.cache = _get_http_cache()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope)

        # Only cache GET requests
        if request.method != "GET":
            await self.app(scope, receive, send)
            return

        # Build full URL for cache key generation
        path = request.url.path
        query = request.url.query
        full_url = f"{request.url.scheme}://{request.url.netloc}{path}"
        if query:
            full_url += f"?{query}"

        # Generate cache key
        from app.services.response_cache import generate_http_cache_key
        cache_key = generate_http_cache_key(full_url)

        # Check for Cache-Control: no-cache bypass
        cache_control = request.headers.get("cache-control", "")
        bypass_cache = "no-cache" in cache_control

        # Check cache
        if not bypass_cache:
            cached_entry = self.cache.get(cache_key)
            if cached_entry is not None:
                logger.info(
                    f"[HTTP-CACHE] HIT for {path} | "
                    f"key={cache_key[:12]}... | "
                    f"status={cached_entry.status_code}"
                )
                remaining = round(
                    cached_entry.ttl - (time.time() - cached_entry.timestamp), 1
                )
                headers_to_send: list[tuple[bytes, bytes]] = [
                    (b"content-type", cached_entry.headers.get("content-type", "application/json").encode()),
                    (b"x-cache", b"HIT"),
                    (b"x-cache-ttl-remaining", str(remaining).encode()),
                ]
                for k, v in cached_entry.headers.items():
                    lower_k = k.lower()
                    if lower_k not in ("content-type", "x-cache", "x-cache-ttl-remaining"):
                        headers_to_send.append((k.encode(), v.encode()))

                await self._send_response(send, cached_entry.status_code, headers_to_send, cached_entry.body.encode("utf-8"))
                return

        # Cache miss: we need to capture the response
        capture = _StreamingResponseCapture()

        async def _send(message: Message) -> None:
            if message["type"] == "http.response.start":
                capture.status_code = message["status"]
                capture.headers_list = message.get("headers", [])
            elif message["type"] == "http.response.body":
                if body := message.get("body"):
                    capture.add_part(body)
                # For final chunk, store and return cached response
                if not message.get("more_body", False):
                    body_str = capture.body.decode("utf-8", errors="replace")

                    # Only cache successful responses
                    if capture.status_code == 200:
                        # Parse headers
                        resp_headers: dict[str, str] = {}
                        for k, v in capture.headers_list:
                            resp_headers[k.decode()] = v.decode()

                        self.cache.set(
                            key=cache_key,
                            status_code=capture.status_code,
                            headers=resp_headers,
                            body=body_str,
                            ttl=self._ttl,
                        )
                        logger.info(
                            f"[HTTP-CACHE] STORED for {path} | "
                            f"key={cache_key[:12]}... | "
                            f"size={len(body_str)}"
                        )

                    # Send original response with X-Cache: MISS
                    headers_to_send: list[tuple[bytes, bytes]] = [
                        *capture.headers_list,
                        (b"x-cache", b"MISS"),
                    ]
                    await self._send_response(
                        send,
                        capture.status_code,
                        headers_to_send,
                        capture.body,
                    )

        await self.app(scope, receive, _send)

    @staticmethod
    async def _send_response(
        send: Send,
        status_code: int,
        headers: list[tuple[bytes, bytes]],
        body: bytes,
    ) -> None:
        await send(
            {
                "type": "http.response.start",
                "status": status_code,
                "headers": headers,
            }
        )
        await send(
            {
                "type": "http.response.body",
                "body": body,
            }
        )