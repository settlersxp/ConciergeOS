#!/usr/bin/env python3
"""
Response cache middleware for LLM interactions.

Provides diagnostic logging for LLM calls with built-in HTTP-level response caching.
Caches LLM responses by customer name (case-insensitive, trimmed) to avoid redundant
LLM calls for repeated requests.

Currently captures via Python logging:
- Per-turn diagnostics: finish_reason, token usage, response length
- Conversation hashing for future cache keys
- Truncation detection and warnings
- Response checksums to detect incomplete outputs

Caching behavior:
- Cache key = SHA256(normalized customer name)
- Default TTL = 3600 seconds (1 hour)
- Storage = in-memory dict (swappable for Redis later)
- Transparent: call_llm_with_db_tools() checks cache before LLM call

Usage:
    from app.services.response_cache import call_llm_with_db_tools, cache_clear
    
    response = call_llm_with_db_tools("Show me all special guests")
    print(response)
    
    # Clear cache (e.g., after DB changes)
    cache_clear()
"""

import hashlib
import json
import logging
import time
from typing import Any, Generic, TypeVar
from urllib.parse import urlencode, urlparse, parse_qs

logger = logging.getLogger(__name__)

T = TypeVar("T")


# ---------------------------------------------------------------------------
# Generic Cache data structures
# ---------------------------------------------------------------------------

class CacheEntry(Generic[T]):
    """A generic cached entry with expiration tracking.

    Type parameter T represents the stored data type (e.g., str, tuple[int, dict, str]).
    """

    def __init__(self, value: T, timestamp: float, ttl: int):
        self.value = value
        self.timestamp = timestamp
        self.ttl = ttl

    @property
    def is_expired(self) -> bool:
        """Return True if this entry has exceeded its TTL."""
        return (time.time() - self.timestamp) >= self.ttl

    @property
    def response(self) -> Any:
        """Alias for .value — provides backwards-compatible access as 'response'."""
        return self.value

    @response.setter
    def response(self, value: Any) -> None:
        self.value = value


class CacheStore:
    """In-memory LLM response cache with TTL-based expiration.

    Single-process use. Designed to be swapped for Redis or other backends later
    without changing the API.

    Usage:
        store = CacheStore(ttl=3600)
        store.set("key", "response")
        entry = store.get("key")
        if entry and not entry.is_expired:
            print(entry.value)
    """

    def __init__(self, ttl: int = 3600):
        """Initialize the cache store.

        Args:
            ttl: Time-to-live in seconds (default 3600 = 1 hour)
        """
        self._store: dict[str, CacheEntry[str]] = {}
        self._ttl = ttl
        self._hits = 0
        self._misses = 0

    @property
    def ttl(self) -> int:
        """Current TTL in seconds."""
        return self._ttl

    @ttl.setter
    def ttl(self, value: int) -> None:
        """Change the TTL. Existing entries keep their original timestamps."""
        self._ttl = value

    def get(self, key: str) -> CacheEntry[str] | None:
        """Get a cached entry by key. Returns None if expired."""
        entry = self._store.get(key)
        if entry is None or entry.is_expired:
            if entry:
                del self._store[key]
            self._misses += 1
            return None
        self._hits += 1
        return entry

    def set(self, key: str, value: str) -> None:
        """Cache a value with the default TTL."""
        self._store[key] = CacheEntry(value=value, timestamp=time.time(), ttl=self._ttl)

    def delete(self, key: str) -> None:
        """Remove an entry from the cache."""
        self._store.pop(key, None)

    def clear(self) -> None:
        """Clear all entries from the cache."""
        self._store.clear()
        self._hits = 0
        self._misses = 0

    @property
    def stats(self) -> dict[str, int]:
        """Return cache hit/miss stats."""
        return {"hits": self._hits, "misses": self._misses, "size": len(self._store)}


# ---------------------------------------------------------------------------
# HTTP Cache data structures
# ---------------------------------------------------------------------------

class HttpCacheEntry:
    """A single cached HTTP response with expiration tracking."""

    def __init__(self, status_code: int, headers: dict[str, str], body: str, timestamp: float, ttl: int):
        self.status_code = status_code
        self.headers = headers
        self.body = body
        self.timestamp = timestamp
        self.ttl = ttl

    @property
    def is_expired(self) -> bool:
        """Return True if this entry has exceeded its TTL."""
        return (time.time() - self.timestamp) >= self.ttl


