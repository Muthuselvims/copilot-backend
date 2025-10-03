from __future__ import annotations

from typing import Callable, Dict, List, DefaultDict
from collections import defaultdict
import logging

from app.utils.message_schemas import AgentEvent


EventHandler = Callable[[AgentEvent], None]


class MessageBus:
    def publish(self, event: AgentEvent) -> None:
        raise NotImplementedError

    def subscribe(self, topic: str, handler: EventHandler) -> None:
        raise NotImplementedError


class InMemoryMessageBus(MessageBus):
    def __init__(self) -> None:
        self._subscribers: DefaultDict[str, List[EventHandler]] = defaultdict(list)
        self._logger = logging.getLogger("app.utils.message_bus")
        self._validators: List[Callable[[AgentEvent], None]] = []

    def publish(self, event: AgentEvent) -> None:
        # Validate first
        for validator in list(self._validators):
            validator(event)
        handlers = list(self._subscribers.get(event.topic, []))
        for handler in handlers:
            try:
                handler(event)
            except Exception:
                self._logger.exception("Event handler failed", extra={"topic": event.topic, "event_id": event.id})
                # Dead-letter publication
                try:
                    dlq = self._subscribers.get("deadletter", [])
                    for dl_handler in list(dlq):
                        dl_handler(AgentEvent(topic="deadletter", payload={"failed_topic": event.topic, "event": event.model_dump()}))
                except Exception:
                    self._logger.exception("Dead-letter handler failed")

    def subscribe(self, topic: str, handler: EventHandler) -> None:
        self._subscribers[topic].append(handler)

    def add_validator(self, validator: Callable[[AgentEvent], None]) -> None:
        self._validators.append(validator)


_GLOBAL_BUS = InMemoryMessageBus()


def get_message_bus() -> MessageBus:
    return _GLOBAL_BUS


