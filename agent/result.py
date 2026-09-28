from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel

from agent.tools.parse_tool import ParseToolOutput


class AgentEvent(BaseModel):
    """Structured progress event emitted alongside on_log text."""

    type: Literal[
        "trial_started",
        "proposal",
        "metrics",
        "recommendation",
        "error",
    ]
    trial: Optional[int] = None
    rationale: Optional[str] = None
    hypothesis: Optional[str] = None
    command_flags: Optional[str] = None
    metrics: Optional[ParseToolOutput] = None
    recommendation: Optional[str] = None
    error: Optional[str] = None
    exit_code: Optional[int] = None
    timed_out: bool = False


class TrialResult(BaseModel):
    trial_number: int
    status: Literal["running", "completed", "failed"] = "running"
    rationale: Optional[str] = None
    hypothesis: Optional[str] = None
    command_flags: Optional[str] = None
    metrics: Optional[ParseToolOutput] = None
    exit_code: Optional[int] = None
    timed_out: bool = False
    error: Optional[str] = None


class AgentRunResult(BaseModel):
    status: Literal["completed", "failed"]
    trials: List[TrialResult] = []
    recommendation: Optional[str] = None
    error: Optional[str] = None
