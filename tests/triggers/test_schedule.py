from __future__ import annotations

import pytest
from unittest.mock import MagicMock
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from pyflow.triggers.schedule import ScheduleTrigger
from pyflow.core.models import TriggerDef


class TestScheduleTrigger:
    def test_create_from_cron(self):
        trigger_def = TriggerDef(type="schedule", config={"cron": "0 * * * *"})
        trigger = ScheduleTrigger(trigger_def)
        assert trigger.cron == "0 * * * *"

    def test_create_from_interval(self):
        trigger_def = TriggerDef(type="schedule", config={"interval_seconds": 60})
        trigger = ScheduleTrigger(trigger_def)
        assert trigger.interval_seconds == 60

    def test_requires_cron_or_interval(self):
        trigger_def = TriggerDef(type="schedule", config={})
        with pytest.raises(ValueError, match="cron.*interval"):
            ScheduleTrigger(trigger_def)

    def test_cron_validation_rejects_invalid_format(self):
        trigger_def = TriggerDef(type="schedule", config={"cron": "invalid"})
        with pytest.raises(ValueError, match="5 parts"):
            ScheduleTrigger(trigger_def)

    def test_cron_validation_rejects_too_many_parts(self):
        trigger_def = TriggerDef(type="schedule", config={"cron": "0 * * * * *"})
        with pytest.raises(ValueError, match="5 parts"):
            ScheduleTrigger(trigger_def)

    def test_register_cron_with_scheduler(self):
        trigger_def = TriggerDef(type="schedule", config={"cron": "30 2 * * 1"})
        trigger = ScheduleTrigger(trigger_def)
        mock_scheduler = MagicMock()
        mock_callback = MagicMock()
        trigger.register(mock_scheduler, mock_callback)
        mock_scheduler.add_job.assert_called_once()
        args, kwargs = mock_scheduler.add_job.call_args
        assert args[0] is mock_callback
        assert isinstance(args[1], CronTrigger)

    def test_register_interval_with_scheduler(self):
        trigger_def = TriggerDef(type="schedule", config={"interval_seconds": 120})
        trigger = ScheduleTrigger(trigger_def)
        mock_scheduler = MagicMock()
        mock_callback = MagicMock()
        trigger.register(mock_scheduler, mock_callback)
        mock_scheduler.add_job.assert_called_once()
        args, kwargs = mock_scheduler.add_job.call_args
        assert args[0] is mock_callback
        assert isinstance(args[1], IntervalTrigger)
