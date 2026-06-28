"""LLM communication layer for performance testing.

Wraps the OpenAI client to handle both standard chat completions and
the multi-turn tool calling protocol.

For tool calling, delegates to app.services.response_cache.call_llm_with_db_tools
which provides diagnostic logging and future caching support.
"""

from __future__ import annotations

from typing import Any

from app.services.llm import get_llm_config
from .settings import (
    DEFAULT_MAX_TOKENS,
    DEFAULT_TEMPERATURE,
)


# ── Main LLM query entry point ──────────────────────────────────────────────


def query_guest_with_llm(
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

    Args:
        model_name: The model name to use.
        system_content: The system prompt to use.
        user_prompt: The user's query (customer name).
        use_tool_calling: Whether to use tool calling mode.
        tool_definitions: Optional tool definitions for the LLM.
    """
    if use_tool_calling:
        # Use the response_cache wrapper which handles tool calling loop + logging
        # Forward system_content and tool_definitions to ensure the correct prompts are used
        from app.services.response_cache import call_llm_with_db_tools
        return call_llm_with_db_tools(
            user_prompt,
            model=model_name,
            system_prompt=system_content,
            tool_definitions=tool_definitions,
        )

    # Non-tool-calling mode: direct chat completion
    client, _ = get_llm_config()
    messages: list[Any] = [
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
