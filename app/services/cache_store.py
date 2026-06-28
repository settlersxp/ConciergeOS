#!/usr/bin/env python3
"""
Shared cache store base class and utilities.

Provides a unified base class for all cache implementations to reduce code
duplication between CacheStore (LLM responses), HttpCacheStore (HTTP responses),
and ToolCallCacheStore (tool call results).

Also provides centralized cache configuration.

Usage:
    from app.services.cache_store import CacheConfig, BaseCacheStore
    
    # Use configured TTLs
    cache = BaseCacheStore(ttl=CacheConfig.RESPONSE_CACHE_TTL)
"""

import json
import logging
import os
import threading
import time
from abc import ABC, abstractmethod
from collections import OrderedDict
from typing import Any, Generic, TypeVar

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Cache Configuration - Centralized TTL and size settings
# ---------------------------------------------------------------------------


class CacheConfig:
    """Centralized cache configuration constants."""

    # TTL values (in seconds)
    RESPONSE_CACHE_TTL: int = int(os.environ.get("RESPONSE_CACHE_TTL", "3600"))        # 1 hour
    TOOL_CACHE_TTL: int = int(os.environ.get("TOOL_CACHE_TTL", "3600"))                # 1 hour
    HTTP_CACHE_TTL: int = int(os.environ.get("HTTP_CACHE_TTL", "3600"))                # 1 hour
    NAME_CACHE_TTL: int = int(os.environ.get("NAME_CACHE_TTL", "300"))                 # 5 minutes

    # Max cache sizes (for LRU eviction)
    RESPONSE_CACHE_MAX_SIZE: int = int(os.environ.get("RESPONSE_CACHE_MAX_SIZE", "10000"))
    TOOL_CACHE_MAX_SIZE: int = int(os.environ.get("TOOL_CACHE_MAX_SIZE", "5000"))
    HTTP_CACHE_MAX_SIZE: int = int(os.environ.get("HTTP_CACHE_MAX_SIZE", "5000"))
    NAME_CACHE_MAX_SIZE: int = int(os.environ.get("NAME_CACHE_MAX_SIZE", "2000"))

    # Logging configuration
    CACHE_LOG_SAMPLE_RATE: float = float(os.environ.get("CACHE_LOG_SAMPLE_RATE", "0.1"))  # 10%
    CACHE_LOG_MIN_SIZE: int = int(os.environ.get("CACHE_LOG_MIN_SIZE", "1024"))           # 1KB
    CACHE_LOG_MAX_FILE_SIZE: int = int(os.environ.get("CACHE_LOG_MAX_FILE_SIZE", "52428800"))  # 50MB
    CACHE_LOG_ROTATE_COUNT: int = int(os.environ.get("CACHE_LOG_ROTATE_COUNT", "3"))

    # Failure cache TTL (for caching DB query failures)
    FAILURE_CACHE_TTL: int = int(os.environ.get("FAILURE_CACHE_TTL", "60"))             # 1 minute

    @classmethod
    def reload(cls) -> None:
        """Reload configuration from environment variables."""
        cls.RESPONSE_CACHE_TTL = int(os.environ.get("RESPONSE_CACHE_TTL", "3600"))
        cls.TOOL_CACHE_TTL = int(os.environ.get("TOOL_CACHE_TTL", "3600"))
        cls.HTTP_CACHE_TTL = int(os.environ.get("HTTP_CACHE_TTL", "3600"))
        cls.NAME_CACHE_TTL = int(os.environ.get("NAME_CACHE_TTL", "300"))
        cls.RESPONSE_CACHE_MAX_SIZE = int(os.environ.get("RESPONSE_CACHE_MAX_SIZE", "10000"))
        cls.TOOL_CACHE_MAX_SIZE = int(os.environ.get("TOOL_CACHE_MAX_SIZE", "5000"))
        cls.HTTP_CACHE_MAX_SIZE = int(os.environ.get("HTTP_CACHE_MAX_SIZE", "5000"))
        cls.NAME_CACHE_MAX_SIZE = int(os.environ.get("NAME_CACHE_MAX_SIZE", "2000"))
        cls.CACHE_LOG_SAMPLE_RATE = float(os.environ.get("CACHE_LOG_SAMPLE_RATE", "0.1"))
        cls.CACHE_LOG_MIN_SIZE = int(os.environ.get("CACHE_LOG_MIN_SIZE", "1024"))
        cls.CACHE_LOG_MAX_FILE_SIZE = int(os.environ.get("CACHE_LOG_MAX_FILE_SIZE", "52428800"))
        cls.CACHE_LOG_ROTATE_COUNT = int(os.environ.get("CACHE_LOG_ROTATE_COUNT", "3"))
        cls.FAILURE_CACHE_TTL = int(os.environ.get("FAILURE_CACHE_TTL", "60"))


