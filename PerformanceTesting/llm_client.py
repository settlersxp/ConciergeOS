"""LLM communication layer for performance testing.

Wraps the OpenAI client to handle both standard chat completions and
the multi-turn tool calling protocol.

For tool calling, delegates to app.services.response_cache.call_llm_with_db_tools
which provides diagnostic logging and future caching support.
"""

from __future__ import annotations

from typing import Any

from .model_info import create_openai_client
from .settings import (
    DEFAULT_MAX_TOKENS,
    DEFAULT_TEMPERATURE,
)


# ── Main LLM query entry point ──────────────────────────────────────────────


def query_guest_with_llm(
    base_url: str,
    model_name: str,
    system_content: str,
    user_prompt: str,
    use_tool_calling: bool,
    tool_definitions: list[dict[str, Any]] | None = None,
) -> str:
    """Query the LLM and return the assistant's text response.

    For tool calling mode, delegates to app.services.response_cache.call_llm_with_db_tools
    which provides diagnostic logging (finish_reason, token usage, truncation warnings)
    and future caching support.

    This is the single, shared implementation that both single-guest and
    multi-guest code paths delegate to.
    """
    if use_tool_calling:
        # Use the response_cache wrapper which handles tool calling loop + logging
        from app.services.response_cache import call_llm_with_db_tools
        return call_llm_with_db_tools(user_prompt, model=model_name)

    # Non-tool-calling mode: direct chat completion
    client = create_openai_client(base_url)
    messages: list[dict[str, str]] = [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_prompt},
    ]

    response = client.chat.completions.create(
        model=model_name,
        messages=messages,
        temperature=DEFAULT_TEMPERATURE,
        max_tokens=DEFAULT_MAX_TOKENS,
    )
    return response.choices[0].message.content or "The LLM returned an empty response."
