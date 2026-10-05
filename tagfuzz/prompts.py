from __future__ import annotations

from typing import Iterable, List

from .activation import ActivationResult
from .tag_graph import TAGNode, TargetSpec


def _node_lines(target: TargetSpec, node_ids: Iterable[str]) -> List[str]:
    lines = []
    for node_id in sorted(node_ids):
        node = target.nodes[node_id]
        text = node.description or node.guidance or node.id
        lines.append(f"- {node.id} ({node.kind}): {text}")
    return lines


def build_tagfuzz_prompt(
    target: TargetSpec,
    current_program: str,
    activation: ActivationResult,
    examples: List[str] = None,
) -> str:
    examples = examples or []
    state = "\n".join(_node_lines(target, activation.state)) or "- none"
    frontier = "\n".join(_node_lines(target, activation.frontier)) or "- target may already be reached or TAG is blocked"
    features = ", ".join(sorted(activation.features)) or "none"
    rendered_examples = "\n\n".join(
        f"Useful previous candidate {idx}:\n```go\n{code.strip()}\n```"
        for idx, code in enumerate(examples, 1)
    ) or "- none"

    return f"""<|im_start|>system
You are TAGFuzz, a compiler directed-fuzzing agent. Generate exactly one
complete Go source file that advances the Target Activation Graph for the
requested Go compiler target. Output source only inside <code>...</code>.
<|im_end|>
<|im_start|>user
Target: {target.name}
Target id: {target.id}
Target requirement:
{target.requirement.strip()}

Already activated TAG nodes:
{state}

Current Activation Frontier:
{frontier}

Features detected in the current program: {features}

Current program:
```go
{current_program.strip()}
```

Useful prior candidates:
{rendered_examples}

Generate a fresh deterministic Go program that preserves activated conditions
when possible and focuses on satisfying the current Activation Frontier. Use
only the standard library, include package main and func main, avoid cgo, avoid
nondeterministic behavior, and do not explain the answer.

Strict output format: <code>...complete Go source...</code>
<|im_end|>
<|im_start|>assistant
"""

