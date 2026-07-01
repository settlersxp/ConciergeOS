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
) -> dict[str, Any]:
    """Execute all prompts in a group sequentially.

    Each prompt's LLM output is fed as context to the next prompt in the chain.

    Args:
        group_id: ID of the PromptGroup to execute.
        initial_input: Optional initial text passed to the first prompt's user message.
        scheduled: Whether this execution was triggered by the scheduler.
        db: Optional existing database session. If None, a new session is created.

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
        accumulated_context = initial_input

        prompt_store = PromptStore()

        for item in items:
            try:
                # Resolve prompt template
                system_prompt, user_template = prompt_store.resolve_prompt(
                    item.prompt_id, item.prompt_version
                )

                # Build user message: combine accumulated context + template
                if accumulated_context:
                    user_message = f"{accumulated_context}\n\n---\n\n{user_template}"
                else:
                    user_message = user_template

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
                    system_prompt=system_prompt,
                )

                chain_steps.append({
                    "position": item.position,
                    "prompt_id": item.prompt_id,
                    "prompt_version": item.prompt_version,
                    "system_prompt": system_prompt,
                    "user_message": user_message,
                    "response": llm_response,
                    "cached": was_cached,
                    "error": None,
                })

                # Feed response into next prompt's context
                accumulated_context = llm_response

            except Exception as step_err:
                logger.error("Error executing step %s (%s:v%s): %s", item.position, item.prompt_id, item.prompt_version, step_err, exc_info=True)
                chain_steps.append({
                    "position": item.position,
                    "prompt_id": item.prompt_id,
                    "prompt_version": item.prompt_version,
                    "system_prompt": None,
                    "user_message": None,
                    "response": None,
                    "cached": False,
                    "error": str(step_err),
                })
                # Continue chain even if a step fails (pass empty context)
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
