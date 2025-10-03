from __future__ import annotations

import logging
from typing import Dict

from app.agents.base_agent import BaseAgent
from app.utils.message_schemas import AgentEvent, FipaPerformative


logger = logging.getLogger("app.agents.example_worker_agent")


class ExampleWorkerAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__(name="WorkerAgent", role="worker", purpose="Compute KPIs and summaries")

    def subscribe_topics(self) -> Dict[str, str]:
        return {
            "agents.worker.request": "on_request",
        }

    def on_request(self, event: AgentEvent) -> None:
        try:
            payload = event.payload or {}
            message = (payload.get("message") or {})
            content = message.get("content")
            conv_id = ((message.get("fipa") or {}).get("conversation_id"))

            # Do some lightweight work
            result_text = f"Processed: {content}"

            # Reply to sender if provided
            sender = message.get("sender")
            if sender:
                self.send(
                    recipients=[sender],
                    topic="agents.worker.response",
                    content=result_text,
                    performative=FipaPerformative.inform,
                    conversation_id=conv_id,
                )
        except Exception:
            logger.exception("WorkerAgent failed to process request")


