from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

from app.utils.message_bus import get_message_bus
from app.utils.message_schemas import AgentMessage, AgentEvent, FipaAclEnvelope, FipaPerformative
import os


class BaseAgent(ABC):
    def __init__(self, name: str, role: str, purpose: str) -> None:
        self._name = name
        self._role = role
        self._purpose = purpose
        self._running = False

    @property
    def name(self) -> str:
        return self._name

    @property
    def role(self) -> str:
        return self._role

    @property
    def purpose(self) -> str:
        return self._purpose

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._on_start()

    def stop(self) -> None:
        if not self._running:
            return
        self._on_stop()
        self._running = False

    @abstractmethod
    def subscribe_topics(self) -> Dict[str, str]:
        """Return mapping of topic -> handler method name for bus subscription."""

    def _on_start(self) -> None:
        bus = get_message_bus()
        for topic, handler_name in self.subscribe_topics().items():
            handler = getattr(self, handler_name)
            bus.subscribe(topic, lambda event, h=handler: h(event))

    def _on_stop(self) -> None:
        # In-memory bus doesn't support unsubscription; noop for now
        pass

    # Public send API (encapsulates bus & schema details)
    def send(self, recipients: list[str], topic: str, content: str, performative: Optional[FipaPerformative] = None, conversation_id: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> None:
        # Enforce performative for agent topics
        if topic.startswith("agents.") and not performative:
            raise ValueError("performative is required for agent topics")
        metadata = metadata or {}
        token = os.getenv("AGENT_COMM_TOKEN")
        if token:
            metadata = {**metadata, "auth_token": token}
        message = AgentMessage(
            sender=self._name,
            recipients=recipients,
            topic=topic,
            content=content,
            fipa=FipaAclEnvelope(performative=performative, conversation_id=conversation_id) if performative else None,
            metadata=metadata or {},
        )
        get_message_bus().publish(AgentEvent(topic=topic, payload={"message": message.model_dump()}))

    # Default message handler signature (agents override concrete handlers)
    def handle_message(self, event: AgentEvent) -> None:
        pass


