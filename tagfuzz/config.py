from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


@dataclass
class ModelConfig:
    name: str = ""
    temperature: float = 0.8
    max_new_tokens: int = 2048
    context_length: int = 8192
    batch_size: int = 1
    gpu_devices: List[int] = field(default_factory=lambda: [0])
    backend: str = "hf"


@dataclass
class RunnerConfig:
    work_dir: Path
    compile_command: List[str]
    coverage_command: List[str]
    command_cwd: Path
    crash_command: Optional[List[str]] = None
    oracle_command: Optional[List[str]] = None
    timeout_seconds: int = 1200


@dataclass
class TAGFuzzConfig:
    targets_file: Path
    target_ids: List[str]
    candidate_group_size: int = 8
    calls_budget: int = 0
    time_budget_seconds: int = 0
    alpha: float = 1.0
    beta: float = 0.5
    regression_lambda: float = 0.5
    feedback_examples: int = 3
    grpo_enabled: bool = False
    grpo_output: Path = Path("grpo/updates.jsonl")
    seed_program: str = "package main\nfunc main() {}\n"


@dataclass
class ExperimentConfig:
    model: ModelConfig
    runner: RunnerConfig
    tagfuzz: TAGFuzzConfig


def _as_path(base: Path, value: str) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        return path
    return (base / path).resolve()


def _string_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return [str(item) for item in value]


def _command(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return [str(item) for item in value]


def load_config(path: Path) -> ExperimentConfig:
    path = path.expanduser().resolve()
    raw: Dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    base = path.parent

    model_raw = raw.get("model", {}) or {}
    model = ModelConfig(
        name=str(model_raw.get("name", "")),
        temperature=float(model_raw.get("temperature", 0.8)),
        max_new_tokens=int(model_raw.get("max_new_tokens", 2048)),
        context_length=int(model_raw.get("context_length", 8192)),
        batch_size=int(model_raw.get("batch_size", 1)),
        gpu_devices=[int(x) for x in model_raw.get("gpu_devices", [0])],
        backend=str(model_raw.get("backend", "hf")),
    )

    runner_raw = raw.get("runner", {}) or {}
    work_dir = _as_path(base, str(runner_raw.get("work_dir", "runs/tagfuzz")))
    runner = RunnerConfig(
        work_dir=work_dir,
        compile_command=_command(runner_raw.get("compile_command")),
        coverage_command=_command(runner_raw.get("coverage_command")),
        command_cwd=_as_path(base, str(runner_raw.get("command_cwd", ".."))),
        crash_command=_command(runner_raw.get("crash_command")) or None,
        oracle_command=_command(runner_raw.get("oracle_command")) or None,
        timeout_seconds=int(runner_raw.get("timeout_seconds", 1200)),
    )

    tf_raw = raw.get("tagfuzz", {}) or {}
    tagfuzz = TAGFuzzConfig(
        targets_file=_as_path(base, str(tf_raw.get("targets_file", "targets/go/fse20.yaml"))),
        target_ids=_string_list(tf_raw.get("target_ids")),
        candidate_group_size=int(tf_raw.get("candidate_group_size", 8)),
        calls_budget=int(tf_raw.get("calls_budget", 0)),
        time_budget_seconds=int(tf_raw.get("time_budget_seconds", 0)),
        alpha=float(tf_raw.get("alpha", 1.0)),
        beta=float(tf_raw.get("beta", 0.5)),
        regression_lambda=float(tf_raw.get("regression_lambda", 0.5)),
        feedback_examples=int(tf_raw.get("feedback_examples", 3)),
        grpo_enabled=bool(tf_raw.get("grpo_enabled", False)),
        grpo_output=_as_path(work_dir, str(tf_raw.get("grpo_output", "grpo/updates.jsonl"))),
        seed_program=str(tf_raw.get("seed_program", "package main\nfunc main() {}\n")),
    )
    return ExperimentConfig(model=model, runner=runner, tagfuzz=tagfuzz)
