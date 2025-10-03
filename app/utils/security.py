from __future__ import annotations

import os
from fastapi import Header, HTTPException, status, Depends


def require_agent_token(x_agent_token: str | None = Header(default=None)) -> None:
    expected = os.getenv("AGENT_COMM_TOKEN")
    if not expected:
        return  # disabled when not configured
    if not x_agent_token or x_agent_token != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing X-Agent-Token")


RequireAgentToken = Depends(require_agent_token)


