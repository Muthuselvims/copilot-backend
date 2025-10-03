from __future__ import annotations

import os
from typing import Dict, Any

from app.utils.message_schemas import AgentEvent, AgentMessage, FipaAclEnvelope, FipaPerformative
from app.utils.message_bus import get_message_bus


AGENT_TOPIC_PREFIX = "agents."


def _ensure_auth(event: AgentEvent) -> None:
    token = os.getenv("AGENT_COMM_TOKEN")
    if not token:
        return  # policy disabled when no token configured
    payload = event.payload or {}
    message = payload.get("message") or {}
    metadata = message.get("metadata") or {}
    provided = metadata.get("auth_token")
    if provided != token:
        raise PermissionError("Unauthorized event: invalid or missing auth token")


def _ensure_fipa_for_agent_topics(event: AgentEvent) -> None:
    if not event.topic.startswith(AGENT_TOPIC_PREFIX):
        return
    payload = event.payload or {}
    message = payload.get("message") or {}
    fipa = message.get("fipa") or {}
    performative = fipa.get("performative")
    if not performative:
        raise ValueError("FIPA performative required for agent topics")


def register_default_policy() -> None:
    bus = get_message_bus()
    # The in-memory bus exposes add_validator
    try:
        bus.add_validator(_ensure_auth)  # type: ignore[attr-defined]
        bus.add_validator(_ensure_fipa_for_agent_topics)  # type: ignore[attr-defined]
        bus.add_validator(_payload_size_limit)  # type: ignore[attr-defined]
    except AttributeError:
        # Non-validating bus implementation
        pass


def _payload_size_limit(event: AgentEvent, max_bytes: int = 64 * 1024) -> None:
    import json
    try:
        data = json.dumps(event.payload or {})
    except Exception:
        # If not serializable, consider it too large/unsafe
        raise ValueError("Event payload not serializable; rejected by privacy policy")
    if len(data.encode("utf-8")) > max_bytes:
        raise ValueError("Event payload exceeds privacy size limit")


