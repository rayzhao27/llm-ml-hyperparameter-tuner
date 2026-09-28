from __future__ import annotations

# mirrors QueryEngine.ts from Claude Code repo
# the core agent loop: read → propose → run → parse → decide → repeat

import json
import time
from typing import Callable, Optional

import anthropic

from agent.config import AgentConfig
from agent.observability import (
    observe_error,
    observe_llm,
    observe_run_start,
    observe_tool,
    observe_trial,
    observe_val_loss,
)
from agent.result import AgentEvent, AgentRunResult, TrialResult
from agent.tools.read_tool import ReadToolInput, read_file
from agent.tools.execute_tool import ExecuteToolInput, execute_command
from agent.tools.parse_tool import ParseToolInput, parse_logs


OnLog = Callable[[str], None]
OnEvent = Callable[[AgentEvent], None]

_client: Optional[anthropic.Anthropic] = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client


def _parse_proposal(raw: str) -> dict:
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        if text.endswith("```"):
            text = text[: text.rfind("```")]
        text = text.strip()
    text = text.replace("```json", "").replace("```", "").strip()
    proposal = json.loads(text)
    if not isinstance(proposal, dict):
        raise ValueError("proposal is not a JSON object")
    missing = {"rationale", "command_flags", "hypothesis"} - proposal.keys()
    if missing:
        raise ValueError(f"proposal missing keys: {sorted(missing)}")
    return proposal


def _emit(on_event: Optional[OnEvent], event: AgentEvent) -> None:
    if on_event:
        on_event(event)


