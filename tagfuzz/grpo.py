from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List


@dataclass
class GRPOSample:
    prompt: str
    code: str
    reward: float
    advantage: float
    metadata: Dict

    def serializable(self) -> Dict:
        return {
            "prompt": self.prompt,
            "code": self.code,
            "reward": self.reward,
            "advantage": self.advantage,
            "metadata": self.metadata,
        }


class GRPOAdapter:
    """Interface for online policy updates.

    The paper method updates LoRA parameters with group-relative advantages.
    This adapter keeps the runtime independent from a specific training stack:
    experiments can record GRPO samples by default, while deployments with
    PEFT/TRL can subclass this interface and perform actual updates.
    """

    def update(self, samples: Iterable[GRPOSample]) -> Dict:
        raise NotImplementedError


class RecordingGRPOAdapter(GRPOAdapter):
    """Persist GRPO samples without mutating model parameters."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def update(self, samples: Iterable[GRPOSample]) -> Dict:
        rows = [sample.serializable() for sample in samples]
        with self.path.open("a", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        return {"status": "recorded", "samples": len(rows), "path": str(self.path)}


def build_grpo_adapter(config) -> GRPOAdapter:
    return RecordingGRPOAdapter(Path(config.grpo_output))

