from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from .activation import ActivationResult, analyze_activation
from .compiler import CompilerRunner
from .config import ExperimentConfig
from .grpo import GRPOAdapter, GRPOSample
from .llm import BaseGenerator
from .prompts import build_tagfuzz_prompt
from .reward import activation_reward, relative_advantages
from .tag_graph import TargetSpec


@dataclass
class CandidateResult:
    case_id: str
    code: str
    activation: ActivationResult
    reward: float
    delta_state: float
    delta_distance: float
    compile_valid: bool
    compiler_crash: bool
    covered_lines: int


def append_jsonl(path: Path, item: Dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n")


class TAGFuzzEngine:
    def __init__(
        self,
        config: ExperimentConfig,
        generator: BaseGenerator,
        runner: CompilerRunner,
        grpo_adapter: Optional[GRPOAdapter] = None,
    ):
        self.config = config
        self.generator = generator
        self.runner = runner
        self.grpo_adapter = grpo_adapter
        self.work_dir = config.runner.work_dir
        self.codes_dir = self.work_dir / "codes"
        self.logs_dir = self.work_dir / "logs"
        self.codes_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.events_log = self.logs_dir / "events.jsonl"
        self.candidates_log = self.logs_dir / "candidate_rewards.jsonl"
        self.states_log = self.logs_dir / "tag_states.jsonl"
        for path in (self.events_log, self.candidates_log, self.states_log):
            path.write_text("", encoding="utf-8")

    def run_target(self, target: TargetSpec) -> Dict:
        start = time.time()
        calls = 0
        iteration = 0
        current_program = self.config.tagfuzz.seed_program
        current_activation = analyze_activation(target, current_program, set())
        examples: List[str] = []
        best_seen: Optional[CandidateResult] = None

        while True:
            if self.config.tagfuzz.calls_budget and calls >= self.config.tagfuzz.calls_budget:
                break
            if self.config.tagfuzz.time_budget_seconds and time.time() - start >= self.config.tagfuzz.time_budget_seconds:
                break
            if target.target_node_id in current_activation.state:
                break

            iteration += 1
            group_size = self.config.tagfuzz.candidate_group_size
            if self.config.tagfuzz.calls_budget:
                group_size = min(group_size, self.config.tagfuzz.calls_budget - calls)
            prompt = build_tagfuzz_prompt(target, current_program, current_activation, examples)
            generated = self.generator.generate_group(
                prompt,
                group_size,
                temperature=self.config.model.temperature,
            )
            calls += len(generated)

            candidates: List[CandidateResult] = []
            for idx, code in enumerate(generated, 1):
                case_id = f"{target.id}_iter{iteration:04d}_cand{idx:02d}"
                if not code:
                    append_jsonl(self.candidates_log, {
                        "case_id": case_id,
                        "target_id": target.id,
                        "status": "no_code",
                    })
                    continue
                source = self.codes_dir / f"{case_id}.go"
                source.write_text(code.strip() + "\n", encoding="utf-8")
                compile_result = self.runner.compile(source, case_id, target.id)
                activation = analyze_activation(
                    target,
                    code,
                    compile_result.coverage,
                    compiler_output=compile_result.output,
                )
                reward = activation_reward(
                    current_activation,
                    activation,
                    alpha=self.config.tagfuzz.alpha,
                    beta=self.config.tagfuzz.beta,
                    regression_lambda=self.config.tagfuzz.regression_lambda,
                )
                candidate = CandidateResult(
                    case_id=case_id,
                    code=code,
                    activation=activation,
                    reward=reward.reward,
                    delta_state=reward.delta_state,
                    delta_distance=reward.delta_distance,
                    compile_valid=compile_result.returncode == 0,
                    compiler_crash=compile_result.crash,
                    covered_lines=len(compile_result.coverage),
                )
                candidates.append(candidate)

            advantages = relative_advantages([item.reward for item in candidates])
            for candidate, advantage in zip(candidates, advantages):
                append_jsonl(self.candidates_log, {
                    "case_id": candidate.case_id,
                    "target_id": target.id,
                    "iteration": iteration,
                    "reward": candidate.reward,
                    "advantage": advantage,
                    "delta_state": candidate.delta_state,
                    "delta_distance": candidate.delta_distance,
                    "compile_valid": candidate.compile_valid,
                    "compiler_crash": candidate.compiler_crash,
                    "covered_lines": candidate.covered_lines,
                    "activation": candidate.activation.serializable(),
                })

            if self.config.tagfuzz.grpo_enabled and self.grpo_adapter and candidates:
                samples = [
                    GRPOSample(
                        prompt=prompt,
                        code=candidate.code,
                        reward=candidate.reward,
                        advantage=advantage,
                        metadata={
                            "case_id": candidate.case_id,
                            "target_id": target.id,
                            "iteration": iteration,
                            "delta_state": candidate.delta_state,
                            "delta_distance": candidate.delta_distance,
                            "compile_valid": candidate.compile_valid,
                            "compiler_crash": candidate.compiler_crash,
                        },
                    )
                    for candidate, advantage in zip(candidates, advantages)
                ]
                update_info = self.grpo_adapter.update(samples)
                append_jsonl(self.logs_dir / "grpo_updates.jsonl", update_info)

            if not candidates:
                continue
            selected = max(candidates, key=lambda item: (item.reward, len(item.activation.state), item.case_id))
            current_program = selected.code
            current_activation = selected.activation
            if selected.reward > 0:
                examples.append(selected.code)
                examples = examples[-self.config.tagfuzz.feedback_examples:]
            if best_seen is None or selected.reward > best_seen.reward:
                best_seen = selected

            event = {
                "target_id": target.id,
                "target_name": target.name,
                "iteration": iteration,
                "selected_case_id": selected.case_id,
                "model_calls": calls,
                "elapsed_seconds": round(time.time() - start, 3),
                "target_reached": target.target_node_id in selected.activation.state,
                "reward": selected.reward,
                "activation": selected.activation.serializable(),
            }
            append_jsonl(self.events_log, event)
            append_jsonl(self.states_log, event)

        return {
            "target_id": target.id,
            "target_name": target.name,
            "iterations": iteration,
            "model_calls": calls,
            "elapsed_seconds": round(time.time() - start, 3),
            "target_reached": target.target_node_id in current_activation.state,
            "final_activation": current_activation.serializable(),
            "best_case_id": best_seen.case_id if best_seen else "",
        }
