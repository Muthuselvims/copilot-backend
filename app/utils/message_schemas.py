from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from uuid import uuid4
from datetime import datetime, timezone


class MessageRole(str, Enum):
    user = "user"
    agent = "agent"
    system = "system"


class FipaPerformative(str, Enum):
    inform = "inform"
    request = "request"
    propose = "propose"
    agree = "agree"
    refuse = "refuse"
    confirm = "confirm"
    disconfirm = "disconfirm"
    query_if = "query-if"
    query_ref = "query-ref"
    not_understood = "not-understood"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class FipaAclEnvelope(BaseModel):
    protocol: str = Field(default="fipa-acl")
    performative: Optional[FipaPerformative] = None
    language: Optional[str] = None
    ontology: Optional[str] = None
    conversation_id: Optional[str] = None
    reply_with: Optional[str] = None
    in_reply_to: Optional[str] = None
    reply_by: Optional[str] = None


class AgentMessage(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: str = Field(default_factory=_now_iso)
    sender: str
    recipients: List[str] = Field(default_factory=list)
    role: MessageRole = MessageRole.agent
    topic: Optional[str] = None
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    fipa: Optional[FipaAclEnvelope] = None


class AgentEvent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: str = Field(default_factory=_now_iso)
    topic: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    correlation_id: Optional[str] = None


class Subscription(BaseModel):
    topic: str
    group: Optional[str] = None

