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

        # --- Load group + items ---
        group = session_manager.query(PromptGroup).filter(PromptGroup.group_id == group_id).first()
        if not group:
            raise ValueError(f"PromptGroup {group_id} not found")

        items = (
            session_manager.query(PromptGroupItem)
            .filter(PromptGroupItem.group_id == group_id)
            .order_by(PromptGroupItem.position)
            .all()
        )
        if not items:
            raise ValueError(f"PromptGroup {group_id} has no items")

        # --- Build alias map: alias_name -> step_position ---
        # Also maps "step_{N}" -> N for built-in step references
        aliases: dict[str, int] = {}
        for item in items:
            aliases[f"step_{item.position}"] = item.position
            if item.alias:
                aliases[item.alias] = item.position

        # --- Create result record ---
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
            try:
                # Resolve prompt template
                system_prompt, user_template = prompt_store.resolve_prompt(
                    item.prompt_id, item.prompt_version
                )

                # Resolve system prompt (static placeholders only)
                system_prompt_resolved = _resolve_static(system_prompt)

                # --- Determine runtime variables for this step ---
                runtime_vars: dict[str, str] = {}
                if page_mode and user_inputs and item.position in user_inputs:
                    runtime_vars = user_inputs[item.position]

                # --- Resolve user message: static + runtime + chain results ---
                user_message = _resolve_all_with_chain(
                    user_template,
                    runtime_vars=runtime_vars,
                    chain_results=chain_results,
                    aliases=aliases,
                )

                # Build user message: combine accumulated context + template
                if accumulated_context:
                    user_message = f"{accumulated_context}\n\n---\n\n{user_message}"
                else:
                    user_message = user_message

                # Resolve model_id for this prompt version
                from app.models import PromptVersion as PV
                pv = session_manager.query(PV).filter(
                    PV.prompt_id == item.prompt_id,
                    PV.version == item.prompt_version,
                ).first()
                model_id_val = pv.model_id if pv else None

                # Call LLM
                from app.services.llm import get_llm_config_by_model_id
                from app.services.response_cache import call_llm_with_db_tools_with_cache_flag

                client, model_name = get_llm_config_by_model_id(model_id_val)
                llm_response, was_cached = call_llm_with_db_tools_with_cache_flag(
                    user_message,
                    system_prompt=system_prompt_resolved,
                )

                # Store in chain_results for subsequent steps
                chain_results[item.position] = llm_response

                chain_steps.append({
                    "position": item.position,
                    "prompt_id": item.prompt_id,
                    "prompt_version": item.prompt_version,
                    "alias": item.alias,
                    "system_prompt": system_prompt_resolved,
                    "user_message": user_message,
                    "response": llm_response,
                    "cached": was_cached,
                    "error": None,
                })

                # Feed response into next prompt's context
                accumulated_context = llm_response

            except Exception as step_err:
                logger.error("Error executing step %s (%s:v%s): %s", item.position, item.prompt_id, item.prompt_version, step_err, exc_info=True)
                # Store error in chain_results for subsequent steps
                chain_results[item.position] = f"[ERROR in step {item.position}]: {step_err}"
                chain_steps.append({
                    "position": item.position,
                    "prompt_id": item.prompt_id,
                    "prompt_version": item.prompt_version,
                    "alias": item.alias,
                    "system_prompt": None,
                    "user_message": None,
                    "response": None,
                    "cached": False,
                    "error": str(step_err),
                })
                # Continue chain even if a step fails
                accumulated_context = f"[ERROR in step {item.position}]: {step_err}"

        # --- Build final result payload ---
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


# ---------------------------------------------------------------------------
# Helper functions for placeholder resolution
# ---------------------------------------------------------------------------

def _resolve_static(text: str) -> str:
    """Resolve static placeholders (DATABASE_TABLES, GUEST_INFORMATION, etc.)."""
    from app.services.placeholders import resolve_placeholders
    return resolve_placeholders(text)


