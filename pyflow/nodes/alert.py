from __future__ import annotations

import httpx
import structlog

from pyflow.core.context import ExecutionContext
from pyflow.core.node import BaseNode
from pyflow.nodes.schemas import AlertConfig, AlertResponse

logger = structlog.get_logger()


class AlertNode(BaseNode[AlertConfig, AlertResponse]):
    node_type = "alert"
    config_model = AlertConfig
    response_model = AlertResponse

    async def execute(self, config: dict | AlertConfig, context: ExecutionContext) -> object:
        if isinstance(config, AlertConfig):
            webhook_url = config.webhook_url
            message = config.message
        else:
            webhook_url = config["webhook_url"]
            message = config["message"]

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(webhook_url, json={"text": message})
            return {"status": response.status_code, "sent": True}
        except Exception as exc:
            logger.warning("alert_send_failed", error=str(exc), webhook_url=webhook_url)
            return {"status": 0, "sent": False, "error": str(exc)}