def run_agent(
        cfg: AgentConfig,
        on_log: OnLog = print,  # callback for live streaming
        on_event: Optional[OnEvent] = None,
        run_id: Optional[str] = None,
) -> AgentRunResult:

    rid = run_id or "cli"
    if run_id is None:
        observe_run_start(rid, cfg)

    trials: list[TrialResult] = []

    def fail(
            message: str,
            trial: Optional[int] = None,
            kind: str = "error",
            trial_started_at: Optional[float] = None,
    ) -> AgentRunResult:
        observe_error(kind, run_id=rid, trial=trial, error=message)
        if trial is not None and trial_started_at is not None:
            observe_trial(
                run_id=rid,
                trial=trial,
                duration_s=time.perf_counter() - trial_started_at,
                status="failed",
            )
        on_log(f" {message}\n")
        _emit(on_event, AgentEvent(type="error", trial=trial, error=message))
        return AgentRunResult(status="failed", trials=trials, error=message)

    on_log("\n reading trainer.py...\n")

    # step 1 — read trainer.py (mirrors FileReadTool)
    tool_t0 = time.perf_counter()
    try:
        trainer = read_file(ReadToolInput(path=cfg.trainer_path))
    except (FileNotFoundError, ValueError) as exc:
        observe_tool("read", time.perf_counter() - tool_t0, run_id=rid, success=False)
        return fail(f"bad config: {exc}", kind="config")
    observe_tool(
        "read",
        time.perf_counter() - tool_t0,
        run_id=rid,
        success=True,
        lines=trainer.lines,
    )

    on_log(f" read {trainer.lines} lines from {trainer.path}\n")

    on_log(" sending to claude for analysis...\n")

    baseline = cfg.baseline
    direction = "lower is better" if not baseline.higher_is_better else "higher is better"

    # build initial prompt with trainer code loaded from disk
    messages = [
        {
            "role": "user",
            "content": f"""{cfg.agent_persona}
            
            
            ```Here is the trainer code:
            ```python
            {trainer.content}
            ```

            Baseline to beat:
            - Metric: {baseline.metric_name} ({direction})
            - Value: {baseline.metric_value}
            - Full run: {baseline.epochs} epochs
            - Note: {baseline.note}

            Your job is to propose hyperparameter configurations that could improve performance.
            Each config will be smoke tested for {cfg.smoke_epochs} epochs before deciding if it is worth a full run.

            Propose your FIRST configuration. Think carefully about what is most likely to improve {baseline.metric_name}.

            Respond in this exact JSON format:
            {{
                "rationale": "why you chose these params",
                "command_flags": "--hidden_size 512 --learning_rate 5e-4",
                "hypothesis": "what you expect to happen"
            }}

            Return ONLY the JSON, no other text."""
        }
    ]

    # step 2 — the agent loop (mirrors QueryEngine.ts tool loop)
    for trial in range(1, cfg.max_trials + 1):
        trial_t0 = time.perf_counter()
        current = TrialResult(trial_number=trial, status="running")
        trials.append(current)
        _emit(on_event, AgentEvent(type="trial_started", trial=trial))
        on_log(f"\n trial {trial}/{cfg.max_trials} — asking claude for config...\n")

        # call claude
        llm_t0 = time.perf_counter()
        try:
            response = _get_client().messages.create(
                model="claude-opus-4-5",
                max_tokens=1000,
                messages=messages
            )
        except Exception as exc:
            observe_llm(time.perf_counter() - llm_t0, run_id=rid, trial=trial, kind="proposal")
            current.status = "failed"
            current.error = f"LLM call failed: {exc}"
            return fail(current.error, trial=trial, kind="llm", trial_started_at=trial_t0)
        observe_llm(time.perf_counter() - llm_t0, run_id=rid, trial=trial, kind="proposal")

        if not response.content or not getattr(response.content[0], "text", None):
            current.status = "failed"
            current.error = "empty LLM response"
            return fail(current.error, trial=trial, kind="llm", trial_started_at=trial_t0)

        raw = response.content[0].text

        # parse claude's proposed config
        try:
            proposal = _parse_proposal(raw)
        except (json.JSONDecodeError, ValueError) as exc:
            current.status = "failed"
            current.error = f"failed to parse claude response: {exc}"
            on_log(f" failed to parse claude response: {raw}\n")
            _emit(on_event, AgentEvent(type="error", trial=trial, error=current.error))
            observe_error("parse", run_id=rid, trial=trial, error=current.error)
            observe_trial(
                run_id=rid,
                trial=trial,
                duration_s=time.perf_counter() - trial_t0,
                status="failed",
            )
            return AgentRunResult(status="failed", trials=trials, error=current.error)

        current.rationale = proposal["rationale"]
        current.hypothesis = proposal["hypothesis"]
        current.command_flags = proposal["command_flags"]
        _emit(on_event, AgentEvent(
            type="proposal",
            trial=trial,
            rationale=current.rationale,
            hypothesis=current.hypothesis,
            command_flags=current.command_flags,
        ))

        on_log(f" rationale: {proposal['rationale']}\n")
        on_log(f" hypothesis: {proposal['hypothesis']}\n")
        on_log(f" flags: {proposal['command_flags']}\n")

        # step 3 — run smoke test (mirrors BashTool)
        command = (
            f"caffeinate -i {cfg.python_bin} training/trainer.py "
            f"{proposal['command_flags']} "
            f"{cfg.extra_flags} "
            f"--epochs {cfg.smoke_epochs} "
            f"--checkpoint_dir checkpoints/trial_{trial} "
            f"--log_dir runs/trial_{trial}"
        )

        on_log(f"\n running {cfg.smoke_epochs}-epoch smoke test...\n")
        on_log(" ─────────────────────────────────────\n")

        exec_t0 = time.perf_counter()
        result = execute_command(
            ExecuteToolInput(command=command, cwd=cfg.project_dir),
            on_output=on_log  # stream logs live
        )
        observe_tool(
            "execute",
            time.perf_counter() - exec_t0,
            run_id=rid,
            trial=trial,
            success=result.success,
            timed_out=result.timed_out,
            exit_code=result.exit_code,
        )

        on_log("\n ─────────────────────────────────────\n")

        current.exit_code = result.exit_code
        current.timed_out = result.timed_out
        if result.timed_out:
            current.error = "subprocess timed out"
            on_log(f" {current.error}\n")
            observe_error("timeout", run_id=rid, trial=trial, error=current.error)
            _emit(on_event, AgentEvent(
                type="error",
                trial=trial,
                error=current.error,
                exit_code=result.exit_code,
                timed_out=True,
            ))

        # step 4 — parse the logs
        parse_t0 = time.perf_counter()
        metrics = parse_logs(ParseToolInput(logs=result.stdout))
        observe_tool(
            "parse",
            time.perf_counter() - parse_t0,
            run_id=rid,
            trial=trial,
            epochs=len(metrics.epochs),
        )
        current.metrics = metrics
        current.status = "failed" if result.timed_out else "completed"
        if metrics.best_val_loss is not None:
            observe_val_loss(rid, metrics.best_val_loss)
        _emit(on_event, AgentEvent(
            type="metrics",
            trial=trial,
            metrics=metrics,
            exit_code=result.exit_code,
            timed_out=result.timed_out,
        ))
        on_log(f" metrics: {metrics.summary}\n")
        observe_trial(
            run_id=rid,
            trial=trial,
            duration_s=time.perf_counter() - trial_t0,
            status=current.status,
        )

        # step 5 — feed results back to claude (mirrors QueryEngine retry logic)
        messages.append({"role": "assistant", "content": raw})
        messages.append({
            "role": "user",
            "content": f"""Smoke test results for trial {trial}:

            {metrics.summary}

            Epoch breakdown:
            {chr(10).join(
                f"  epoch {e.epoch}: train_loss={e.train_loss:.4f} val_loss={e.val_loss:.4f}"
                + (f" ppl={e.ppl:.1f}" if e.ppl else "")
                for e in metrics.epochs
            )}

            Converging: {metrics.converging}
            Exit code: {result.exit_code}
            Timed out: {result.timed_out}

            {"This config looks promising — val_loss is improving." if metrics.converging else "This config did not show strong convergence."}

            {
                f"Propose your NEXT configuration. Learn from what worked and what did not. Return the same JSON format."
                if trial < cfg.max_trials else
                f"This was the final trial. Summarize all trials and give your final recommendation — which config should I use for the full {baseline.epochs}-epoch run and why?"
            }"""
        })

        # final recommendation
        if trial == cfg.max_trials:
            on_log("\n getting final recommendation from claude...\n")

            llm_t0 = time.perf_counter()
            try:
                final = _get_client().messages.create(
                    model="claude-opus-4-5",
                    max_tokens=2000,
                    messages=messages
                )
            except Exception as exc:
                observe_llm(time.perf_counter() - llm_t0, run_id=rid, trial=trial, kind="recommendation")
                return fail(f"LLM call failed: {exc}", trial=trial, kind="llm")
            observe_llm(time.perf_counter() - llm_t0, run_id=rid, trial=trial, kind="recommendation")

            if not final.content or not getattr(final.content[0], "text", None):
                return fail("empty LLM recommendation", trial=trial, kind="llm")

            recommendation = final.content[0].text
            on_log("\n final recommendation:\n\n")
            on_log(recommendation)
            on_log("\n")
            _emit(on_event, AgentEvent(type="recommendation", recommendation=recommendation))
            return AgentRunResult(
                status="completed",
                trials=trials,
                recommendation=recommendation,
            )

    return AgentRunResult(status="completed", trials=trials)
