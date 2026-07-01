#!/usr/bin/env python3
"""
SQLAlchemy tool calling service for LLM interactions.

Provides a set of read-only database tools that an LLM can call via function calling.
Supports multiple tool calls in a single response and chains them across multiple turns.

Imports tool definitions and system prompt from app.services.llm for consistency.

Usage:
    from app.services.tool_calling import call_llm_with_db_tools
    
    response = call_llm_with_db_tools("Show me all special guests and their reservations")
    print(response)
"""

import json
from typing import Any

from app.services.llm import TOOL_DEFINITIONS, SHARED_SYSTEM_PROMPT, get_llm_config
from app.services.tool_logic import execute_query_guest_with_reservations


# ---------------------------------------------------------------------------
# Response Cache Integration
# ---------------------------------------------------------------------------
# The response_cache module provides diagnostic logging and future caching.
# To enable response logging/caching, change the import below to use
# the wrapper from response_cache instead.
#
# To ENABLE diagnostic logging, uncomment the following import and remove
# the standard import above:
#
#   from app.services.response_cache import call_llm_with_db_tools  # WITH logging
#
# For now, this module provides the base implementation. The response_cache
# module wraps this with diagnostics.
# ---------------------------------------------------------------------------

# Map tool names to their execution functions
# Only query_guest_with_reservations is registered — it handles all guest/reservation queries
# in a single tool call, eliminating the multi-turn workflow that was causing latency.
TOOL_EXECUTORS = {
    "query_guest_with_reservations": execute_query_guest_with_reservations,
}


def call_llm_with_db_tools(
    user_message: str,
    model: str | None = None,
    max_turns: int = 100,
) -> str:
    """
    Call the LLM with database tools and handle the tool calling loop.

    This function:
    1. Sends the user message with system prompt and tool definitions to the LLM
    2. Collects any function calls from the response
    3. Executes all function calls (supports multiple in one response)
    4. Sends the results back to the LLM
    5. Repeats until the LLM stops calling tools (or max_turns reached)
    6. Returns the final response text

    Args:
        user_message: The user's question or request
        model: Optional model name (uses configured model from llm.py if None)
        max_turns: Max number of LLM turns (default 10)

    Returns:
        The final response text from the LLM
    """
    client, model_name = get_llm_config()
    if model:
        model_name = model

    # Initialize conversation - uses unified system prompt from llm.py
    messages = [
        {"role": "system", "content": SHARED_SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]

    for turn in range(max_turns):
        # Call LLM with tools
        response = client.chat.completions.create(
            model=model_name,
            messages=messages,
            tools=TOOL_DEFINITIONS,
            temperature=0.1,
            max_tokens=10240,
        )

        assistant_message = response.choices[0].message

        # Check if the assistant wants to call tools
        tool_calls = assistant_message.tool_calls or []

        if not tool_calls:
            # No more tool calls - this is the final response
            return assistant_message.content or "The LLM returned an empty response."

        # Append assistant message to conversation
        messages.append(assistant_message)

        # Execute ALL tool calls in this response (batch execution)
        for tool_call in tool_calls:
            # Use attribute access for tool_call.function
            func_name = tool_call.function.name
            func_args = json.loads(tool_call.function.arguments)
            call_id = tool_call.id

            # Execute the tool
            if func_name in TOOL_EXECUTORS:
                try:
                    result = TOOL_EXECUTORS[func_name](func_args)
                except Exception as e:
                    result = f"Error executing {func_name}: {str(e)}"
            else:
                result = f"Unknown tool: {func_name}"

            # Append tool result to conversation
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call_id,
                    "content": result,
                }
            )

    # If we exhausted max_turns, return a message
    return f"The request exceeded the maximum of {max_turns} turns. Please simplify your request."