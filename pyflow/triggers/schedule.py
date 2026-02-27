from __future__ import annotations

from typing import Callable

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from pyflow.core.models import TriggerDef


class ScheduleTrigger:
    def __init__(self, trigger_def: TriggerDef) -> None:
        self.cron: str | None = trigger_def.config.get("cron")
        self.interval_seconds: int | None = trigger_def.config.get("interval_seconds")
        if not self.cron and not self.interval_seconds:
            raise ValueError("Schedule trigger requires 'cron' or 'interval_seconds'")

    def register(self, scheduler: AsyncIOScheduler, callback: Callable) -> None:
        if self.cron:
            parts = self.cron.split()
            scheduler.add_job(
                callback,
                CronTrigger(
                    minute=parts[0],
                    hour=parts[1],
                    day=parts[2],
                    month=parts[3],
                    day_of_week=parts[4],
                ),
            )
        else:
            scheduler.add_job(
                callback,
                IntervalTrigger(seconds=self.interval_seconds),
            )
