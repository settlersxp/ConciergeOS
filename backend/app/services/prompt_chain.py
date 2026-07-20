#!/usr/bin/env python3
"""
Prompt chain execution service.

Executes a sequence of prompts (from a PromptGroup) sequentially,
passing each prompt's output as context to the next prompt in the chain.
"""

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import PromptGroup, PromptGroupItem, PromptGroupResult
from app.services.placeholders import resolve_placeholders, resolve_all_placeholders
from app.services.prompts import PromptStore

logger = logging.getLogger(__name__)

# Directory where chain results are saved
RESULTS_DIR = Path("data/prompt_group_results")


def _ensure_results_dir() -> Path:
    """Create the results directory if it doesn't exist."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    return RESULTS_DIR


def _save_result_to_file(group_id: int, chain_result: dict[str, Any]) -> str:
    """Save chain execution result to a JSON file and return the relative path."""
    dest = _ensure_results_dir()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    filename = f"group_{group_id}_{timestamp}.json"
    filepath = dest / filename
    filepath.write_text(json.dumps(chain_result, indent=2, ensure_ascii=False), encoding="utf-8")
    return str(filepath)


# ---------------------------------------------------------------------------
# Shared internal helpers (eliminates duplication between execute_chain
# and execute_chain_step)
# ---------------------------------------------------------------------------

def _load_group_and_items(session: Session, group_id: int) -> tuple[PromptGroup, list[PromptGroupItem]]:
    """Load a PromptGroup and its ordered items. Raises ValueError if not found."""
    group = session.query(PromptGroup).filter(PromptGroup.group_id == group_id).first()
    if not group:
        raise ValueError(f"PromptGroup {group_id} not found")

    items = (
        session.query(PromptGroupItem)
        .filter(PromptGroupItem.group_id == group_id)
        .order_by(PromptGroupItem.position)
        .all()
    )
    if not items:
        raise ValueError(f"PromptGroup {group_id} has no items")

    return group, items


def _build_aliases_map(items: list[PromptGroupItem]) -> dict[str, int]:
    """Build alias -> position mapping for step referencing."""
    aliases: dict[str, int] = {}
    for item in items:
        aliases[f"step_{item.position}"] = item.position
        if item.alias:
            aliases[item.alias] = item.position
    return aliases


def _resolve_prompt_and_placeholders(
    prompt_store: PromptStore,
    item: PromptGroupItem,
    runtime_vars: dict[str, str],
    chain_results: dict[int, str],
    aliases: dict[str, int],
    accumulated_context: str,
    initial_input: str = "",
    step_position: int = 1,
) -> tuple[str, str]:
    """Resolve the prompt template, placeholders, and build the user message.

    Returns (system_prompt_resolved, user_message).
    """
    system_prompt, user_template = prompt_store.resolve_prompt(
        item.prompt_id, item.prompt_version
    )

    # Resolve system prompt (static placeholders only)
    system_prompt_resolved = resolve_placeholders(system_prompt)

    # Resolve user message: static + runtime + chain results
    user_message = resolve_all_placeholders(
        user_template,
        runtime_variables=runtime_vars,
        chain_results=chain_results,
        aliases=aliases,
    )

    # Build user message: combine accumulated context + template
    if accumulated_context:
        user_message = f"{accumulated_context}\n\n---\n\n{user_message}"

    # If initial_input is provided (step 1), prepend it
    if step_position == 1 and initial_input and not accumulated_context:
        user_message = f"{initial_input}\n\n---\n\n{user_message}"

    return system_prompt_resolved, user_message


def _call_llm(
    session: Session,
    item: PromptGroupItem,
    user_message: str,
    system_prompt: str,
    media_file: bytes | None = None,
    media_content_type: str | None = None,
) -> tuple[str, bool]:
    """Call the LLM with the resolved prompts. Returns (response, was_cached).

    When media_file is provided, the LLM is called with multimodal content
    (image or audio) so it can extract information directly from the media
    and then use tools to look up guest data.
    """
    from app.models import PromptVersion as PV
    from app.services.llm import get_llm_config_by_model_id

    pv = session.query(PV).filter(
        PV.prompt_id == item.prompt_id,
        PV.version == item.prompt_version,
    ).first()
    model_id_val = pv.model_id if pv else None

    client, model_name = get_llm_config_by_model_id(model_id_val)

    # If no media, use the simple cached text path
    if not media_file:
        from app.services.response_cache import call_llm_with_db_tools_with_cache_flag
        llm_response, was_cached = call_llm_with_db_tools_with_cache_flag(
            user_message,
            system_prompt=system_prompt,
        )
        return llm_response, was_cached

    # --- Multimodal LLM call with tool calling ---
    import base64

    b64_data = base64.b64encode(media_file).decode("ascii")
    is_image = media_content_type and "image" in media_content_type
    is_audio = media_content_type and "audio" in media_content_type

    # Build multimodal user content
    content_parts: list[dict[str, Any]] = []
    if is_image:
        content_parts.append({
            "type": "image_url",
            "image_url": {"url": f"data:{media_content_type};base64,{b64_data}"},
        })
    elif is_audio:
        content_parts.append({
            "type": "input_audio",
            "input_audio": {
                "data": b64_data,
                "format": media_content_type.split("/")[-1].split(";")[0] if media_content_type else "webm",
            },
        })
    content_parts.append({"type": "text", "text": user_message})

    from app.services.tool_calling import _run_tool_calling_loop

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": content_parts},
    ]

    llm_response = _run_tool_calling_loop(client, model_name, messages)
    return llm_response, False


def _build_step_result(
    item: PromptGroupItem,
    system_prompt: str | None,
    user_message: str | None,
    response: str | None,
    cached: bool,
    error: str | None,
) -> dict[str, Any]:
    """Build a step result dictionary."""
    return {
        "position": item.position,
        "prompt_id": item.prompt_id,
        "prompt_version": item.prompt_version,
        "alias": item.alias,
        "system_prompt": system_prompt,
        "user_message": user_message,
        "response": response,
        "cached": cached,
        "error": error,
    }


def _execute_single_step(
    session: Session,
    prompt_store: PromptStore,
    item: PromptGroupItem,
    runtime_vars: dict[str, str],
    chain_results: dict[int, str],
    aliases: dict[str, int],
    accumulated_context: str,
    initial_input: str = "",
    media_file: bytes | None = None,
    media_content_type: str | None = None,
) -> tuple[dict[str, Any], str, str]:
    """Execute a single chain step and return (step_result, llm_response, new_context).

    This is the core shared logic between execute_chain() and execute_chain_step().
    """
    try:
        system_prompt, user_message = _resolve_prompt_and_placeholders(
            prompt_store, item, runtime_vars, chain_results, aliases,
            accumulated_context, initial_input, item.position,
        )

        llm_response, was_cached = _call_llm(
            session, item, user_message, system_prompt,
            media_file=media_file,
            media_content_type=media_content_type,
        )

        step_result = _build_step_result(
            item, system_prompt, user_message, llm_response, was_cached, None
        )
        return step_result, llm_response, llm_response

    except Exception as step_err:
        logger.error(
            "Error executing step %s (%s:v%s): %s",
            item.position, item.prompt_id, item.prompt_version, step_err, exc_info=True,
        )
        error_msg = f"[ERROR in step {item.position}]: {step_err}"
        step_result = _build_step_result(
            item, None, None, None, False, str(step_err)
        )
        return step_result, error_msg, error_msg


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def execute_chain(
    group_id: int,
    initial_input: str = "",
    scheduled: bool = False,
    db: Session | None = None,
    page_mode: bool = False,
    user_inputs: dict[int, dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Execute all prompts in a group sequentially.

    Each prompt's LLM output is fed as context to the next prompt in the chain.
    In page_mode, user_inputs provide template variables for the first step(s).

    Args:
        group_id: ID of the PromptGroup to execute.
        initial_input: Optional initial text passed to the first prompt's user message.
        scheduled: Whether this execution was triggered by the scheduler.
        db: Optional existing database session. If None, a new session is created.
        page_mode: If True, treat first step as user-input step (uses user_inputs as template vars).
        user_inputs: {step_position: {field: value}} mapping for page mode execution.

    Returns:
        Dictionary with execution details including per-step results.

    Raises:
        ValueError: If the group doesn't exist or has no items.
    """
    session_manager = db if db is not None else SessionLocal()
    should_close = db is None

    try:
        if should_close:
            session_manager.__enter__()

        group, items = _load_group_and_items(session_manager, group_id)
        aliases = _build_aliases_map(items)

        # Create result record
        result_record = PromptGroupResult(
            group_id=group_id,
            scheduled=scheduled,
            status="running",
        )
        session_manager.add(result_record)
        session_manager.commit()
        session_manager.refresh(result_record)

        chain_steps: list[dict[str, Any]] = []
        chain_results: dict[int, str] = {}
        accumulated_context = initial_input

        prompt_store = PromptStore()

        for item in items:
            # Determine runtime variables for this step
            runtime_vars: dict[str, str] = {}
            if page_mode and user_inputs and item.position in user_inputs:
                runtime_vars = user_inputs[item.position]

            step_result, response, new_context = _execute_single_step(
                session_manager, prompt_store, item,
                runtime_vars, chain_results, aliases,
                accumulated_context, initial_input,
            )

            chain_results[item.position] = response
            chain_steps.append(step_result)
            accumulated_context = new_context

        # Build final result payload
        success = all(step["error"] is None for step in chain_steps)
        chain_result = {
            "group_id": group_id,
            "group_name": group.name,
            "executed_at": datetime.now(timezone.utc).isoformat(),
            "scheduled": scheduled,
            "success": success,
            "steps_count": len(chain_steps),
            "steps": chain_steps,
            "final_output": chain_steps[-1]["response"] if chain_steps else None,
        }

        # Save to file
        result_file_path = _save_result_to_file(group_id, chain_result)

        # Update result record
        result_record.status = "success" if success else "failed"
        result_record.result_file = result_file_path
        if not success:
            errors = [step["error"] for step in chain_steps if step["error"]]
            result_record.error_message = "; ".join(errors)
        session_manager.commit()

        chain_result["result_file"] = result_file_path
        chain_result["result_id"] = result_record.result_id

        return chain_result

    finally:
        if should_close:
            session_manager.__exit__(*sys.exc_info())


