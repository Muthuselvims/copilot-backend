from __future__ import annotations

import logging
from typing import Dict, List

from app.agents.base_agent import BaseAgent
from app.utils.message_schemas import AgentEvent, FipaPerformative


logger = logging.getLogger("app.agents.coordinator_agent")


class CoordinatorAgent(BaseAgent):
    def __init__(self, workers: List[str]) -> None:
        super().__init__(name="CoordinatorAgent", role="coordinator", purpose="Allocate tasks to workers")
        self._workers = workers
        self._next = 0

    def subscribe_topics(self) -> Dict[str, str]:
        return {
            "agents.coordinator.task": "on_task",
            "agents.worker.response": "on_worker_response",
        }

    def on_task(self, event: AgentEvent) -> None:
        # Simple round-robin assignment
        if not self._workers:
            return
        worker = self._workers[self._next % len(self._workers)]
        self._next += 1
        payload = event.payload or {}
        message = payload.get("message") or {}
        content = message.get("content", "")
        conv_id = ((message.get("fipa") or {}).get("conversation_id"))
        self.send(
            recipients=[worker],
            topic="agents.worker.request",
            content=content,
            performative=FipaPerformative.request,
            conversation_id=conv_id,
        )

    def on_worker_response(self, event: AgentEvent) -> None:
        # For now just log; could aggregate or route to original requester
        try:
            logger.info("Coordinator received worker response", extra={"payload_keys": list((event.payload or {}).keys())})
        except Exception:
            logger.exception("Coordinator failed to process worker response")


