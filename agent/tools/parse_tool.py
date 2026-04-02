# no direct equivalent in Claude Code — this is the ML-specific part
# parses trainer.py log output into structured metrics
# matches the exact log format from your trainer.py:
# "Epoch 3/3 done in 12.4s | train_loss=2.1234 | val_loss=1.9876"
from __future__ import annotations

import re
from pydantic import BaseModel
from typing import Optional, List


class ParseToolInput(BaseModel):
    logs: str


class EpochMetrics(BaseModel):
    epoch: int
    train_loss: float
    val_loss: float
    ppl: Optional[float] = None


class ParseToolOutput(BaseModel):
    epochs: List[EpochMetrics]
    best_val_loss: Optional[float] = None
    final_val_loss: Optional[float] = None
    converging: bool
    summary: str


def parse_logs(input: ParseToolInput) -> ParseToolOutput:
    lines = input.logs.splitlines()
    epochs = []

    for line in lines:
        # matches: "Epoch 3/3 done in 12.4s | train_loss=2.1234 | val_loss=1.9876"
        epoch_match = re.search(
            r"Epoch (\d+)/\d+ done.*train_loss=([\d.]+).*val_loss=([\d.]+)", line
        )
        if epoch_match:
            epochs.append(EpochMetrics(
                epoch=int(epoch_match.group(1)),
                train_loss=float(epoch_match.group(2)),
                val_loss=float(epoch_match.group(3)),
            ))

        # matches: "── val epoch 3 | loss 1.9876 | ppl 7.3 | acc 0.234"
        val_match = re.search(
            r"val epoch (\d+).*loss ([\d.]+).*ppl\s+([\d.]+)", line
        )
        if val_match:
            epoch_num = int(val_match.group(1))
            existing = next((e for e in epochs if e.epoch == epoch_num), None)
            if existing:
                existing.ppl = float(val_match.group(3))

    best_val_loss = min((e.val_loss for e in epochs), default=None)
    final_val_loss = epochs[-1].val_loss if epochs else None

    # converging = val loss going down in at least 60% of epochs
    converging = False
    if len(epochs) >= 2:
        improvements = sum(
            1 for i in range(1, len(epochs))
            if epochs[i].val_loss < epochs[i - 1].val_loss
        )
        converging = improvements >= len(epochs) * 0.6

    if not epochs:
        summary = "no epoch metrics found in logs"
    else:
        summary = (
            f"{len(epochs)} epochs — "
            f"best val_loss: {best_val_loss:.4f}, "
            f"final val_loss: {final_val_loss:.4f}, "
            f"converging: {converging}"
        )

    return ParseToolOutput(
        epochs=epochs,
        best_val_loss=best_val_loss,
        final_val_loss=final_val_loss,
        converging=converging,
        summary=summary
    )