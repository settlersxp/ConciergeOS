#!/usr/bin/env python3
"""
API routes for Prompt Group CRUD, execution, and scheduling.
"""

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import and_
from sqlalchemy.orm import Session, joinedload

from app.db import get_db
from app.models import (
    PromptGroup,
    PromptGroupItem,
    PromptGroupSchedule,
    PromptGroupResult,
)
from app.schemas import (
    ChainExecutionRequest,
    CreateGroupRequest,
    PromptGroupItemSchema,
    PromptGroupResultSchema,
    PromptGroupSchema,
    PromptGroupScheduleCreate,
    PromptGroupScheduleSchema,
    UpdateGroupRequest,
)
from app.services.prompt_chain import execute_chain, execute_chain_step
from app.services.prompt_scheduler import PromptScheduler

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/prompt-groups", tags=["prompt-groups"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _group_with_relations(db: Session) -> Any:
    """Return a PromptGroup query with items, schedules, and results joined."""
    return db.query(PromptGroup).options(
        joinedload(PromptGroup.items),
        joinedload(PromptGroup.schedules),
        joinedload(PromptGroup.results),
    )


def _require_group(db: Session, group_id: int) -> PromptGroup:
    """Fetch a PromptGroup by ID or raise 404."""
    group = db.query(PromptGroup).filter(PromptGroup.group_id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail=f"PromptGroup {group_id} not found")
    return group


def _require_group_with_relations(db: Session, group_id: int) -> PromptGroup:
    """Fetch a PromptGroup with all relations by ID or raise 404."""
    group = _group_with_relations(db).filter(PromptGroup.group_id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail=f"PromptGroup {group_id} not found")
    return group


def _cancel_active_schedules(db: Session, group_id: int, mark_inactive: bool = False) -> int:
    """Cancel all active APScheduler jobs for a group and optionally mark them inactive.

    Returns the number of schedules cancelled.
    """
    scheduler = PromptScheduler.get()
    schedules = (
        db.query(PromptGroupSchedule)
        .filter(
            and_(
                PromptGroupSchedule.group_id == group_id,
                PromptGroupSchedule.active == True,  # noqa: E712
            )
        )
        .all()
    )
    for sched in schedules:
        scheduler.cancel_schedule(sched.schedule_id)
        if mark_inactive:
            sched.active = False
    return len(schedules)


