from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, Iterable, List, Set, Tuple

from .features import extract_go_features, has_all
from .tag_graph import TAGNode, TargetSpec

CoverageLine = Tuple[str, int]


@dataclass
class ActivationResult:
    state: Set[str]
    frontier: Set[str]
    features: Set[str]
    node_status: Dict[str, bool]
    frontier_distance: int

    def serializable(self) -> Dict:
        return {
            "state": sorted(self.state),
            "frontier": sorted(self.frontier),
            "features": sorted(self.features),
            "node_status": dict(sorted(self.node_status.items())),
            "frontier_distance": self.frontier_distance,
        }


def _coverage_hits(location, coverage: Iterable[CoverageLine]) -> bool:
    return any(location.contains(path, line) for path, line in coverage)


def _regex_hits(pattern: str, text: str) -> bool:
    if not pattern:
        return False
    try:
        return re.search(pattern, text or "", flags=re.MULTILINE | re.DOTALL) is not None
    except re.error:
        return False


def _rule_active(node: TAGNode, code: str, features: Set[str], coverage: Set[CoverageLine], compiler_output: str) -> bool:
    rule = node.rule or {}
    if rule.get("any_features"):
        if not (features & set(rule.get("any_features") or [])):
            return False
    if rule.get("all_features") and not has_all(features, rule.get("all_features")):
        return False
    if rule.get("source_regex") and not _regex_hits(str(rule["source_regex"]), code):
        return False
    if rule.get("output_regex") and not _regex_hits(str(rule["output_regex"]), compiler_output):
        return False
    if rule.get("coverage") and not _coverage_hits(node.source, coverage):
        return False
    checks = [
        bool(rule.get("any_features")),
        bool(rule.get("all_features")),
        bool(rule.get("source_regex")),
        bool(rule.get("output_regex")),
        bool(rule.get("coverage")),
    ]
    return any(checks)


def analyze_activation(
    target: TargetSpec,
    code: str,
    coverage: Iterable[CoverageLine],
    compiler_output: str = "",
) -> ActivationResult:
    coverage_set = set(coverage or [])
    features = extract_go_features(code)
    status: Dict[str, bool] = {}
    for node_id, node in target.nodes.items():
        active = False
        if node.kind == "requirement":
            active = _rule_active(node, code, features, coverage_set, compiler_output)
        elif node.kind == "condition":
            active = _rule_active(node, code, features, coverage_set, compiler_output)
        elif node.kind in {"function", "callsite", "target"}:
            active = _coverage_hits(node.source, coverage_set)
            if not active:
                active = _rule_active(node, code, features, coverage_set, compiler_output)
        else:
            active = _rule_active(node, code, features, coverage_set, compiler_output)
        status[node_id] = active

    state = {node_id for node_id, active in status.items() if active}
    frontier = {
        node_id
        for node_id in target.nodes
        if node_id not in state and target.predecessors(node_id).issubset(state)
    }
    if frontier:
        distance = min(target.distance_to_target(node_id) for node_id in frontier)
    elif target.target_node_id in state:
        distance = 0
    else:
        distance = 10_000
    return ActivationResult(
        state=state,
        frontier=frontier,
        features=features,
        node_status=status,
        frontier_distance=distance,
    )

