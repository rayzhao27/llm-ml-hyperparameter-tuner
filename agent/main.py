from __future__ import annotations
import os
from agent.config import load_config
from agent.engine import run_agent

if not os.environ.get("ANTHROPIC_API_KEY"):
    raise EnvironmentError("missing ANTHROPIC_API_KEY — run: export ANTHROPIC_API_KEY=your_key")

cfg = load_config("config.json")
run_agent(cfg)
