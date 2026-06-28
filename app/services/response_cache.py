#!/usr/bin/env python3
"""
Response cache middleware for LLM interactions.

Caches LLM responses by customer name (case-insensitive, trimmed) to avoid redundant
LLM calls for repeated requests.

Caching layers:
1. Tool Cache — caches database query results by resolved IDs
2. Structured Response Cache — caches final LLM responses by conversation hash

Logging:
- Full cache value logging to /tmp/cof_cache_full_value.log (no truncation)

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
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urlparse, parse_qs

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Full cache value logging — no truncation
# ---------------------------------------------------------------------------
_CACHE_FULL_VALUE_FILE = Path("/tmp/cof_cache_full_value.log")


def _log_cache_entry_full(
    operation: str,
    key: str,
    value: str,
) -> None:
    """
    Write a cache entry to the full-value log file with NO truncation.

    Each entry is a single JSON line containing:
      - op: SET / HIT / DELETE / CLEAR
      - key: the full cache key
      - value: the FULL cached value (no truncation)
      - timestamp: epoch float
      - value_len: len(value) for quick scanning
    """
    try:
        entry = {
            "op": operation,
            "key": key,
            "value": value,
            "value_len": len(value),
            "timestamp": time.time(),
        }
        line = json.dumps(entry, ensure_ascii=False) + "\n"
        with open(_CACHE_FULL_VALUE_FILE, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass  # Best-effort — don't break the application if logging fails


# ---------------------------------------------------------------------------
# Tool-call loop detection configuration
# ---------------------------------------------------------------------------
_MAX_IDENTICAL_TOOL_CALLS = 3


# ---------------------------------------------------------------------------
# Tool call cache data structures
# ---------------------------------------------------------------------------


class ToolCallCacheEntry:
    """A single cached tool call result with expiration tracking."""

    def __init__(self, result: str, timestamp: float, ttl: int):
        self.result = result
        self.timestamp = timestamp
        self.ttl = ttl

    @property
    def is_expired(self) -> bool:
        """Return True if this entry has exceeded its TTL."""
        return (time.time() - self.timestamp) >= self.ttl


class ToolCallCacheStore:
    """
    In-memory cache for tool call results with TTL-based expiration.

    Caches results by structured cache key (model_identifier:resource_identifier:prompt_id:prompt_version:model_name).
    """

    def __init__(self, ttl: int = 3600):
        self._store: dict[str, ToolCallCacheEntry] = {}
        self._ttl = ttl
        self._hits = 0
        self._misses = 0

    @property
    def ttl(self) -> int:
        return self._ttl

    @ttl.setter
    def ttl(self, value: int) -> None:
        self._ttl = value

    def get(self, key: str) -> ToolCallCacheEntry | None:
        entry = self._store.get(key)
        if entry is None:
            self._misses += 1
            return None
        if entry.is_expired:
            del self._store[key]
            self._misses += 1
            return None
        self._hits += 1
        return entry

    def set(self, key: str, result: str, ttl: int | None = None) -> None:
        effective_ttl = ttl if ttl is not None else self._ttl
        self._store[key] = ToolCallCacheEntry(
            result=result,
            timestamp=time.time(),
            ttl=effective_ttl,
        )
        _log_cache_entry_full("SET", key, result)

    def delete(self, key: str) -> bool:
        if key in self._store:
            del self._store[key]
            return True
        return False

    def clear(self) -> int:
        count = len(self._store)
        self._store.clear()
        self._hits = 0
        self._misses = 0
        return count

    def cleanup_expired(self) -> int:
        expired_keys = [k for k, v in self._store.items() if v.is_expired]
        for key in expired_keys:
            del self._store[key]
        return len(expired_keys)

    @property
    def stats(self) -> dict[str, Any]:
        total = self._hits + self._misses
        return {
            "tool_cache_hits": self._hits,
            "tool_cache_misses": self._misses,
            "size": len(self._store),
            "hit_rate": round(self._hits / total * 100, 1) if total > 0 else 0.0,
        }

    def __len__(self) -> int:
        return len(self._store)


# ---------------------------------------------------------------------------
# Cache data structures
# ---------------------------------------------------------------------------


class CacheEntry:
    """A single cached LLM response with expiration tracking."""

    def __init__(self, response: str, timestamp: float, ttl: int):
        self.response = response
        self.timestamp = timestamp
        self.ttl = ttl

    @property
    def is_expired(self) -> bool:
        """Return True if this entry has exceeded its TTL."""
        return (time.time() - self.timestamp) >= self.ttl


class CacheStore:
    """
    In-memory LLM response cache with TTL-based expiration.
    """

    def __init__(self, ttl: int = 3600):
        self._store: dict[str, CacheEntry] = {}
        self._ttl = ttl
        self._hits = 0
        self._misses = 0

    @property
    def ttl(self) -> int:
        return self._ttl

    @ttl.setter
    def ttl(self, value: int) -> None:
        self._ttl = value

    def get(self, key: str) -> CacheEntry | None:
        entry = self._store.get(key)
        if entry is None:
            self._misses += 1
            return None
        if entry.is_expired:
            del self._store[key]
            self._misses += 1
            return None
        self._hits += 1
        return entry

    def set(self, key: str, response: str, ttl: int | None = None) -> None:
        effective_ttl = ttl if ttl is not None else self._ttl
        self._store[key] = CacheEntry(
            response=response,
            timestamp=time.time(),
            ttl=effective_ttl,
        )
        _log_cache_entry_full("SET", key, response)

    def delete(self, key: str) -> bool:
        if key in self._store:
            del self._store[key]
            return True
        return False

    def clear(self) -> int:
        count = len(self._store)
        self._store.clear()
        self._hits = 0
        self._misses = 0
        return count

    def cleanup_expired(self) -> int:
        expired_keys = [k for k, v in self._store.items() if v.is_expired]
        for key in expired_keys:
            del self._store[key]
        return len(expired_keys)

    @property
    def stats(self) -> dict[str, Any]:
        total = self._hits + self._misses
        return {
            "hits": self._hits,
            "misses": self._misses,
            "size": len(self._store),
            "total_requests": total,
            "hit_rate": round(self._hits / total * 100, 1) if total > 0 else 0.0,
        }

    def __len__(self) -> int:
        return len(self._store)


# ---------------------------------------------------------------------------
# Cache key generation (kept for backward compatibility)
# ---------------------------------------------------------------------------


def generate_cache_key(text: str) -> str:
    """
    Generate a deterministic cache key from normalized text.

    Normalization: strip whitespace, lowercase.

    Args:
        text: Raw input text (e.g., customer name)

    Returns:
        SHA256 hex digest string
    """
    normalized = text.strip().lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Singleton cache stores
# ---------------------------------------------------------------------------

# Structured response cache: keyed by conversation hash
_response_cache = CacheStore(ttl=3600)


def _get_cache() -> CacheStore:
    """Get the singleton structured response CacheStore instance."""
    return _response_cache


def cache_get(key: str) -> CacheEntry | None:
    """Get a cached entry by key. Returns None if not found or expired."""
    return _get_cache().get(key)


def cache_set(key: str, response: str, ttl: int | None = None) -> None:
    """Cache a response with the given key."""
    _get_cache().set(key, response, ttl)


def cache_clear() -> int:
    """Clear all cached entries. Returns the count of entries removed."""
    return _get_cache().clear()


def cache_cleanup_expired() -> int:
    """Remove all expired entries. Returns the count removed."""
    return _get_cache().cleanup_expired()


def cache_stats() -> dict[str, Any]:
    """Return cache statistics."""
    return _get_cache().stats


# ---------------------------------------------------------------------------
# HTTP Response Cache
# ---------------------------------------------------------------------------


class HttpCacheEntry:
    """A cached HTTP response with expiration tracking."""

    def __init__(self, status_code: int, headers: dict[str, str], body: str, timestamp: float, ttl: int):
        self.status_code = status_code
        self.headers = headers
        self.body = body
        self.timestamp = timestamp
        self.ttl = ttl

    @property
    def is_expired(self) -> bool:
        return (time.time() - self.timestamp) >= self.ttl


class HttpCacheStore:
    """In-memory HTTP response cache with TTL-based expiration."""

    def __init__(self, ttl: int = 3600):
        self._store: dict[str, HttpCacheEntry] = {}
        self._ttl = ttl
        self._hits = 0
        self._misses = 0

    @property
    def ttl(self) -> int:
        return self._ttl

    @ttl.setter
    def ttl(self, value: int) -> None:
        self._ttl = value

    def get(self, key: str) -> HttpCacheEntry | None:
        entry = self._store.get(key)
        if entry is None:
            self._misses += 1
            return None
        if entry.is_expired:
            del self._store[key]
            self._misses += 1
            return None
        self._hits += 1
        return entry

    def set(self, key: str, status_code: int, headers: dict[str, str], body: str, ttl: int | None = None) -> None:
        effective_ttl = ttl if ttl is not None else self._ttl
        self._store[key] = HttpCacheEntry(
            status_code=status_code,
            headers=headers,
            body=body,
            timestamp=time.time(),
            ttl=effective_ttl,
        )

    def delete(self, key: str) -> bool:
        if key in self._store:
            del self._store[key]
            return True
        return False

    def clear(self) -> int:
        count = len(self._store)
        self._store.clear()
        self._hits = 0
        self._misses = 0
        return count

    def cleanup_expired(self) -> int:
        expired_keys = [k for k, v in self._store.items() if v.is_expired]
        for key in expired_keys:
            del self._store[key]
        return len(expired_keys)

    @property
    def stats(self) -> dict[str, Any]:
        total = self._hits + self._misses
        return {
            "hits": self._hits,
            "misses": self._misses,
            "size": len(self._store),
            "total_requests": total,
            "hit_rate": round(self._hits / total * 100, 1) if total > 0 else 0.0,
        }

    def __len__(self) -> int:
        return len(self._store)


def generate_http_cache_key(url: str) -> str:
    """Generate a deterministic cache key from a request URL."""
    parsed = urlparse(url)
    query_params = sorted(parse_qs(parsed.query).items())
    normalized = f"{parsed.path}?{urlencode(query_params)}"
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


# Singleton HTTP cache store
_http_response_cache = HttpCacheStore(ttl=3600)


def _get_http_cache() -> HttpCacheStore:
    return _http_response_cache


def http_cache_get(key: str) -> HttpCacheEntry | None:
    return _get_http_cache().get(key)


def http_cache_set(key: str, status_code: int, headers: dict[str, str], body: str) -> None:
    _get_http_cache().set(key, status_code, headers, body)


def http_cache_clear() -> int:
    return _get_http_cache().clear()


def http_cache_cleanup_expired() -> int:
    return _get_http_cache().cleanup_expired()


def http_cache_stats() -> dict[str, Any]:
    return _get_http_cache().stats


# ---------------------------------------------------------------------------
# Tool call cache singleton and helpers
# ---------------------------------------------------------------------------

_tool_call_cache = ToolCallCacheStore(ttl=3600)


def _get_tool_call_cache() -> ToolCallCacheStore:
    return _tool_call_cache


def tool_call_cache_get(key: str) -> ToolCallCacheEntry | None:
    return _get_tool_call_cache().get(key)


def tool_call_cache_set(key: str, result: str) -> None:
    _get_tool_call_cache().set(key, result)


def tool_call_cache_clear() -> int:
    return _get_tool_call_cache().clear()


def tool_call_cache_stats() -> dict[str, Any]:
    return _get_tool_call_cache().stats


# ---------------------------------------------------------------------------
# TOOL_CALL file logging configuration
# ---------------------------------------------------------------------------
_TOOL_CALL_LOG_FILE = Path("/tmp/cof_tool_call.log")


class _ToolCallFilter(logging.Filter):
    """Filter that only allows log records containing '[TOOL_CALL]' in the message."""
    def filter(self, record: logging.LogRecord) -> bool:
        return "[TOOL_CALL]" in record.getMessage()


# ---------------------------------------------------------------------------
# ResponseLogger - diagnostic logging for LLM calls
# ---------------------------------------------------------------------------


class ResponseLogger:
    """
    Middleware for LLM response diagnostics.
    
    All [TOOL_CALL] messages are also written to /tmp/cof_tool_call.log
    with no truncation.
    """

    def __init__(self, log_level: str = "INFO"):
        self.log_level = log_level
        logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

        if not logger.handlers:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(getattr(logging, log_level.upper(), logging.INFO))
            console_formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
            console_handler.setFormatter(console_formatter)
            logger.addHandler(console_handler)

            _TOOL_CALL_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
            tool_call_handler = logging.FileHandler(
                _TOOL_CALL_LOG_FILE,
                mode="a",
                encoding="utf-8",
            )
            tool_call_handler.setLevel(logging.DEBUG)
            tool_call_formatter = logging.Formatter("%(message)s")
            tool_call_handler.setFormatter(tool_call_formatter)
            tool_call_handler.addFilter(_ToolCallFilter())
            logger.addHandler(tool_call_handler)

    def generate_conversation_hash(
        self, messages: list[dict], tools: list[dict] | None = None
    ) -> str:
        """Generate a deterministic hash for the complete conversation context."""
        canonical: dict[str, Any] = {
            "messages": messages,
            "tools": tools,
        }
        canonical_str = json.dumps(canonical, sort_keys=True, default=str)
        return hashlib.sha256(canonical_str.encode()).hexdigest()

    def log_request(
        self,
        conversation_hash: str,
        messages: list[dict],
        tools: list[dict] | None,
        model: str,
        turn: int,
    ) -> None:
        msg_summary = []
        for i, msg in enumerate(messages):
            if isinstance(msg, dict):
                role = msg.get("role", "unknown")
                content = msg.get("content", "") or ""
            else:
                role = getattr(msg, "role", "unknown")
                content = getattr(msg, "content", "") or ""
            content_len = len(content) if content else 0
            msg_summary.append(f"  [{i}] {role}: {content_len} chars")

        tool_names = [t.get("function", {}).get("name", "?") for t in (tools or [])]

        logger.info(
            f"[TOOL_CALL] Turn {turn} REQUEST | model={model} | "
            f"conv_hash={conversation_hash[:12]}... | "
            f"messages_count={len(messages)} | "
            f"tools={tool_names}"
        )

    def log_response(
        self,
        conversation_hash: str,
        turn: int,
        response: Any,
        finish_reason: str | None,
        prompt_tokens: int | None,
        completion_tokens: int | None,
        total_tokens: int | None,
        model: str,
    ) -> None:
        if response is None:
            content = None
            content_len = 0
            is_empty = True
        else:
            content = getattr(response, "content", None)
            content_len = len(content) if content else 0
            is_empty = content is None or content.strip() == ""

        token_info = ""
        if prompt_tokens is not None:
            token_info += f" | prompt_tok={prompt_tokens}"
        if completion_tokens is not None:
            token_info += f" | completion_tok={completion_tokens}"
        if total_tokens is not None:
            token_info += f" | total_tok={total_tokens}"

        logger.info(
            f"[TOOL_CALL] Turn {turn} RESPONSE | model={model} | "
            f"conv_hash={conversation_hash[:12]}... | "
            f"finish_reason={finish_reason} | "
            f"content_len={content_len} | is_empty={is_empty}"
            f"{token_info}"
        )

        if finish_reason == "length":
            logger.warning(
                f"[TOOL_CALL] TRUNCATION DETECTED on turn {turn} | "
                f"conv_hash={conversation_hash[:12]}... | "
                f"The response was truncated at {completion_tokens} tokens."
            )

        if is_empty and finish_reason == "stop":
            logger.warning(
                f"[TOOL_CALL] EMPTY RESPONSE on turn {turn} | "
                f"conv_hash={conversation_hash[:12]}... | "
                f"The model stopped with 'stop' reason but produced no content."
            )

        if content:
            response_checksum = hashlib.md5(content.encode()).hexdigest()
            logger.debug(
                f"[TOOL_CALL] Response checksum: {response_checksum} | "
                f"conv_hash={conversation_hash[:12]}..."
            )

    def log_tool_calls(self, conversation_hash: str, turn: int, tool_calls: list[Any]) -> None:
        call_info = []
        for i, call in enumerate(tool_calls):
            func_name = getattr(call.function, "name", "?")
            func_args = getattr(call.function, "arguments", "{}")
            call_id = getattr(call, "id", "?")
            args_summary = func_args[:100] + "..." if len(func_args) > 100 else func_args
            call_info.append(f"  [{i}] id={call_id} | func={func_name} | args={args_summary}")
            logger.info(
                f"[TOOL_CALL] Turn {turn} | tool_call: {func_name}({args_summary[:200]})"
            )

    def log_tool_result(
        self, conversation_hash: str, turn: int, call_id: str, func_name: str, result: str
    ) -> None:
        result_len = len(result) if result else 0
        logger.info(
            f"[TOOL_CALL] Turn {turn} TOOL_RESULT | "
            f"call_id={call_id} | func={func_name} | "
            f"result_len={result_len}"
        )

    def log_final_response(
        self,
        conversation_hash: str,
        user_message: str,
        final_result: str,
        total_turns: int,
    ) -> None:
        result_len = len(final_result) if final_result else 0
        result_preview = final_result[:500] if final_result else ""

        logger.info(
            f"[TOOL_CALL] FINAL RESPONSE | "
            f"conv_hash={conversation_hash[:12]}... | "
            f"turns={total_turns} | result_len={result_len}"
        )

        if result_len > 0:
            logger.debug(f"[TOOL_CALL] Final response preview:\n{result_preview}")

        if final_result:
            response_checksum = hashlib.md5(final_result.encode()).hexdigest()
            logger.info(
                f"[TOOL_CALL] Response checksum: {response_checksum} | "
                f"conv_hash={conversation_hash[:12]}..."
            )

    def log_error(self, error: Exception, context: str = "") -> None:
        context_str = f" | context={context}" if context else ""
        logger.error(
            f"[TOOL_CALL] ERROR{context_str} | "
            f"exception={type(error).__name__}: {error}"
        )


# ---------------------------------------------------------------------------
# Structured response cache helpers
# ---------------------------------------------------------------------------


def _build_response_cache_key(
    conversation_hash: str,
    tool_cache_keys: list[str],
    prompt_id: str,
    prompt_version: int,
    model_name: str,
) -> str:
    """
    Build a deterministic response cache key using conversation hash.
    
    The cache key is based on the conversation hash which uniquely identifies
    the complete conversation state (messages + tools). This ensures that
    different customers get different cache keys even when they access the
    same tool cache keys.
    
    Args:
        conversation_hash: SHA256 hash of the conversation context
        tool_cache_keys: List of structured tool cache keys used during execution
        prompt_id: Prompt template identifier
        prompt_version: Prompt version number
        model_name: LLM model name
    
    Returns:
        SHA256 hex digest string
    """
    if tool_cache_keys:
        sorted_keys = sorted(tool_cache_keys)
        key_string = f"_response:{conversation_hash[:16]}:{prompt_id}:{prompt_version}:{model_name}:{'|'.join(sorted_keys)}"
    else:
        key_string = f"_no_tools:{conversation_hash[:16]}:{prompt_id}:{prompt_version}:{model_name}"
    
    return hashlib.sha256(key_string.encode("utf-8")).hexdigest()


def _store_structured_response(
    cache: CacheStore,
    conversation_hash: str,
    tool_cache_keys: list[str],
    prompt_id: str,
    prompt_version: int,
    model_name: str,
    final_result: str,
    use_cache: bool,
) -> str:
    """Build a structured response cache key and store the response."""
    if not use_cache:
        return ""

    response_cache_key = _build_response_cache_key(
        conversation_hash, tool_cache_keys, prompt_id, prompt_version, model_name
    )
    response_cache_key_preview = response_cache_key[:12]

    cache.set(response_cache_key, final_result)
    logger.info(
        f"[CACHE] STRUCTURED STORED for key={response_cache_key_preview}... | "
        f"conv_hash={conversation_hash[:12]}... | "
        f"tools_used={len(tool_cache_keys)} | response_len={len(final_result)} | ttl={cache.ttl}s"
    )

    return response_cache_key


# ---------------------------------------------------------------------------
# Singleton logger instance
# ---------------------------------------------------------------------------

_response_logger: ResponseLogger | None = None


def _get_logger() -> ResponseLogger:
    """Get or create the singleton ResponseLogger instance."""
    global _response_logger
    if _response_logger is None:
        _response_logger = ResponseLogger()
    return _response_logger


# ---------------------------------------------------------------------------
# Main wrapper function with caching
# ---------------------------------------------------------------------------


def _call_llm_impl(
    user_message: str,
    model: str | None,
    max_turns: int,
    use_cache: bool,
    system_prompt: str | None = None,
    tool_definitions: list[dict] | None = None,
    prompt_id: str = "default",
    prompt_version: int = 1,
) -> tuple[str, bool]:
    """
    Internal implementation of the LLM call with caching.

    Args:
        user_message: The user's question or request (customer name).
        model: Optional model name.
        max_turns: Maximum number of LLM turns.
        use_cache: If True, check cache before LLM call and store result after.
        system_prompt: Optional custom system prompt.
        tool_definitions: Optional custom tool definitions.
        prompt_id: Prompt template identifier (e.g., "guest-search").
        prompt_version: Prompt version number.

    Returns:
        (response_text, was_cached) tuple.
    """
    from app.services.cache_key_builder import build_cache_key
    from app.services.llm import TOOL_DEFINITIONS, SHARED_SYSTEM_PROMPT, get_llm_config
    from app.services.tool_calling import TOOL_EXECUTORS

    client, model_name = get_llm_config()
    if model:
        model_name = model

    effective_system_prompt = system_prompt if system_prompt is not None else SHARED_SYSTEM_PROMPT
    effective_tool_definitions = tool_definitions if tool_definitions is not None else TOOL_DEFINITIONS

    response_logger = _get_logger()
    response_cache = _get_cache()
    tool_cache = _get_tool_call_cache()

    logger.info(
        f"[TOOL_CALL] Starting call_llm_with_db_tools | "
        f"user_msg_preview={user_message[:100]}... | "
        f"prompt_id={prompt_id} v{prompt_version} | model={model_name} | use_cache={use_cache}"
    )

    # --- Cache miss: call the LLM ---
    if use_cache:
        logger.info(f"[CACHE] MISS | calling LLM")

    # Initialize conversation
    messages: list[dict] = [
        {"role": "system", "content": effective_system_prompt},
        {"role": "user", "content": user_message},
    ]

    any_tool_cached = False
    used_tool_cache_keys: list[str] = []

    # Generate conversation hash for cache key differentiation
    conversation_hash = response_logger.generate_conversation_hash(messages, effective_tool_definitions)

    # -----------------------------------------------------------------------
    # Tool-call loop detection
    # -----------------------------------------------------------------------
    recent_calls: dict[tuple[str, tuple], int] = {}

    def _freeze_args(args: dict) -> tuple:
        result = []
        for k in sorted(args):
            v = args[k]
            if isinstance(v, list):
                result.append((k, tuple(v)))
            else:
                result.append((k, v))
        return tuple(result)

    def _check_loop(tool_calls_list: list) -> bool:
        for tc in tool_calls_list:
            fname = tc.function.name  # type: ignore[attr-defined]
            fargs = json.loads(tc.function.arguments)  # type: ignore[attr-defined]
            key = (fname, _freeze_args(fargs))
            count = recent_calls.get(key, 0) + 1
            recent_calls[key] = count
            if count >= _MAX_IDENTICAL_TOOL_CALLS:
                logger.warning(
                    f"[LOOP-DET] TOOL-CALL LOOP DETECTED | "
                    f"conv_hash={conversation_hash[:12]}... | "
                    f"tool={fname} called {count} times consecutively | "
                    f"forcing termination"
                )
                return True
        return False

    def _reset_loop_detector() -> None:
        nonlocal prev_turn_calls
        recent_calls.clear()
        prev_turn_calls = set()

    prev_turn_calls: set[tuple[str, tuple]] = set()

    final_result = ""
    turn = max_turns

    for turn in range(1, max_turns + 1):
        response_logger.log_request(
            conversation_hash, messages, effective_tool_definitions, model_name, turn
        )

        response = client.chat.completions.create(
            model=model_name,
            messages=messages,
            tools=effective_tool_definitions,  # type: ignore[arg-type]
            temperature=0.1,
            max_tokens=102400,
        )

        assistant_message = response.choices[0].message
        finish_reason = response.choices[0].finish_reason

        if response.usage:
            prompt_tokens = response.usage.prompt_tokens
            completion_tokens = response.usage.completion_tokens
            total_tokens = response.usage.total_tokens
        else:
            prompt_tokens = None
            completion_tokens = None
            total_tokens = None

        response_logger.log_response(
            conversation_hash=conversation_hash,
            turn=turn,
            response=assistant_message,
            finish_reason=finish_reason,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            model=model_name,
        )

        tool_calls = assistant_message.tool_calls or []

        if tool_calls:
            response_logger.log_tool_calls(conversation_hash, turn, tool_calls)

            if _check_loop(tool_calls):
                logger.warning(
                    f"[LOOP-DET] Breaking out of tool-call loop at turn {turn} | "
                    f"conv_hash={conversation_hash[:12]}..."
                )
                break

        if not tool_calls:
            # Final response
            final_result = assistant_message.content or "The LLM returned an empty response."

            # Store in structured response cache
            if use_cache:
                _store_structured_response(
                    response_cache, conversation_hash, used_tool_cache_keys,
                    prompt_id, prompt_version, model_name, final_result, use_cache
                )

            response_logger.log_final_response(
                conversation_hash, user_message, final_result, turn
            )

            return final_result, any_tool_cached

        # Append assistant message
        messages.append(assistant_message)  # type: ignore[arg-type]

        # Execute ALL tool calls in this response
        for tool_call in tool_calls:
            func_name = tool_call.function.name  # type: ignore[attr-defined]
            func_args = json.loads(tool_call.function.arguments)  # type: ignore[attr-defined]
            call_id = tool_call.id

            # --- Structured cache key for this tool call ---
            try:
                tool_cache_key = build_cache_key(
                    tool_name=func_name,
                    params=func_args,
                    prompt_id=prompt_id,
                    prompt_version=prompt_version,
                    model_name=model_name,
                )
                tool_cache_key_preview = tool_cache_key[:12]
            except Exception as e:
                tool_cache_key = None
                tool_cache_key_preview = f"ERROR:{e}"

            # Check tool cache
            cached_tool_result = None
            if use_cache and tool_cache_key:
                cached_tool_result = tool_cache.get(tool_cache_key)
            if cached_tool_result is not None:
                logger.info(
                    f"[TOOL-CACHE] HIT for key={tool_cache_key_preview}... | "
                    f"tool={func_name} | result_len={len(cached_tool_result.result)}"
                )
                any_tool_cached = True
                used_tool_cache_keys.append(tool_cache_key)

            if cached_tool_result is not None:
                result = cached_tool_result.result
            else:
                logger.info(
                    f"[TOOL_CALL] Turn {turn} EXECUTING | "
                    f"call_id={call_id} | func={func_name} | cache={'MISS' if tool_cache_key else 'SKIPPED'}"
                )

                if func_name in TOOL_EXECUTORS:
                    try:
                        result = TOOL_EXECUTORS[func_name](func_args)
                    except Exception as e:
                        result = f"Error executing {func_name}: {str(e)}"
                        response_logger.log_error(e, context=f"tool_execution:{func_name}")
                else:
                    result = f"Unknown tool: {func_name}"

                if use_cache and tool_cache_key is not None:
                    tool_cache.set(tool_cache_key, result)
                    logger.info(
                        f"[TOOL-CACHE] STORED for key={tool_cache_key_preview}... | "
                        f"tool={func_name} | result_len={len(result)}"
                    )

            response_logger.log_tool_result(
                conversation_hash, turn, call_id, func_name, result
            )

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call_id,
                    "content": result,
                }
            )

        _reset_loop_detector()

        # PRE-FINAL HIT: Check if we can skip remaining LLM turns
        # Uses conversation_hash to ensure each customer's conversation is unique
        if use_cache and used_tool_cache_keys:
            pre_response_cache_key = _build_response_cache_key(
                conversation_hash, used_tool_cache_keys, prompt_id, prompt_version, model_name
            )
            pre_response_cache_key_preview = pre_response_cache_key[:12]

            cached_response_entry = response_cache.get(pre_response_cache_key)
            if cached_response_entry is not None:
                logger.info(
                    f"[CACHE] PRE-FINAL HIT for key={pre_response_cache_key_preview}... | "
                    f"conv_hash={conversation_hash[:12]}... | "
                    f"tools_used={len(used_tool_cache_keys)} | "
                    f"skipping remaining LLM turns | "
                    f"response_len={len(cached_response_entry.response)}"
                )
                final_result = cached_response_entry.response

                response_logger.log_final_response(
                    conversation_hash, user_message, final_result, turn
                )

                return final_result, True

    # Exhausted max_turns or loop detection
    if recent_calls:
        max_count = max(recent_calls.values()) if recent_calls else 0
        if max_count >= _MAX_IDENTICAL_TOOL_CALLS:
            final_result = (
                "I apologize, but I keep requesting the same data without being able to process it. "
                "This appears to be a technical limitation. Please try rephrasing your question "
                "or providing more specific details about what information you need."
            )
            logger.warning(
                f"[TOOL-LOOP] TOOL-CALL LOOP DETECTED AND BROKE | "
                f"conv_hash={conversation_hash[:12]}... | "
                f"max_consecutive_calls={max_count}."
            )
        else:
            final_result = f"The request exceeded the maximum of {max_turns} turns. Please simplify your request."
            logger.warning(
                f"[TOOL_CALL] MAX TURNS EXCEEDED | "
                f"conv_hash={conversation_hash[:12]}... | max_turns={max_turns}."
            )
    else:
        final_result = f"The request exceeded the maximum of {max_turns} turns. Please simplify your request."
        logger.warning(
            f"[TOOL_CALL] MAX TURNS EXCEEDED | "
            f"conv_hash={conversation_hash[:12]}... | max_turns={max_turns}."
        )

    _store_structured_response(
        response_cache, conversation_hash, used_tool_cache_keys,
        prompt_id, prompt_version, model_name, final_result, use_cache
    )

    response_logger.log_final_response(
        conversation_hash, user_message, final_result, turn
    )

    return final_result, any_tool_cached


def call_llm_with_db_tools(
    user_message: str,
    model: str | None = None,
    max_turns: int = 100,
    use_cache: bool = True,
    system_prompt: str | None = None,
    tool_definitions: list[dict] | None = None,
    prompt_id: str = "default",
    prompt_version: int = 1,
) -> str:
    """
    Call the LLM with database tools and handle the tool calling loop.

    Args:
        user_message: The user's question or request
        model: Optional model name
        max_turns: Maximum number of LLM turns (default 100)
        use_cache: If True, use response caching (default True)
        system_prompt: Optional custom system prompt
        tool_definitions: Optional custom tool definitions
        prompt_id: Prompt template identifier (e.g., "guest-search")
        prompt_version: Prompt version number

    Returns:
        The final response text from the LLM (possibly from cache)
    """
    result, _ = _call_llm_impl(
        user_message, model, max_turns, use_cache, system_prompt, tool_definitions, prompt_id, prompt_version
    )
    return result


def call_llm_with_db_tools_with_cache_flag(
    user_message: str,
    model: str | None = None,
    max_turns: int = 100,
    use_cache: bool = True,
    system_prompt: str | None = None,
    tool_definitions: list[dict] | None = None,
    prompt_id: str = "default",
    prompt_version: int = 1,
) -> tuple[str, bool]:
    """
    Call the LLM with database tools and caching.

    Returns:
        A tuple of (response_text, was_cached) where was_cached is True if cached.
    """
    return _call_llm_impl(
        user_message, model, max_turns, use_cache, system_prompt, tool_definitions, prompt_id, prompt_version
    )