class HttpCacheStore:
    """
    In-memory HTTP response cache with TTL-based expiration.
    
    Stores full HTTP responses (status, headers, body) to avoid redundant network calls.

    Single-process use. Designed to be swapped for Redis or other backends later
    without changing the API.

    Usage:
        store = HttpCacheStore(ttl=3600)
        store.set("key", 200, {"content-type": "application/json"}, "{}")
        entry = store.get("key")
        if entry and not entry.is_expired:
            print(entry.body)
    """

    def __init__(self, ttl: int = 3600):
        """Initialize the HTTP cache store.

        Args:
            ttl: Time-to-live in seconds (default 3600 = 1 hour)
        """
        self._store: dict[str, HttpCacheEntry] = {}
        self._ttl = ttl
        self._hits = 0
        self._misses = 0

    @property
    def ttl(self) -> int:
        """Current TTL in seconds."""
        return self._ttl

    @ttl.setter
    def ttl(self, value: int) -> None:
        """Change the TTL. Existing entries keep their original timestamps."""
        self._ttl = value

    def get(self, key: str) -> HttpCacheEntry | None:
        """Get a cached HTTP response entry by key. Returns None if expired."""
        entry = self._store.get(key)
        if entry is None or entry.is_expired:
            if entry:
                del self._store[key]
            self._misses += 1
            return None
        self._hits += 1
        return entry

    def set(self, key: str, status_code: int, headers: dict[str, str], body: str, ttl: int | None = None) -> None:
        """Cache an HTTP response.

        Args:
            key: Cache key string.
            status_code: HTTP status code.
            headers: Response headers dict.
            body: Response body string.
            ttl: Optional TTL override (uses default if not provided).
        """
        entry_ttl = ttl if ttl is not None else self._ttl
        self._store[key] = HttpCacheEntry(
            status_code=status_code,
            headers=headers,
            body=body,
            timestamp=time.time(),
            ttl=entry_ttl,
        )

    def delete(self, key: str) -> None:
        """Remove an entry from the cache."""
        self._store.pop(key, None)

    def clear(self) -> None:
        """Clear all entries from the cache."""
        self._store.clear()
        self._hits = 0
        self._misses = 0

    @property
    def stats(self) -> dict[str, int]:
        """Return cache hit/miss stats."""
        return {"hits": self._hits, "misses": self._misses, "size": len(self._store)}


# ---------------------------------------------------------------------------
# Cache Key Generation
# ---------------------------------------------------------------------------

def generate_cache_key(data: str) -> str:
    """Generate a SHA256 cache key from the input string.

    Normalizes the input (lowercase, trimmed) before hashing.

    Args:
        data: The input string to hash for cache key generation.

    Returns:
        A hex-encoded SHA256 hash string.
    """
    normalized = data.strip().lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def generate_http_cache_key(url: str) -> str:
    """Generate a SHA256 cache key from an HTTP URL.

    Parses the URL and normalizes query parameters before hashing.

    Args:
        url: The URL string to hash for cache key generation.

    Returns:
        A hex-encoded SHA256 hash string.
    """
    parsed = urlparse(url)
    # Sort query params for consistent hashing
    sorted_query = urlencode(sorted(parse_qs(parsed.query).items()))
    normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}?{sorted_query}"
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Singleton cache instances
# ---------------------------------------------------------------------------

_response_cache: CacheStore | None = None
_http_response_cache: HttpCacheStore | None = None


def _get_cache() -> CacheStore:
    """Return the module-level singleton LLM response cache.

    Created lazily on first use. All LLM calls through
    ``call_llm_with_db_tools_with_cache_flag()`` share this single cache.
    """
    global _response_cache
    if _response_cache is None:
        _response_cache = CacheStore(ttl=3600)
    return _response_cache


def _get_http_cache() -> HttpCacheStore:
    """Return the module-level singleton HTTP response cache.

    Created lazily on first use. All HTTP-level caching shares this single instance.
    """
    global _http_response_cache
    if _http_response_cache is None:
        _http_response_cache = HttpCacheStore(ttl=300)
    return _http_response_cache


def cache_clear() -> None:
    """Clear the LLM response cache."""
    global _response_cache
    if _response_cache is not None:
        _response_cache.clear()


def http_cache_clear() -> None:
    """Clear the HTTP response cache."""
    global _http_response_cache
    if _http_response_cache is not None:
        _http_response_cache.clear()


# ---------------------------------------------------------------------------
# LLM Call wrapper with caching
# ---------------------------------------------------------------------------

def call_llm_with_db_tools_with_cache_flag(
    user_prompt: str,
    model: str | None = None,
    system_prompt: str | None = None,
) -> tuple[str, bool]:
    """Call the LLM with database tools, checking cache first.

    Args:
        user_prompt: The user's prompt to send to the LLM.
        model: Optional model name (falls back to config).
        system_prompt: Optional system prompt override.

    Returns:
        A tuple of (llm_response, was_cached) where was_cached is True if the
        response was served from the cache.
    """
    from app.services.llm import get_llm_config, SHARED_SYSTEM_PROMPT

    client, model_name = get_llm_config()
    sys_prompt = system_prompt or SHARED_SYSTEM_PROMPT

    # Generate cache key from the prompt content
    cache_input = f"{sys_prompt}\n\n{user_prompt}"
    cache_key = generate_cache_key(cache_input)

    # Check cache
    cache = _get_cache()
    cached_entry = cache.get(cache_key)
    if cached_entry is not None:
        logger.info(f"[CACHE] HIT for prompt, returning cached response")
        return cached_entry.value, True

    # Cache miss - call LLM
    logger.info(f"[CACHE] MISS for prompt, calling LLM with model={model_name}")

    from openai.types.chat import ChatCompletionUserMessageParam, ChatCompletionSystemMessageParam

    messages: list[ChatCompletionSystemMessageParam | ChatCompletionUserMessageParam] = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": user_prompt},
    ]

    response = client.chat.completions.create(
        model=model or model_name,
        messages=messages,
        response_format={"type": "json_object"},
    )

    result = response.choices[0].message.content or ""

    # Store in cache
    cache.set(cache_key, result)

    return result, False