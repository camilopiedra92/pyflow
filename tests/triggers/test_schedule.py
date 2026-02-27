import pytest
from unittest.mock import AsyncMock, MagicMock
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
