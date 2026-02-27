from __future__ import annotations

from pyflow.triggers.webhook import WebhookTrigger
from pyflow.core.models import TriggerDef


class TestWebhookTrigger:
    def test_init_with_path(self):
        trigger_def = TriggerDef(type="webhook", config={"path": "/my-webhook"})
        trigger = WebhookTrigger(trigger_def)
        assert trigger.path == "/my-webhook"

    def test_default_path(self):
        trigger_def = TriggerDef(type="webhook", config={})
        trigger = WebhookTrigger(trigger_def)
        assert trigger.path == "/"
