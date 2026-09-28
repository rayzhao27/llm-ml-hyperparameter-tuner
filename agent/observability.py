from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any, Optional

from prometheus_client import Counter, Gauge, Histogram

from agent.config import AgentConfig

RUNS_STARTED = Counter("ml_agent_runs_started_total", "Agent runs started")
TRIALS_RUN = Counter("ml_agent_trials_run_total", "Trials run")
TOOL_CALLS = Counter("ml_agent_tool_calls_total", "Tool calls", ["tool"])
ERRORS = Counter("ml_agent_errors_total", "Errors", ["kind"])
TRIAL_DURATION = Histogram(
    "ml_agent_trial_duration_seconds",
    "Wall time for one trial",
    buckets=(1, 5, 15, 30, 60, 120, 300, 600, 1200),
)
LLM_LATENCY = Histogram(
    "ml_agent_llm_latency_seconds",
    "Anthropic messages.create latency",
    buckets=(0.1, 0.5, 1, 2, 5, 10, 30, 60, 120),
)
BEST_VAL_LOSS = Gauge(
    "ml_agent_best_val_loss",
    "Best val_loss observed for a run",
    ["run_id"],
)

_best_val_loss: dict[str, float] = {}
_configured = False


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "event": getattr(record, "event", record.getMessage()),
        }
        fields = getattr(record, "fields", None)
        if isinstance(fields, dict):
            payload.update(fields)
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging() -> None:
    global _configured
    if _configured:
        return
    logger = logging.getLogger("ml_agent")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    logger.handlers = [handler]
    _configured = True


def log_event(event: str, level: int = logging.INFO, **fields: Any) -> None:
    configure_logging()
    logging.getLogger("ml_agent").log(
        level,
        event,
        extra={"event": event, "fields": fields},
    )


def observe_run_start(run_id: str, cfg: AgentConfig) -> None:
    RUNS_STARTED.inc()
    log_event(
        "run_start",
        run_id=run_id,
        max_trials=cfg.max_trials,
        smoke_epochs=cfg.smoke_epochs,
        trainer_path=cfg.trainer_path,
        project_dir=cfg.project_dir,
    )


def observe_trial(
        *,
        run_id: str,
        trial: int,
        duration_s: float,
        status: str,
) -> None:
    TRIALS_RUN.inc()
    TRIAL_DURATION.observe(duration_s)
    log_event(
        "trial",
        run_id=run_id,
        trial=trial,
        duration_s=round(duration_s, 4),
        status=status,
    )


def observe_tool(
        tool: str,
        duration_s: float,
        *,
        run_id: str,
        trial: Optional[int] = None,
        **extra: Any,
) -> None:
    TOOL_CALLS.labels(tool=tool).inc()
    log_event(
        "tool_call",
        run_id=run_id,
        trial=trial,
        tool=tool,
        duration_s=round(duration_s, 4),
        **extra,
    )


def observe_llm(
        duration_s: float,
        *,
        run_id: str,
        trial: Optional[int] = None,
        kind: str = "proposal",
) -> None:
    LLM_LATENCY.observe(duration_s)
    log_event(
        "llm_latency",
        run_id=run_id,
        trial=trial,
        kind=kind,
        duration_s=round(duration_s, 4),
    )


def observe_error(kind: str, *, run_id: Optional[str] = None, **fields: Any) -> None:
    ERRORS.labels(kind=kind).inc()
    log_event("error", level=logging.ERROR, kind=kind, run_id=run_id, **fields)


def observe_val_loss(run_id: str, val_loss: float) -> None:
    prev = _best_val_loss.get(run_id)
    if prev is None or val_loss < prev:
        _best_val_loss[run_id] = val_loss
        BEST_VAL_LOSS.labels(run_id=run_id).set(val_loss)
        log_event("best_val_loss", run_id=run_id, val_loss=val_loss)
