from __future__ import annotations

import time
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from agent.config import AgentConfig
from agent.result import AgentEvent, AgentRunResult, TrialResult
from agent.tools.parse_tool import EpochMetrics, ParseToolOutput
from backend.app import app

REPO_ROOT = Path(__file__).resolve().parents[2]


def _valid_config() -> dict:
    return {
        "trainer_path": str(REPO_ROOT / "agent" / "engine.py"),
        "project_dir": str(REPO_ROOT),
        "smoke_epochs": 1,
        "max_trials": 1,
        "baseline": {
            "metric_name": "val_loss",
            "metric_value": 1.0,
            "higher_is_better": False,
            "epochs": 10,
            "note": "test",
        },
        "python_bin": "python3",
    }


def _fake_run_agent(cfg: AgentConfig, on_log=print, on_event=None, run_id=None) -> AgentRunResult:
    on_log(" reading trainer.py...\n")
    metrics = ParseToolOutput(
        epochs=[EpochMetrics(epoch=1, train_loss=1.2, val_loss=1.1)],
        best_val_loss=1.1,
        final_val_loss=1.1,
        converging=False,
        summary="1 epochs — best val_loss: 1.1000, final val_loss: 1.1000, converging: False",
    )
    if on_event:
        on_event(AgentEvent(type="trial_started", trial=1))
        on_event(AgentEvent(
            type="proposal",
            trial=1,
            rationale="try a larger hidden size",
            hypothesis="val_loss should drop",
            command_flags="--hidden_size 512",
        ))
        on_log(" rationale: try a larger hidden size\n")
        on_log(" epoch 1 val_loss=1.1\n")
        on_event(AgentEvent(type="metrics", trial=1, metrics=metrics, exit_code=0))
        on_event(AgentEvent(type="recommendation", recommendation="use --hidden_size 512"))
    on_log(" final recommendation: use --hidden_size 512\n")
    return AgentRunResult(
        status="completed",
        trials=[TrialResult(
            trial_number=1,
            status="completed",
            rationale="try a larger hidden size",
            hypothesis="val_loss should drop",
            command_flags="--hidden_size 512",
            metrics=metrics,
            exit_code=0,
        )],
        recommendation="use --hidden_size 512",
    )


def _wait_until_done(client: TestClient, run_id: str, timeout: float = 2.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        payload = client.get(f"/runs/{run_id}").json()
        if payload["status"] in {"completed", "failed"}:
            return payload
        time.sleep(0.02)
    raise TimeoutError(f"run {run_id} did not finish: {payload}")


class ApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self._cm = TestClient(app)
        self.client = self._cm.__enter__()

    def tearDown(self) -> None:
        self._cm.__exit__(None, None, None)

    def test_health(self) -> None:
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    def test_bad_body_returns_422(self) -> None:
        response = self.client.post("/runs", json={"trainer_path": "x"})
        self.assertEqual(response.status_code, 422)

    def test_missing_trainer_returns_400(self) -> None:
        body = _valid_config()
        body["trainer_path"] = "/no/such/trainer.py"
        response = self.client.post("/runs", json=body)
        self.assertEqual(response.status_code, 400)
        self.assertIn("trainer_path not found", response.json()["detail"])

    def test_unknown_run_returns_404(self) -> None:
        response = self.client.get("/runs/does-not-exist")
        self.assertEqual(response.status_code, 404)

    def test_metrics_endpoint(self) -> None:
        response = self.client.get("/metrics")
        self.assertEqual(response.status_code, 200)
        body = response.text
        self.assertIn("ml_agent_runs_started_total", body)
        self.assertIn("ml_agent_trials_run_total", body)
        self.assertIn("ml_agent_tool_calls_total", body)
        self.assertIn("ml_agent_errors_total", body)
        self.assertIn("ml_agent_trial_duration_seconds", body)
        self.assertIn("ml_agent_llm_latency_seconds", body)
        self.assertIn("ml_agent_best_val_loss", body)

    def test_create_run_streams_and_records_trials(self) -> None:
        with patch("backend.runner.run_agent", side_effect=_fake_run_agent):
            created = self.client.post("/runs", json=_valid_config())
            self.assertEqual(created.status_code, 201)
            run_id = created.json()["run_id"]
            self.assertTrue(created.json()["stream_url"].endswith(f"/runs/{run_id}/stream"))

            snapshot = _wait_until_done(self.client, run_id)
            self.assertEqual(snapshot["status"], "completed")
            self.assertEqual(len(snapshot["trials"]), 1)
            self.assertEqual(snapshot["trials"][0]["command_flags"], "--hidden_size 512")
            self.assertEqual(snapshot["trials"][0]["metrics"]["best_val_loss"], 1.1)
            self.assertEqual(snapshot["recommendation"], "use --hidden_size 512")

            with self.client.websocket_connect(f"/runs/{run_id}/stream") as ws:
                types = []
                while True:
                    event = ws.receive_json()
                    types.append(event["type"])
                    if event["type"] == "status" and event["data"]["status"] in {"completed", "failed"}:
                        break
            self.assertIn("log", types)
            self.assertIn("proposal", types)
            self.assertIn("metrics", types)
            self.assertIn("recommendation", types)


if __name__ == "__main__":
    unittest.main()