# ---------------------------------------------------------------------------
# Generic type variable for cache entry values
# ---------------------------------------------------------------------------

T = TypeVar("T")


# ---------------------------------------------------------------------------
# Base Cache Store
# ---------------------------------------------------------------------------


class BaseCacheStore(Generic[T], ABC):
    """
    Abstract base class for all cache stores.

    Provides shared functionality:
    - TTL-based expiration
    - Optional LRU eviction when max_size is exceeded
    - Thread-safe access
    - Statistics tracking

    Subclasses must define:
    - _value_type: The type of values stored
    - get_value()/set_value() methods for type-specific operations
    """

    def __init__(self, ttl: int | None = None, max_size: int | None = None):
        self._store: OrderedDict[str, T] = OrderedDict()
        self._ttl = ttl or 3600
        self._max_size = max_size
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0

    @property
    def ttl(self) -> int:
        return self._ttl

    @ttl.setter
    def ttl(self, value: int) -> None:
        self._ttl = value

    @property
    def max_size(self) -> int | None:
        return self._max_size

    @max_size.setter
    def max_size(self, value: int | None) -> None:
        self._max_size = value

    def get(self, key: str) -> T | None:
        """Get a cached value by key. Returns None if not found or expired."""
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                self._misses += 1
                return None

            if self._is_expired(entry):
                del self._store[key]
                self._misses += 1
                return None

            # Move to end (most recently used) for LRU
            self._store.move_to_end(key)
            self._hits += 1
            return entry

    def set(self, key: str, value: T, ttl: int | None = None) -> None:
        """Cache a value with the given key."""
        with self._lock:
            effective_ttl = ttl if ttl is not None else self._ttl

            if key in self._store:
                # Update existing key, move to end
                self._store[key] = value
                self._store.move_to_end(key)
            else:
                # Check if we need to evict for LRU
                if self._max_size is not None and len(self._store) >= self._max_size:
                    self._evict_lru()

                self._store[key] = value

    def delete(self, key: str) -> bool:
        """Remove a cached entry by key. Returns True if found and removed."""
        with self._lock:
            if key in self._store:
                del self._store[key]
                return True
            return False

    def clear(self) -> int:
        """Clear all cached entries. Returns the count of entries removed."""
        with self._lock:
            count = len(self._store)
            self._store.clear()
            self._hits = 0
            self._misses = 0
            return count

    def cleanup_expired(self) -> int:
        """Remove all expired entries. Returns the count removed."""
        with self._lock:
            expired_keys = [k for k, v in self._store.items() if self._is_expired(v)]
            for key in expired_keys:
                del self._store[key]
            return len(expired_keys)

    def _evict_lru(self) -> None:
        """Evict the least recently used entry. Must be called with lock held."""
        if self._store:
            evicted_key, _ = self._store.popitem(last=False)
            logger.debug(f"[CACHE-EVICT] LRU evicted key={evicted_key}")

    @abstractmethod
    def _is_expired(self, entry: T) -> bool:
        """Check if a cached entry has expired. Subclasses must implement."""
        ...

    @property
    def stats(self) -> dict[str, Any]:
        """Return cache statistics."""
        total = self._hits + self._misses
        return {
            "hits": self._hits,
            "misses": self._misses,
            "size": len(self._store),
            "total_requests": total,
            "hit_rate": round(self._hits / total * 100, 1) if total > 0 else 0.0,
        }

    def __len__(self) -> int:
        with self._lock:
            return len(self._store)


# ---------------------------------------------------------------------------
# Metrics Export
# ---------------------------------------------------------------------------


