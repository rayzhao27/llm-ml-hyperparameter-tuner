# handles loading user config from config.json
# makes the agent generalized — not hardcoded to BERT4Rec

import json
from pathlib import Path
from pydantic import BaseModel


class BaselineConfig(BaseModel):
    metric_name: str        # e.g. "val_loss", "hr10", "ndcg10"
    metric_value: float     # e.g. 0.29
    higher_is_better: bool  # True for HR@10, False for val_loss
    epochs: int             # full run epoch count e.g. 300
    note: str = ""          # any context about the baseline


class AgentConfig(BaseModel):
    trainer_path: str           # path to trainer.py
    project_dir: str            # root of the ML project
    smoke_epochs: int = 5       # epochs per smoke test
    max_trials: int = 3         # how many configs to try
    baseline: BaselineConfig
    extra_flags: str = ""       # any fixed flags to always include
    agent_persona: str = "You are an expert ML engineer."
    python_bin: str = "python"


def load_config(config_path: str = "config.json") -> AgentConfig:
    path = Path(config_path)

    if not path.exists():
        raise FileNotFoundError(
            f"config.json not found at {config_path}\n"
            f"create one based on config.example.json"
        )

    raw = json.loads(path.read_text(encoding="utf-8"))
    return AgentConfig(**raw)
