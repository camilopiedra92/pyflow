from __future__ import annotations

from pyflow.core.models import TriggerDef


class WebhookTrigger:
    def __init__(self, trigger_def: TriggerDef) -> None:
        self.path: str = trigger_def.config.get("path", "/")
