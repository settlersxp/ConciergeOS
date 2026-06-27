"""Prompt building and resolution for performance tests.

Provides helpers to construct the system and user prompts sent to the LLM,
delegating data fetching and formatting to ``app.services.llm``.
"""

from __future__ import annotations

from .settings import TestSettings

# Lazy imports to avoid circular dependencies at package load time
# These are resolved from the single source of truth in app.services.llm


def _get_llm_module():
    """Import shared prompts from the single source of truth."""
    from app.services.llm import (
        SHARED_SYSTEM_PROMPT,
        build_user_prompt,
        fetch_all_as_json,
        fetch_all_as_xml,
        fetch_all_guests_and_reservations,
    )
    return SHARED_SYSTEM_PROMPT, build_user_prompt, fetch_all_as_json, fetch_all_as_xml, fetch_all_guests_and_reservations


# ── Prompt resolution ───────────────────────────────────────────────────────


def resolve_system_prompt(settings: TestSettings) -> str:
    """Return the effective system prompt based on settings.

    Uses the shared system prompt when tool calling is enabled, otherwise
    falls back to the default or user-configured prompt.
    """
    if settings.use_tool_calling:
        shared_system_prompt, _, _, _, _ = _get_llm_module()
        return shared_system_prompt
    return settings.system_prompt


def build_user_prompt_from_name(customer_name: str, data_format: str = "csv") -> str:
    """Build the full user prompt with embedded DB data using the specified format."""
    _, build_user_prompt, fetch_all_as_json, fetch_all_as_xml, fetch_all_guests_and_reservations = _get_llm_module()

    if data_format == "json":
        data = fetch_all_as_json()
    elif data_format == "xml":
        data = fetch_all_as_xml()
    else:
        data = fetch_all_guests_and_reservations()
    return build_user_prompt(customer_name, data)


def _build_runtime_variables(name: str) -> dict[str, str]:
    """Build runtime variable map from a guest name.

    Splits the full name into first/last parts so templates can use
    conventional {table.field} keys like ``customers.first_name``.
    """
    name_parts = name.strip().split(None, 1)
    vars: dict[str, str] = {}
    if len(name_parts) == 2:
        first, last = name_parts
        vars["customers.first_name"] = first
        vars["customers.last_name"] = last
        vars["customers.name"] = name
    elif len(name_parts) == 1:
        vars["customers.first_name"] = name_parts[0]
        vars["customers.last_name"] = ""
        vars["customers.name"] = name_parts[0]
    else:
        vars["customers.first_name"] = ""
        vars["customers.last_name"] = ""
        vars["customers.name"] = name
    return vars


def resolve_user_prompt(
    settings: TestSettings,
    customer_name: str | None = None,
) -> str:
    """Resolve the user prompt for a single request.

    Returns a computed prompt string without mutating the shared
    ``TestSettings`` instance, making this safe to call from multiple
    threads concurrently.

    Uses the shared ``resolve_all_placeholders`` so that both the normal
    LLM flow and performance testing share the exact same placeholder
    resolution logic.
    """
    from app.services.placeholders import resolve_all_placeholders

    name = customer_name or settings.customer_name

    if settings.user_prompt:
        runtime_vars = _build_runtime_variables(name)
        # Merge any additional runtime variables from settings
        if hasattr(settings, "runtime_variables") and settings.runtime_variables:  # type: ignore[attr-defined]
            runtime_vars.update(settings.runtime_variables)  # type: ignore[attr-defined]
        return resolve_all_placeholders(settings.user_prompt, runtime_vars)

    if settings.use_tool_calling:
        return f"Find all information about the customer named: {name}"

    return build_user_prompt_from_name(name, settings.data_format)
