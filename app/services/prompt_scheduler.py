#!/usr/bin/env python3
"""
Prompt group scheduler service.

Uses APScheduler to trigger prompt chain executions at scheduled times.
Persisted schedules are stored in the PromptGroupSchedule database table.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import select

from app.db import SessionLocal
from app.models import PromptGroup, PromptGroupSchedule
from app.services.prompt_chain import execute_chain

logger = logging.getLogger(__name__)

# JSON file for schedule recovery (survives process restarts)
_SCHEDULE_STATE_FILE = Path("data/scheduler_state.json")


class PromptScheduler:
    """Background scheduler for prompt group chain executions."""

    _instance: "PromptScheduler | None" = None

    def __init__(self):
        self.scheduler = BackgroundScheduler(daemon=True)
        self._loaded = False

    @classmethod
    def get(cls) -> "PromptScheduler":
        """Singleton accessor."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the scheduler and recover persisted schedules."""
        if self.scheduler.running:
            logger.warning("PromptScheduler already running")
            return

        self._recover_schedules()
        self.scheduler.start()
        self._loaded = True
        logger.info("PromptScheduler started")

    def shutdown(self) -> None:
        """Shutdown the scheduler gracefully."""
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            self._loaded = False
            logger.info("PromptScheduler shut down")

    # ------------------------------------------------------------------
    # Scheduling
    # ------------------------------------------------------------------

    def schedule_execution(self, schedule_id: int, group_id: int, run_at: datetime, schedule_type: str = "daily") -> str:
        """Add a job for a prompt group chain execution.

        Args:
            schedule_id: Database schedule record ID.
            group_id: Prompt group to execute.
            run_at: First execution time.
            schedule_type: "none" (one-shot), "daily", or "weekly".

        Returns the job_id assigned by APScheduler.
        """
        if schedule_type == "none":
            trigger = DateTrigger(run_date=run_at)
        elif schedule_type == "weekly":
            trigger = IntervalTrigger(weeks=1, start_date=run_at)
        else:
            # default to daily
            trigger = IntervalTrigger(days=1, start_date=run_at)

        job = self.scheduler.add_job(
            self._execute_group,
            trigger=trigger,
            args=[group_id, schedule_id],
            id=f"prompt_group_{schedule_id}",
            replace_existing=True,
        )
        self._persist_state()
        logger.info("Scheduled group %d (schedule %d) type=%s at %s → job %s", group_id, schedule_id, schedule_type, run_at, job.id)
        return job.id

    def cancel_schedule(self, schedule_id: int) -> bool:
        """Cancel a scheduled job by its database schedule_id."""
        job_id = f"prompt_group_{schedule_id}"
        try:
            self.scheduler.remove_job(job_id)
            self._persist_state()
            logger.info("Cancelled schedule %d (job %s)", schedule_id, job_id)
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _execute_group(group_id: int, schedule_id: int) -> None:
        """Callback invoked by APScheduler to run a prompt chain.
        
        Checks if the group is still active before executing. Skips if disabled.
        """
        logger.info("Scheduled execution: group %d (schedule %d)", group_id, schedule_id)
        
        # Check if group is still active
        with SessionLocal() as db:
            group = db.query(PromptGroup).filter(PromptGroup.group_id == group_id).first()
            if not group or not group.is_active:
                logger.warning(
                    "Skipping scheduled execution: group %d is disabled or not found",
                    group_id,
                )
                return

        try:
            result = execute_chain(group_id, scheduled=True)
            logger.info(
                "Scheduled execution completed: group %d — status=%s, result_id=%s",
                group_id,
                "success" if result.get("success") else "failed",
                result.get("result_id"),
            )
        except Exception:
            logger.error("Scheduled execution failed for group %d", group_id, exc_info=True)

    def _persist_state(self) -> None:
        """Save active job info to JSON for recovery after restart."""
        jobs_info = []
        for job in self.scheduler.get_jobs():
            jobs_info.append({
                "job_id": job.id,
                "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
            })
        _SCHEDULE_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        _SCHEDULE_STATE_FILE.write_text(json.dumps(jobs_info, indent=2), encoding="utf-8")

    def _recover_schedules(self) -> None:
        """On startup: reload pending schedules from the database.

        Re-schedules any active PromptGroupSchedule records whose run_at
        is in the future, but only for groups where is_active == True.
        """
        with SessionLocal() as db:
            # Join with PromptGroup to filter out disabled groups
            schedules = db.execute(
                select(PromptGroupSchedule)
                .join(PromptGroup, PromptGroupSchedule.group_id == PromptGroup.group_id)
                .where(
                    PromptGroupSchedule.active == True,  # noqa: E712
                    PromptGroupSchedule.run_at > datetime.now(timezone.utc),
                    PromptGroup.is_active == True,  # noqa: E712
                )
            ).scalars().all()

        for sched in schedules:
            try:
                # Parse run_at if it's a string (shouldn't happen but be defensive)
                run_at = sched.run_at
                if isinstance(run_at, str):
                    run_at = datetime.fromisoformat(run_at)
                if run_at.tzinfo is None:
                    run_at = run_at.replace(tzinfo=timezone.utc)

                schedule_type = getattr(sched, 'schedule_type', None) or "daily"
                self.schedule_execution(sched.schedule_id, sched.group_id, run_at, schedule_type)
            except Exception:
                logger.error(
                    "Failed to recover schedule %d for group %d",
                    sched.schedule_id,
                    sched.group_id,
                    exc_info=True,
                )