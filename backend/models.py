from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel

from agent.config import AgentConfig, BaselineConfig
from agent.tools.parse_tool import ParseToolOutput

# Re-export so API consumers can import request shapes from one place.
__all__ = [
    "AgentConfig",
    "BaselineConfig",
    "CreateRunResponse",
    "HealthResponse",
    "RunResponse",
    "StreamEvent",
    "StreamEventType",
    "TrialRecord",
]


RunStatus = Literal["queued", "running", "completed", "failed"]
TrialStatus = Literal["running", "completed", "failed"]
StreamEventType = Literal[
    "log",
    "status",
    "trial_started",
    "proposal",
    "metrics",
    "recommendation",
    "error",
]


class TrialRecord(BaseModel):
    trial_number: int
    status: TrialStatus = "running"
    rationale: Optional[str] = None
    hypothesis: Optional[str] = None
    command_flags: Optional[str] = None
    metrics: Optional[ParseToolOutput] = None
    exit_code: Optional[int] = None
    timed_out: bool = False
    error: Optional[str] = None


class CreateRunResponse(BaseModel):
    run_id: str
    status: RunStatus
    stream_url: str


class RunResponse(BaseModel):
    run_id: str
    status: RunStatus
    config: AgentConfig
    trials: List[TrialRecord]
    recommendation: Optional[str] = None
    error: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class StreamEvent(BaseModel):
    type: StreamEventType
    run_id: str
    ts: datetime
    trial: Optional[int] = None
    message: Optional[str] = None
    data: Optional[Dict[str, Any]] = None


class HealthResponse(BaseModel):
    status: str
    service: str