def execute_chain_step(
    group_id: int,
    step_position: int,
    inputs: dict[str, str] | None = None,
    initial_input: str = "",
    accumulated_context: str = "",
    db: Session | None = None,
    media_file: bytes | None = None,
    media_content_type: str | None = None,
) -> dict[str, Any]:
    """Execute a single step in a prompt chain.

    This is used for page-mode chain execution where each step is called independently.
    The first step receives user_inputs as template variables.
    Subsequent steps receive the accumulated context from previous steps.
    Optionally accepts a media file (image/audio) for multimodal LLM processing.

    Args:
        group_id: ID of the PromptGroup.
        step_position: The 1-based position of the step to execute.
        inputs: User-provided inputs for this step.
        initial_input: Raw text passed to the first step before template resolution.
        accumulated_context: Context accumulated from previous steps.
        db: Optional existing database session.
        media_file: Optional raw bytes of an image or audio file for multimodal input.
        media_content_type: MIME type of the media file (e.g., "image/png", "audio/webm").

    Returns:
        Dictionary with step execution details.

    Raises:
        ValueError: If the group, step, or prompt doesn't exist.
    """
    session_manager = db if db is not None else SessionLocal()
    should_close = db is None

    try:
        if should_close:
            session_manager.__enter__()

        group, items = _load_group_and_items(session_manager, group_id)

        # Find the target step
        target_item = None
        for item in items:
            if item.position == step_position:
                target_item = item
                break

        if not target_item:
            raise ValueError(
                f"Step position {step_position} not found in group {group_id} "
                f"(valid positions: {[item.position for item in items]})"
            )

        aliases = _build_aliases_map(items)

        # Load previous step results for chain result resolution
        prev_chain_results: dict[int, str] = {}
        if step_position > 1 and accumulated_context:
            prev_chain_results[step_position - 1] = accumulated_context

        # Determine runtime variables
        runtime_vars: dict[str, str] = inputs or {}

        prompt_store = PromptStore()

        step_result, response, _ = _execute_single_step(
            session_manager, prompt_store, target_item,
            runtime_vars, prev_chain_results, aliases,
            accumulated_context, initial_input,
            media_file=media_file,
            media_content_type=media_content_type,
        )

        # Convert batch-format result to step-format
        return {
            "position": step_position,
            "prompt_id": step_result["prompt_id"],
            "prompt_version": step_result["prompt_version"],
            "alias": step_result["alias"],
            "system_prompt": step_result["system_prompt"],
            "user_message": step_result["user_message"],
            "response": step_result["response"],
            "cached": step_result["cached"],
            "error": step_result["error"],
            "status": "success" if step_result["error"] is None else "failed",
        }

    except Exception as e:
        logger.error("Error executing chain step %d (group %d): %s", step_position, group_id, e, exc_info=True)
        return {
            "position": step_position,
            "prompt_id": "",
            "prompt_version": 0,
            "alias": None,
            "system_prompt": None,
            "user_message": None,
            "response": None,
            "cached": False,
            "error": str(e),
            "status": "failed",
        }
    finally:
        if should_close:
            session_manager.__exit__(*sys.exc_info())