def export_cache_metrics(
    response_cache_stats: dict | None = None,
    tool_cache_stats: dict | None = None,
    http_cache_stats: dict | None = None,
    name_cache_stats: dict | None = None,
    failure_cache_stats: dict | None = None,
) -> str:
    """
    Export cache statistics in Prometheus exposition format.

    Example output:
        # HELP cache_entries Number of entries in cache
        # TYPE cache_entries gauge
        cache_entries{type="response"} 42
        # HELP cache_hits_total Total cache hits
        # TYPE cache_hits_total counter
        cache_hits_total{type="response"} 1234

    Args:
        response_cache_stats: Stats from CacheStore
        tool_cache_stats: Stats from ToolCallCacheStore
        http_cache_stats: Stats from HttpCacheStore
        name_cache_stats: Stats from name-to-ID resolution cache
        failure_cache_stats: Stats from failure cache

    Returns:
        Prometheus-format string
    """
    lines = []

    # Header
    lines.append("# Cache Statistics - Exported at " + time.strftime("%Y-%m-%dT%H:%M:%S%z"))
    lines.append("")

    def _export(name: str, stats: dict | None) -> None:
        if stats is None:
            return

        # Entries (gauge)
        size = stats.get("size", 0)
        lines.append(f"# HELP cache_entries{{type=\"{name}\"}} Number of entries in {name} cache")
        lines.append(f"# TYPE cache_entries{{type=\"{name}\"}} gauge")
        lines.append(f'cache_entries{{type="{name}"}} {size}')
        lines.append("")

        # Hits (counter)
        hits = stats.get("hits", 0)
        lines.append(f"# HELP cache_hits{{type=\"{name}\"}} Total cache hits for {name}")
        lines.append(f"# TYPE cache_hits{{type=\"{name}\"}} counter")
        lines.append(f'cache_hits{{type="{name}"}} {hits}')
        lines.append("")

        # Misses (counter)
        misses = stats.get("misses", 0)
        lines.append(f"# HELP cache_misses{{type=\"{name}\"}} Total cache misses for {name}")
        lines.append(f"# TYPE cache_misses{{type=\"{name}\"}} counter")
        lines.append(f'cache_misses{{type="{name}"}} {misses}')
        lines.append("")

        # Hit rate (gauge as percentage)
        hit_rate = stats.get("hit_rate", 0.0)
        lines.append(f"# HELP cache_hit_rate{{type=\"{name}\"}} Cache hit rate percentage for {name}")
        lines.append(f"# TYPE cache_hit_rate{{type=\"{name}\"}} gauge")
        lines.append(f'cache_hit_rate{{type="{name}"}} {hit_rate}')
        lines.append("")

    # Export all provided stats
    _export("response", response_cache_stats)
    _export("tool", tool_cache_stats)
    _export("http", http_cache_stats)
    _export("name_resolution", name_cache_stats)
    _export("failure", failure_cache_stats)

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Failure Cache - for caching DB query failures
# ---------------------------------------------------------------------------


class FailureCacheEntry:
    """A single cache entry for failed operations with short TTL."""

    def __init__(self, timestamp: float, ttl: int):
        self.timestamp = timestamp
        self.ttl = ttl

    @property
    def is_expired(self) -> bool:
        return (time.time() - self.timestamp) >= self.ttl


class FailureCacheStore:
    """
    Lightweight cache for tracking recently-failed operations.

    Prevents repeated DB queries for operations that recently failed.
    """

    def __init__(self, ttl: int | None = None, max_size: int | None = None):
        self._store: OrderedDict[str, FailureCacheEntry] = OrderedDict()
        self._ttl = ttl or CacheConfig.FAILURE_CACHE_TTL
        self._max_size = max_size
        self._lock = threading.Lock()

    def is_failed(self, key: str) -> bool:
        """Check if this key recently failed. Returns True if still in failure window."""
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return False
            if entry.is_expired:
                del self._store[key]
                return False
            return True

    def record_failure(self, key: str) -> None:
        """Record that this key recently failed."""
        with self._lock:
            if key in self._store:
                self._store[key] = FailureCacheEntry(time.time(), self._ttl)
                self._store.move_to_end(key)
            else:
                if self._max_size is not None and len(self._store) >= self._max_size:
                    self._evict_lru()
                self._store[key] = FailureCacheEntry(time.time(), self._ttl)

    def clear(self) -> int:
        with self._lock:
            count = len(self._store)
            self._store.clear()
            return count

    def cleanup_expired(self) -> int:
        with self._lock:
            expired_keys = [k for k, v in self._store.items() if v.is_expired]
            for key in expired_keys:
                del self._store[key]
            return len(expired_keys)

    def _evict_lru(self) -> None:
        if self._store:
            self._store.popitem(last=False)

    @property
    def stats(self) -> dict[str, Any]:
        with self._lock:
            return {
                "size": len(self._store),
                "ttl": self._ttl,
            }

    def __len__(self) -> int:
        with self._lock:
            return len(self._store)