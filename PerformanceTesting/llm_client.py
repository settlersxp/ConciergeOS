"""LLM communication layer for performance testing.

Wraps the OpenAI client to handle both standard chat completions and
the multi-turn tool calling protocol.
"""

from __future__ import annotations

import json
from typing import Any

from .model_info import create_openai_client
from .settings import (
    DEFAULT_MAX_TOKENS,
    DEFAULT_TEMPERATURE,
    MAX_TOOL_TURNS,
    TOOL_CALL_MAX_TOKENS,
    TOOL_CALL_TEMPERATURE,
)
from .tool_executors import TOOL_EXECUTORS


# ── Tool calling loop ───────────────────────────────────────────────────────


def execute_tool_calling_loop(
    client: Any,
    messages: list[dict[str, Any]],
    model_name: str,
    tool_definitions: list[dict[str, Any]],
    max_turns: int = MAX_TOOL_TURNS,
) -> str:
    """Execute the multi-turn tool calling protocol.

    1. Send message with tools to LLM.
    2. If LLM returns tool_calls, execute them and send results back.
    3. Repeat until LLM responds with content (no tool calls) or max_turns reached.
    """
    for _turn in range(max_turns):
        response = client.chat.completions.create(
            model=model_name,
            messages=messages,
            tools=tool_definitions,
            temperature=TOOL_CALL_TEMPERATURE,
            max_tokens=TOOL_CALL_MAX_TOKENS,
        )

        assistant_message = response.choices[0].message
        tool_calls = assistant_message.tool_calls or []

        if not tool_calls:
            return assistant_message.content or "The LLM returned an empty response."

        messages.append(assistant_message)

        # Execute ALL tool calls in this response (batch execution)
        for tool_call in tool_calls:
            func_name = tool_call.function.name
            func_args: dict[str, Any] = json.loads(tool_call.function.arguments)
            call_id = tool_call.id

            executor = TOOL_EXECUTORS.get(func_name)
            if executor is not None:
                try:
                    result = executor(func_args)
                except Exception as e:
                    result = f"Error executing {func_name}: {e}"
            else:
                result = f"Unknown tool: {func_name}"

            messages.append({
                "role": "tool",
                "tool_call_id": call_id,
                "content": result,
            })

    return f"The request exceeded the maximum of {max_turns} turns. Please simplify your request."


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

    This is the single, shared implementation that both single-guest and
    multi-guest code paths delegate to.
    """
    client = create_openai_client(base_url)
    messages: list[dict[str, str]] = [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_prompt},
    ]

    if use_tool_calling and tool_definitions:
        return execute_tool_calling_loop(
            client, messages, model_name, tool_definitions
        )

    response = client.chat.completions.create(
        model=model_name,
        messages=messages,
        temperature=DEFAULT_TEMPERATURE,
        max_tokens=DEFAULT_MAX_TOKENS,
    )
    return response.choices[0].message.content or "The LLM returned an empty response."