from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any, Optional

from agent.config import AgentConfig
from agent.engine import run_agent
from agent.observability import observe_error, observe_run_start
from agent.result import AgentEvent, AgentRunResult
from backend.models import StreamEvent
from backend.store import RunStore


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AgentRunner:
    """Runs run_agent() in a background thread and publishes stream events."""

    def __init__(self, store: RunStore) -> None:
        self.store = store

    def start(self, run_id: str, cfg: AgentConfig) -> None:
        thread = threading.Thread(
            target=self._run,
            args=(run_id, cfg),
            name=f"agent-run-{run_id[:8]}",
            daemon=True,
        )
        thread.start()

    def _emit(
            self,
            run_id: str,
            event_type: str,
            *,
            trial: Optional[int] = None,
            message: Optional[str] = None,
            data: Optional[dict[str, Any]] = None,
    ) -> None:
        event = StreamEvent(
            type=event_type,  # type: ignore[arg-type]
            run_id=run_id,
            ts=_utc_now(),
            trial=trial,
            message=message,
            data=data,
        )
        self.store.publish(run_id, event)

    def _run(self, run_id: str, cfg: AgentConfig) -> None:
        observe_run_start(run_id, cfg)
        self.store.set_status(run_id, "running")
        self._emit(run_id, "status", data={"status": "running"})

        def on_log(line: str) -> None:
            self._emit(run_id, "log", message=line)

        def on_event(event: AgentEvent) -> None:
            self.store.apply_event(run_id, event)
            payload = event.model_dump(exclude_none=True)
            payload.pop("type", None)
            payload.pop("trial", None)
            self._emit(
                run_id,
                event.type,
                trial=event.trial,
                message=event.error or event.recommendation,
                data=payload or None,
            )

        try:
            result: AgentRunResult = run_agent(
                cfg, on_log=on_log, on_event=on_event, run_id=run_id,
            )
        except Exception as exc:
            error = f"agent crashed: {exc}"
            observe_error("crash", run_id=run_id, error=error)
            self.store.set_status(run_id, "failed", error=error)
            self._emit(run_id, "error", message=error, data={"status": "failed", "error": error})
            self._emit(run_id, "status", data={"status": "failed", "error": error})
            return

        if result.recommendation:
            self.store.set_recommendation(run_id, result.recommendation)
        if result.status == "failed":
            self.store.set_status(run_id, "failed", error=result.error)
            self._emit(
                run_id,
                "status",
                message=result.error,
                data={"status": "failed", "error": result.error},
            )
            return

        self.store.set_status(run_id, "completed")
        self._emit(run_id, "status", data={"status": "completed"})
