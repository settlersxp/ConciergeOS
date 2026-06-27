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
from typing import Any
from urllib.parse import urlencode, urlparse, parse_qs

logger = logging.getLogger(__name__)

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

    Single-process use. Designed to be swapped for Redis or other backends later
    without changing the API.

    Usage:
        store = CacheStore(ttl=3600)
        store.set("key", "response")
        entry = store.get("key")
        if entry and not entry.is_expired:
            print(entry.response)
    """

    def __init__(self, ttl: int = 3600):
        """
        Initialize the cache store.

        Args:
            ttl: Time-to-live in seconds (default 3600 = 1 hour)
        """
        self._store: dict[str, CacheEntry] = {}
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

    def get(self, key: str) -> CacheEntry | None:
        """
        Get a cached entry by key.

        Returns None if the key doesn't exist or the entry is expired.
        """
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
        """
        Cache a response.

        Args:
            key: Cache key (SHA256 hash of normalized input)
            response: The LLM response text to cache
            ttl: Optional per-key TTL override (uses instance default if None)
        """
        effective_ttl = ttl if ttl is not None else self._ttl
        self._store[key] = CacheEntry(
            response=response,
            timestamp=time.time(),
            ttl=effective_ttl,
        )

    def delete(self, key: str) -> bool:
        """Remove a specific key. Returns True if the key existed."""
        if key in self._store:
            del self._store[key]
            return True
        return False

    def clear(self) -> int:
        """Remove all cached entries. Returns the count of entries removed."""
        count = len(self._store)
        self._store.clear()
        self._hits = 0
        self._misses = 0
        return count

    def cleanup_expired(self) -> int:
        """Remove all expired entries. Returns the count removed."""
        expired_keys = [k for k, v in self._store.items() if v.is_expired]
        for key in expired_keys:
            del self._store[key]
        return len(expired_keys)

    @property
    def stats(self) -> dict[str, Any]:
        """Return cache hit/miss/size statistics."""
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
# Cache key generation
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
# Singleton cache store
# ---------------------------------------------------------------------------

_response_cache = CacheStore(ttl=3600)


def _get_cache() -> CacheStore:
    """Get the singleton CacheStore instance."""
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
        """Return True if this entry has exceeded its TTL."""
        return (time.time() - self.timestamp) >= self.ttl


class HttpCacheStore:
    """
    In-memory HTTP response cache with TTL-based expiration.

    Caches GET responses by normalized URI + query parameters.
    """

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
    """
    Generate a deterministic cache key from a request URL.

    Normalization: parse URL, sort query parameters for order-independence.
    Only caches GET requests (caller should enforce this).

    Args:
        url: Full request URL (e.g., "http://host/api/reservations?foo=bar&baz=qux")

    Returns:
        SHA256 hex digest string
    """
    parsed = urlparse(url)
    # Sort query params for order-independence
    query_params = sorted(parse_qs(parsed.query).items())
    normalized = f"{parsed.path}?{urlencode(query_params)}"
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


# Singleton HTTP cache store
_http_response_cache = HttpCacheStore(ttl=3600)


def _get_http_cache() -> HttpCacheStore:
    """Get the singleton HTTP CacheStore instance."""
    return _http_response_cache


def http_cache_get(key: str) -> HttpCacheEntry | None:
    """Get a cached HTTP response entry by key."""
    return _get_http_cache().get(key)


def http_cache_set(key: str, status_code: int, headers: dict[str, str], body: str) -> None:
    """Cache an HTTP response with the given key."""
    _get_http_cache().set(key, status_code, headers, body)


def http_cache_clear() -> int:
    """Clear all cached HTTP responses. Returns the count of entries removed."""
    return _get_http_cache().clear()


def http_cache_cleanup_expired() -> int:
    """Remove all expired HTTP cache entries. Returns the count removed."""
    return _get_http_cache().cleanup_expired()


def http_cache_stats() -> dict[str, Any]:
    """Return HTTP cache statistics."""
    return _get_http_cache().stats


# ---------------------------------------------------------------------------
# ResponseLogger - diagnostic logging for LLM calls
# ---------------------------------------------------------------------------


class ResponseLogger:
    """
    Middleware for LLM response diagnostics.

    Logs all relevant diagnostics using Python's standard logging module.
    Caching is handled separately by CacheStore.
    """

    def __init__(self, log_level: str = "INFO"):
        """
        Initialize the response logger.

        Args:
            log_level: Python logging level (DEBUG, INFO, WARNING, ERROR)
        """
        self.log_level = log_level
        logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

        if not logger.handlers:
            handler = logging.StreamHandler()
            handler.setLevel(getattr(logging, log_level.upper(), logging.INFO))
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)

    def generate_conversation_hash(
        self, messages: list[dict], tools: list[dict] | None = None
    ) -> str:
        """
        Generate a deterministic hash for the complete conversation context.

        Args:
            messages: List of message dicts with role and content
            tools: Optional list of tool definitions

        Returns:
            SHA256 hex digest string
        """
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
        """Log the request before sending to LLM."""
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
        logger.debug(
            f"[TOOL_CALL] Message history for turn {turn}:\n"
            + "\n".join(msg_summary)
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
        """Log the response from LLM with diagnostics."""
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
                f"The response was truncated at {completion_tokens} tokens. "
                f"Consider increasing max_tokens or reducing prompt size."
            )

        if is_empty and finish_reason == "stop":
            logger.warning(
                f"[TOOL_CALL] EMPTY RESPONSE on turn {turn} | "
                f"conv_hash={conversation_hash[:12]}... | "
                f"The model stopped with 'stop' reason but produced no content. "
                f"This may indicate a model issue or prompt problem."
            )

        if content:
            response_checksum = hashlib.md5(content.encode()).hexdigest()
            logger.debug(
                f"[TOOL_CALL] Response checksum: {response_checksum} | "
                f"conv_hash={conversation_hash[:12]}..."
            )

    def log_tool_calls(self, conversation_hash: str, turn: int, tool_calls: list[Any]) -> None:
        """Log tool calls made by the LLM."""
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

        logger.debug(
            f"[TOOL_CALL] All tool calls for turn {turn}:\n" + "\n".join(call_info)
        )

    def log_tool_result(
        self, conversation_hash: str, turn: int, call_id: str, func_name: str, result: str
    ) -> None:
        """Log the result of a tool execution."""
        result_len = len(result) if result else 0
        result_preview = result[:200] + "..." if result and len(result) > 200 else result or ""

        logger.info(
            f"[TOOL_CALL] Turn {turn} TOOL_RESULT | "
            f"call_id={call_id} | func={func_name} | "
            f"result_len={result_len}"
        )
        logger.debug(f"[TOOL_CALL] Tool result for {func_name}:\n{result_preview}")

    def log_final_response(
        self,
        conversation_hash: str,
        user_message: str,
        final_result: str,
        total_turns: int,
    ) -> None:
        """Log the final response that will be returned to the caller."""
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
        """Log errors that occur during LLM calls."""
        context_str = f" | context={context}" if context else ""
        logger.error(
            f"[TOOL_CALL] ERROR{context_str} | "
            f"exception={type(error).__name__}: {error}"
        )


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
) -> tuple[str, bool]:
    """
    Internal implementation of the LLM call with caching.

    Returns:
        (response_text, was_cached) tuple.
    """
    from app.services.llm import TOOL_DEFINITIONS, SHARED_SYSTEM_PROMPT, get_llm_config
    from app.services.tool_calling import TOOL_EXECUTORS

    client, model_name = get_llm_config()
    if model:
        model_name = model

    response_logger = _get_logger()
    cache = _get_cache()

    # Generate cache key from the raw user message (customer name)
    cache_key = generate_cache_key(user_message)

    logger.info(
        f"[TOOL_CALL] Starting call_llm_with_db_tools | "
        f"user_msg_preview={user_message[:100]}... | "
        f"cache_key={cache_key[:12]}... | use_cache={use_cache}"
    )

    # --- Cache hit: return immediately ---
    if use_cache:
        cached_entry = cache.get(cache_key)
        if cached_entry is not None:
            logger.info(
                f"[CACHE] HIT for key={cache_key[:12]}... | "
                f"response_len={len(cached_entry.response)} | "
                f"ttl_remaining={round(cached_entry.ttl - (time.time() - cached_entry.timestamp), 1)}s"
            )
            return cached_entry.response, True

    # --- Cache miss: call the LLM ---
    if use_cache:
        logger.info(f"[CACHE] MISS for key={cache_key[:12]}... | calling LLM")

    # Initialize conversation
    messages: list[dict] = [
        {"role": "system", "content": SHARED_SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]

    # Generate conversation hash for diagnostic logging
    conversation_hash = response_logger.generate_conversation_hash(messages, TOOL_DEFINITIONS)

    for turn in range(1, max_turns + 1):
        # Log request
        response_logger.log_request(
            conversation_hash, messages, TOOL_DEFINITIONS, model_name, turn
        )

        # Call LLM with tools
        response = client.chat.completions.create(
            model=model_name,
            messages=messages,
            tools=TOOL_DEFINITIONS,  # type: ignore[arg-type]
            temperature=0.1,
            max_tokens=102400,
        )

        assistant_message = response.choices[0].message
        finish_reason = response.choices[0].finish_reason

        # Get token usage if available
        if response.usage:
            prompt_tokens = response.usage.prompt_tokens
            completion_tokens = response.usage.completion_tokens
            total_tokens = response.usage.total_tokens
        else:
            prompt_tokens = None
            completion_tokens = None
            total_tokens = None

        # Log response
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

        # Check if the assistant wants to call tools
        tool_calls = assistant_message.tool_calls or []

        if tool_calls:
            response_logger.log_tool_calls(conversation_hash, turn, tool_calls)

        if not tool_calls:
            # No more tool calls - this is the final response
            final_result = assistant_message.content or "The LLM returned an empty response."

            # Store in cache
            if use_cache:
                cache.set(cache_key, final_result)
                logger.info(
                    f"[CACHE] STORED for key={cache_key[:12]}... | "
                    f"response_len={len(final_result)} | ttl={cache.ttl}s"
                )

            # Log final response
            response_logger.log_final_response(
                conversation_hash, user_message, final_result, turn
            )

            return final_result, False

        # Append assistant message to conversation
        messages.append(assistant_message)  # type: ignore[arg-type]

        # Execute ALL tool calls in this response (batch execution)
        for tool_call in tool_calls:
            func_name = tool_call.function.name  # type: ignore[attr-defined]
            func_args = json.loads(tool_call.function.arguments)  # type: ignore[attr-defined]
            call_id = tool_call.id

            # Log tool result before execution
            logger.info(
                f"[TOOL_CALL] Turn {turn} EXECUTING | "
                f"call_id={call_id} | func={func_name} | args={func_args}"
            )

            # Execute the tool
            if func_name in TOOL_EXECUTORS:
                try:
                    result = TOOL_EXECUTORS[func_name](func_args)
                except Exception as e:
                    result = f"Error executing {func_name}: {str(e)}"
                    response_logger.log_error(e, context=f"tool_execution:{func_name}")
            else:
                result = f"Unknown tool: {func_name}"

            # Log tool result
            response_logger.log_tool_result(
                conversation_hash, turn, call_id, func_name, result
            )

            # Append tool result to conversation
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call_id,
                    "content": result,
                }
            )

    # If we exhausted max_turns
    final_result = (
        f"The request exceeded the maximum of {max_turns} turns. "
        f"Please simplify your request."
    )
    response_logger.log_final_response(
        conversation_hash, user_message, final_result, max_turns
    )
    logger.warning(
        f"[TOOL_CALL] MAX TURNS EXCEEDED | "
        f"conv_hash={conversation_hash[:12]}... | "
        f"max_turns={max_turns}. The conversation may be stuck in a tool-call loop."
    )

    return final_result, False


def call_llm_with_db_tools(
    user_message: str,
    model: str | None = None,
    max_turns: int = 100,
    use_cache: bool = True,
) -> str:
    """
    Call the LLM with database tools and handle the tool calling loop.

    This is a drop-in replacement for tool_calling.call_llm_with_db_tools()
    that adds diagnostic logging and transparent response caching.

    Caching behavior:
        - Cache key = SHA256(normalized user_message)
        - Cache is checked BEFORE calling the LLM
        - Cache is stored AFTER a successful response
        - TTL = 3600 seconds (1 hour) by default

    Args:
        user_message: The user's question or request
        model: Optional model name (uses configured model from llm.py if None)
        max_turns: Maximum number of LLM turns (default 100)
        use_cache: If True, check cache before LLM call and store result after (default True)

    Returns:
        The final response text from the LLM (possibly from cache)

    Examples:
        >>> response = call_llm_with_db_tools("Show me all special guests")
        >>> response = call_llm_with_db_tools("John Doe", use_cache=False)  # bypass cache
    """
    result, _ = _call_llm_impl(user_message, model, max_turns, use_cache)
    return result


def call_llm_with_db_tools_with_cache_flag(
    user_message: str,
    model: str | None = None,
    max_turns: int = 100,
    use_cache: bool = True,
) -> tuple[str, bool]:
    """
    Call the LLM with database tools and caching.

    Returns:
        A tuple of (response_text, was_cached) where was_cached is True if the
        response was served from the cache.

    This function is useful when the caller needs to know whether the response
    came from cache (e.g., for the API response's 'cached' field).

    The original call_llm_with_db_tools() is preserved for backward compatibility
    and only returns the response string.
    """
    return _call_llm_impl(user_message, model, max_turns, use_cache)