def execute_chain_step(
    group_id: int,
    step_position: int,
    inputs: dict[str, str] | None = None,
    initial_input: str = "",
    accumulated_context: str = "",
    db: Session | None = None,
) -> dict[str, Any]:
    """Execute a single step in a prompt chain.

    This is used for page-mode chain execution where each step is called independently.
    The first step receives user_inputs as template variables.
    Subsequent steps receive the accumulated context from previous steps.

    Args:
        group_id: ID of the PromptGroup.
        step_position: The 1-based position of the step to execute.
        inputs: User-provided inputs for this step.
        initial_input: Raw text passed to the first step before template resolution.
        accumulated_context: Context accumulated from previous steps.
        db: Optional existing database session.

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

        # --- Load group ---
        group = session_manager.query(PromptGroup).filter(PromptGroup.group_id == group_id).first()
        if not group:
            raise ValueError(f"PromptGroup {group_id} not found")

        # --- Find the target step ---
        items = (
            session_manager.query(PromptGroupItem)
            .filter(PromptGroupItem.group_id == group_id)
            .order_by(PromptGroupItem.position)
            .all()
        )
        if not items:
            raise ValueError(f"PromptGroup {group_id} has no items")

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

        # --- Build alias map ---
        aliases: dict[str, int] = {}
        for item in items:
            aliases[f"step_{item.position}"] = item.position
            if item.alias:
                aliases[item.alias] = item.position

        # --- Also load previous step results for chain result resolution ---
        # We need the previous step's response for {step_N} and alias references
        prev_chain_results: dict[int, str] = {}
        if step_position > 1 and accumulated_context:
            prev_chain_results[step_position - 1] = accumulated_context

        # --- Load previous step's response if context was passed ---
        if accumulated_context:
            prev_chain_results[step_position - 1] = accumulated_context

        prompt_store = PromptStore()

        # Resolve prompt template
        system_prompt, user_template = prompt_store.resolve_prompt(
            target_item.prompt_id, target_item.prompt_version
        )

        # Resolve system prompt (static placeholders only)
        system_prompt_resolved = _resolve_static(system_prompt)

        # --- Determine runtime variables for this step ---
        runtime_vars: dict[str, str] = {}
        if inputs:
            runtime_vars = inputs

        # --- Resolve user message: static + runtime + chain results ---
        user_message = _resolve_all_with_chain(
            user_template,
            runtime_vars=runtime_vars,
            chain_results=prev_chain_results,
            aliases=aliases,
        )

        # Build user message: combine accumulated context + template
        if accumulated_context:
            user_message = f"{accumulated_context}\n\n---\n\n{user_message}"
        else:
            user_message = user_message

        # --- If initial_input is provided (step 1), prepend it ---
        if step_position == 1 and initial_input and not accumulated_context:
            user_message = f"{initial_input}\n\n---\n\n{user_message}"

        # Resolve model_id for this prompt version
        from app.models import PromptVersion as PV
        pv = session_manager.query(PV).filter(
            PV.prompt_id == target_item.prompt_id,
            PV.version == target_item.prompt_version,
        ).first()
        model_id_val = pv.model_id if pv else None

        # Call LLM
        from app.services.llm import get_llm_config_by_model_id
        from app.services.response_cache import call_llm_with_db_tools_with_cache_flag

        client, model_name = get_llm_config_by_model_id(model_id_val)
        llm_response, was_cached = call_llm_with_db_tools_with_cache_flag(
            user_message,
            system_prompt=system_prompt_resolved,
        )

        return {
            "step": step_position,
            "prompt_id": target_item.prompt_id,
            "prompt_version": target_item.prompt_version,
            "alias": target_item.alias,
            "system_prompt": system_prompt_resolved,
            "user_message": user_message,
            "response": llm_response,
            "cached": was_cached,
            "error": None,
            "status": "success",
        }

    except Exception as e:
        logger.error("Error executing chain step %d (group %d): %s", step_position, group_id, e, exc_info=True)
        return {
            "step": step_position,
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


def _resolve_all_with_chain(
    text: str,
    runtime_vars: dict[str, str],
    chain_results: dict[int, str],
    aliases: dict[str, int],
) -> str:
    """Resolve all placeholder types: static + runtime + chain results."""
    from app.services.placeholders import resolve_all_placeholders
    return resolve_all_placeholders(
        text,
        runtime_variables=runtime_vars,
        chain_results=chain_results,
        aliases=aliases,
    )
