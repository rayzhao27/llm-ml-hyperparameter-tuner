from __future__ import annotations

import asyncio
import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional
from uuid import uuid4

from agent.config import AgentConfig
from agent.result import AgentEvent
from backend.models import RunResponse, RunStatus, StreamEvent, TrialRecord


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RunRecord:
    def __init__(self, run_id: str, config: AgentConfig) -> None:
        self.run_id = run_id
        self.config = config
        self.status: RunStatus = "queued"
        self.trials: Dict[int, TrialRecord] = {}
        self.recommendation: Optional[str] = None
        self.error: Optional[str] = None
        self.events: List[StreamEvent] = []
        self.created_at = _utc_now()
        self.updated_at = self.created_at
        self.subscribers: List[asyncio.Queue[Optional[StreamEvent]]] = []

    def snapshot(self) -> RunResponse:
        trials = [self.trials[n] for n in sorted(self.trials)]
        return RunResponse(
            run_id=self.run_id,
            status=self.status,
            config=self.config,
            trials=trials,
            recommendation=self.recommendation,
            error=self.error,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )


class RunStore:
    """In-memory run store. Agent thread writes; FastAPI/WS read."""

    def __init__(self) -> None:
        self._runs: Dict[str, RunRecord] = {}
        self._lock = threading.Lock()
        self.loop: Optional[asyncio.AbstractEventLoop] = None

    def create(self, config: AgentConfig) -> RunRecord:
        run = RunRecord(run_id=str(uuid4()), config=config)
        with self._lock:
            self._runs[run.run_id] = run
        return run

    def get(self, run_id: str) -> Optional[RunRecord]:
        with self._lock:
            return self._runs.get(run_id)

    def set_status(self, run_id: str, status: RunStatus, error: Optional[str] = None) -> None:
        with self._lock:
            run = self._runs[run_id]
            run.status = status
            if error:
                run.error = error
            run.updated_at = _utc_now()

    def set_recommendation(self, run_id: str, recommendation: str) -> None:
        with self._lock:
            run = self._runs[run_id]
            run.recommendation = recommendation
            run.updated_at = _utc_now()

    def apply_event(self, run_id: str, event: AgentEvent) -> None:
        with self._lock:
            run = self._runs[run_id]
            trial_no = event.trial
            if trial_no is not None and trial_no not in run.trials:
                run.trials[trial_no] = TrialRecord(trial_number=trial_no)

            trial = run.trials.get(trial_no) if trial_no is not None else None
            if trial is not None:
                if event.rationale is not None:
                    trial.rationale = event.rationale
                if event.hypothesis is not None:
                    trial.hypothesis = event.hypothesis
                if event.command_flags is not None:
                    trial.command_flags = event.command_flags
                if event.metrics is not None:
                    trial.metrics = event.metrics
                if event.exit_code is not None:
                    trial.exit_code = event.exit_code
                if event.timed_out:
                    trial.timed_out = True
                if event.error is not None:
                    trial.error = event.error
                    trial.status = "failed"
                elif event.type == "metrics" and not trial.timed_out:
                    trial.status = "completed"
                elif event.type == "trial_started":
                    trial.status = "running"

            if event.type == "recommendation" and event.recommendation:
                run.recommendation = event.recommendation
            if event.type == "error" and event.error and event.trial is None:
                run.error = event.error

            run.updated_at = _utc_now()

    def publish(self, run_id: str, event: StreamEvent) -> None:
        with self._lock:
            run = self._runs[run_id]
            run.events.append(event)
            run.updated_at = _utc_now()
            queues = list(run.subscribers)
        self._fanout(queues, event)

    def subscribe(self, run_id: str) -> tuple[List[StreamEvent], asyncio.Queue[Optional[StreamEvent]]]:
        queue: asyncio.Queue[Optional[StreamEvent]] = asyncio.Queue()
        with self._lock:
            run = self._runs[run_id]
            replay = list(run.events)
            run.subscribers.append(queue)
        return replay, queue

    def unsubscribe(self, run_id: str, queue: asyncio.Queue[Optional[StreamEvent]]) -> None:
        with self._lock:
            run = self._runs.get(run_id)
            if run is None:
                return
            if queue in run.subscribers:
                run.subscribers.remove(queue)

    def _fanout(
            self,
            queues: List[asyncio.Queue[Optional[StreamEvent]]],
            event: StreamEvent,
    ) -> None:
        if self.loop is None:
            return
        for q in queues:
            self.loop.call_soon_threadsafe(q.put_nowait, event)