def _safe_chain_execution(group_id: int, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """Execute a chain function with standardized error handling."""
    try:
        return fn(*args, **kwargs)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("Chain execution failed for group %d: %s", group_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


def _group_to_schema(group: PromptGroup) -> PromptGroupSchema:
    """Convert a PromptGroup ORM object to the response schema."""
    return PromptGroupSchema(
        group_id=group.group_id,
        name=group.name,
        description=group.description,
        is_active=group.is_active,
        is_chain_page=group.is_chain_page,
        page_route=group.page_route,
        created_at=group.created_at.isoformat() if group.created_at else "",
        updated_at=group.updated_at.isoformat() if group.updated_at else "",
        items=[
            PromptGroupItemSchema(
                item_id=item.item_id,
                group_id=item.group_id,
                position=item.position,
                prompt_id=item.prompt_id,
                prompt_version=item.prompt_version,
                alias=item.alias,
                is_input_step=item.is_input_step,
                is_active=item.is_active,
            )
            for item in group.items
        ],
        schedules=[
            PromptGroupScheduleSchema(
                schedule_id=s.schedule_id,
                group_id=s.group_id,
                run_at=s.run_at.isoformat() if s.run_at else "",
                schedule_type=getattr(s, 'schedule_type', None) or "daily",
                active=s.active,
                created_at=s.created_at.isoformat() if s.created_at else "",
            )
            for s in group.schedules
        ],
        results=[
            PromptGroupResultSchema(
                result_id=r.result_id,
                group_id=r.group_id,
                executed_at=r.executed_at.isoformat() if r.executed_at else "",
                scheduled=r.scheduled,
                result_file=r.result_file,
                status=r.status,
                error_message=r.error_message,
            )
            for r in group.results
        ],
    )


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

@router.get("")
def list_groups(db: Session = Depends(get_db)):
    """List all prompt groups."""
    groups = _group_with_relations(db).order_by(PromptGroup.group_id.desc()).all()
    return [_group_to_schema(g) for g in groups]


@router.post("")
def create_group(req: CreateGroupRequest, db: Session = Depends(get_db)):
    """Create a new prompt group with optional items."""
    new_group = PromptGroup(
        name=req.name,
        description=req.description,
    )
    db.add(new_group)
    db.commit()
    db.refresh(new_group)

    created_id = new_group.group_id

    if req.items:
        for item_req in req.items:
            db.add(PromptGroupItem(
                group_id=created_id,
                position=item_req.position,
                prompt_id=item_req.prompt_id,
                prompt_version=item_req.prompt_version,
                alias=item_req.alias,
                is_input_step=item_req.is_input_step,
            ))
        db.commit()

    group = _require_group_with_relations(db, created_id)
    return _group_to_schema(group)


@router.get("/{group_id}")
def get_group(group_id: int, db: Session = Depends(get_db)):
    """Get a single prompt group with all details."""
    group = _require_group_with_relations(db, group_id)
    return _group_to_schema(group)


@router.put("/{group_id}")
def update_group(group_id: int, req: UpdateGroupRequest, db: Session = Depends(get_db)):
    """Update group name, description, and/or items."""
    group = _require_group(db, group_id)

    if req.name is not None:
        group.name = req.name
    if req.description is not None:
        group.description = req.description
    if req.is_active is not None:
        group.is_active = req.is_active

    if req.is_chain_page is not None:
        group.is_chain_page = req.is_chain_page
    if req.page_route is not None:
        group.page_route = req.page_route

    if req.items is not None:
        # Replace all items
        db.query(PromptGroupItem).filter(PromptGroupItem.group_id == group_id).delete()
        for item_req in req.items:
            db.add(PromptGroupItem(
                group_id=group_id,
                position=item_req.position,
                prompt_id=item_req.prompt_id,
                prompt_version=item_req.prompt_version,
                alias=item_req.alias,
                is_input_step=item_req.is_input_step,
            ))

    db.commit()

    refreshed = _require_group_with_relations(db, group_id)
    return _group_to_schema(refreshed)


@router.delete("/{group_id}")
def delete_group(group_id: int, db: Session = Depends(get_db)):
    """Delete a prompt group and all related data."""
    group = _require_group(db, group_id)

    # Cancel all active scheduler jobs for this group before deleting
    _cancel_active_schedules(db, group_id)

    db.delete(group)
    db.commit()
    return {"ok": True, "group_id": group_id}


# ---------------------------------------------------------------------------
# Toggle active state for group
# ---------------------------------------------------------------------------

@router.patch("/{group_id}/toggle")
def toggle_group(group_id: int, db: Session = Depends(get_db)):
    """Toggle the active state of a prompt group."""
    group = _require_group(db, group_id)

    group.is_active = not group.is_active
    db.commit()

    # If disabling, cancel all active APScheduler jobs for this group
    if not group.is_active:
        _cancel_active_schedules(db, group_id, mark_inactive=True)
        db.commit()

    refreshed = _require_group_with_relations(db, group_id)
    return _group_to_schema(refreshed)


# ---------------------------------------------------------------------------
# Toggle active state for individual item
# ---------------------------------------------------------------------------

@router.patch("/{group_id}/items/{item_id}/toggle")
def toggle_item(group_id: int, item_id: int, db: Session = Depends(get_db)):
    """Toggle the active state of a single prompt group item."""
    item = db.query(PromptGroupItem).filter(
        and_(
            PromptGroupItem.item_id == item_id,
            PromptGroupItem.group_id == group_id,
        )
    ).first()

    if not item:
        raise HTTPException(status_code=404, detail=f"PromptGroupItem {item_id} not found in group {group_id}")

    item.is_active = not item.is_active
    db.commit()
    db.refresh(item)
    return {"item_id": item.item_id, "is_active": item.is_active}


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------

@router.post("/{group_id}/execute")
def execute_group(group_id: int, initial_input: str = "", db: Session = Depends(get_db)):
    """Execute the prompt chain now (Recalculate Now)."""
    return _safe_chain_execution(
        group_id,
        execute_chain,
        group_id,
        initial_input=initial_input,
        scheduled=False,
    )


@router.post("/{group_id}/execute-chain")
def execute_chain_page(group_id: int, req: ChainExecutionRequest, db: Session = Depends(get_db)):
    """Execute chain with user inputs (page mode).

    The first step receives user_inputs as template variables.
    Subsequent steps receive the output of their predecessor via chain results.
    """
    return _safe_chain_execution(
        group_id,
        execute_chain,
        group_id,
        initial_input=req.initial_input,
        page_mode=True,
        user_inputs=req.inputs,
    )


@router.post("/{group_id}/execute-chain-step")
async def execute_chain_step_route(
    group_id: int,
    position: int = Form(...),
    initial_input: str = Form(""),
    accumulated_context: str = Form(""),
    inputs_json: str = Form("{}"),
    file: UploadFile | None = File(None),
    db: Session = Depends(get_db),
):
    """Execute a single step in a prompt chain (page mode, step-by-step).

    This endpoint accepts multipart/form-data to support optional file uploads
    (images/audio) for multimodal LLM processing.

    Form fields:
    - position: Step position (1-based)
    - initial_input: Raw text for the first step
    - accumulated_context: Context from previous steps
    - inputs_json: JSON string of {field: value} inputs
    - file: Optional image or audio file for multimodal input
    """
    import json as _json

    try:
        inputs = _json.loads(inputs_json) if inputs_json else {}
    except Exception:
        inputs = {}

    # Read optional media file
    media_file: bytes | None = None
    media_content_type: str | None = None
    if file and file.file:
        media_file = await file.read()
        media_content_type = file.content_type

    return _safe_chain_execution(
        group_id,
        execute_chain_step,
        group_id,
        step_position=position,
        inputs=inputs,
        initial_input=initial_input,
        accumulated_context=accumulated_context,
        media_file=media_file,
        media_content_type=media_content_type,
    )


# ---------------------------------------------------------------------------
# Scheduling
# ---------------------------------------------------------------------------

@router.post("/{group_id}/schedule")
def schedule_group(group_id: int, req: PromptGroupScheduleCreate, db: Session = Depends(get_db)):
    """Schedule a prompt chain execution at a specific time."""
    group = _require_group(db, group_id)

    if not group.is_active:
        raise HTTPException(status_code=400, detail="Cannot schedule a disabled group. Enable the group first.")

    # Parse the ISO 8601 datetime
    try:
        run_at = datetime.fromisoformat(req.run_at)
        if run_at.tzinfo is None:
            run_at = run_at.replace(tzinfo=timezone.utc)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid datetime format. Use ISO 8601.")

    schedule_type = req.schedule_type if req.schedule_type else "daily"

    schedule = PromptGroupSchedule(
        group_id=group_id,
        run_at=run_at,
        schedule_type=schedule_type,
        active=True,
    )
    db.add(schedule)
    db.commit()
    db.refresh(schedule)

    # Add to APScheduler
    scheduler = PromptScheduler.get()
    job_id = scheduler.schedule_execution(schedule.schedule_id, group_id, run_at, schedule_type)

    return {
        "ok": True,
        "schedule_id": schedule.schedule_id,
        "group_id": group_id,
        "run_at": run_at.isoformat(),
        "job_id": job_id,
    }


@router.delete("/{group_id}/schedules/{schedule_id}")
def cancel_schedule(group_id: int, schedule_id: int, db: Session = Depends(get_db)):
    """Cancel a specific schedule for a group."""
    group = _require_group(db, group_id)

    schedule = (
        db.query(PromptGroupSchedule)
        .filter(
            and_(
                PromptGroupSchedule.schedule_id == schedule_id,
                PromptGroupSchedule.group_id == group_id,
            )
        )
        .first()
    )
    if not schedule:
        raise HTTPException(status_code=404, detail=f"Schedule {schedule_id} not found for group {group_id}")

    # Cancel in APScheduler
    scheduler = PromptScheduler.get()
    scheduler.cancel_schedule(schedule_id)

    # Mark as inactive in database
    schedule.active = False
    db.commit()

    return {"ok": True, "schedule_id": schedule_id}


@router.get("/{group_id}/results")
def get_results(group_id: int, db: Session = Depends(get_db)):
    """Get execution history for a group."""
    group = _require_group(db, group_id)

    results = (
        db.query(PromptGroupResult)
        .filter(PromptGroupResult.group_id == group_id)
        .order_by(PromptGroupResult.executed_at.desc())
        .all()
    )

    return [
        PromptGroupResultSchema(
            result_id=r.result_id,
            group_id=r.group_id,
            executed_at=r.executed_at.isoformat() if r.executed_at else "",
            scheduled=r.scheduled,
            result_file=r.result_file,
            status=r.status,
            error_message=r.error_message,
        )
        for r in results
    ]


@router.delete("/{group_id}/schedules")
def clear_schedules(group_id: int, db: Session = Depends(get_db)):
    """Clear all active schedules for a group."""
    group = _require_group(db, group_id)

    deleted = _cancel_active_schedules(db, group_id, mark_inactive=True)
    db.commit()
    return {"ok": True, "deleted": deleted}


# ---------------------------------------------------------------------------
# Result file download
# ---------------------------------------------------------------------------

@router.get("/results/{result_id}/download")
def download_result(result_id: int, db: Session = Depends(get_db)):
    """Download a result file for a specific execution result."""
    result = db.query(PromptGroupResult).filter(
        PromptGroupResult.result_id == result_id
    ).first()

    if not result:
        raise HTTPException(status_code=404, detail=f"Result {result_id} not found")

    if not result.result_file:
        raise HTTPException(status_code=404, detail="No result file available for this execution")

    # Resolve the file path relative to project root
    project_root = Path(__file__).resolve().parent.parent.parent
    file_path = project_root / result.result_file

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Result file not found on disk")

    return FileResponse(
        str(file_path),
        media_type="application/json",
        filename=file_path.name,
    )