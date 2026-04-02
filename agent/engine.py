from __future__ import annotations

# mirrors QueryEngine.ts from Claude Code repo
# the core agent loop: read → propose → run → parse → decide → repeat

import json
from typing import Callable
import anthropic

from agent.config import AgentConfig
from agent.tools.read_tool import ReadToolInput, read_file
from agent.tools.execute_tool import ExecuteToolInput, execute_command
from agent.tools.parse_tool import ParseToolInput, parse_logs


client = anthropic.Anthropic()


def run_agent(
        cfg: AgentConfig,
        on_log: Callable[[str], None] = print  # callback for live streaming
) -> None:

    on_log("\n reading trainer.py...\n")

    # step 1 — read trainer.py (mirrors FileReadTool)
    trainer = read_file(ReadToolInput(path=cfg.trainer_path))
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
        on_log(f"\n trial {trial}/{cfg.max_trials} — asking claude for config...\n")

        # call claude
        response = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=1000,
            messages=messages
        )

        raw = response.content[0].text

        # parse claude's proposed config
        try:
            proposal = json.loads(raw.replace("```json", "").replace("```", "").strip())
        except json.JSONDecodeError:
            on_log(f" failed to parse claude response: {raw}\n")
            break

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

        result = execute_command(
            ExecuteToolInput(command=command, cwd=cfg.project_dir),
            on_output=on_log  # stream logs live
        )

        on_log("\n ─────────────────────────────────────\n")

        # step 4 — parse the logs
        metrics = parse_logs(ParseToolInput(logs=result.stdout))
        on_log(f" metrics: {metrics.summary}\n")

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

            final = client.messages.create(
                model="claude-opus-4-5",
                max_tokens=2000,
                messages=messages
            )

            on_log("\n final recommendation:\n\n")
            on_log(final.content[0].text)
            on_log("\n")
