from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set

import yaml


@dataclass(frozen=True)
class SourceLocation:
    file: str = ""
    start_line: int = 0
    end_line: int = 0

    def contains(self, filename: str, line: int) -> bool:
        if not self.file or self.start_line <= 0:
            return False
        left = str(filename).replace("\\", "/")
        right = self.file.replace("\\", "/")
        return (left.endswith(right) or right.endswith(left)) and self.start_line <= int(line) <= self.end_line


@dataclass
class TAGNode:
    id: str
    kind: str
    description: str = ""
    source: SourceLocation = field(default_factory=SourceLocation)
    rule: Dict[str, Any] = field(default_factory=dict)
    guidance: str = ""


@dataclass
class TAGEdge:
    src: str
    dst: str


@dataclass
class TargetSpec:
    id: str
    name: str
    language: str
    source: SourceLocation
    requirement: str
    nodes: Dict[str, TAGNode]
    edges: List[TAGEdge]
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def target_node_id(self) -> str:
        for node in self.nodes.values():
            if node.kind == "target":
                return node.id
        return "target"

    def predecessors(self, node_id: str) -> Set[str]:
        return {edge.src for edge in self.edges if edge.dst == node_id}

    def successors(self, node_id: str) -> Set[str]:
        return {edge.dst for edge in self.edges if edge.src == node_id}

    def distance_to_target(self, node_id: str) -> int:
        target = self.target_node_id
        if node_id == target:
            return 0
        queue = deque([(node_id, 0)])
        seen = {node_id}
        while queue:
            cur, dist = queue.popleft()
            for nxt in self.successors(cur):
                if nxt == target:
                    return dist + 1
                if nxt not in seen:
                    seen.add(nxt)
                    queue.append((nxt, dist + 1))
        return 10_000


def _location(raw: Dict[str, Any]) -> SourceLocation:
    if not raw:
        return SourceLocation()
    return SourceLocation(
        file=str(raw.get("file", "")),
        start_line=int(raw.get("start_line", raw.get("line", 0)) or 0),
        end_line=int(raw.get("end_line", raw.get("line", raw.get("start_line", 0))) or 0),
    )


def _node(raw: Dict[str, Any]) -> TAGNode:
    return TAGNode(
        id=str(raw["id"]),
        kind=str(raw.get("kind", "requirement")),
        description=str(raw.get("description", "")),
        source=_location(raw.get("source", {}) or {}),
        rule=dict(raw.get("rule", {}) or {}),
        guidance=str(raw.get("guidance", "")),
    )


def _target(raw: Dict[str, Any]) -> TargetSpec:
    graph = raw.get("activation_graph", {}) or {}
    nodes = {_node(item).id: _node(item) for item in graph.get("nodes", [])}
    edges = [
        TAGEdge(src=str(item["from"]), dst=str(item["to"]))
        for item in graph.get("edges", [])
    ]
    target_id = str(raw["id"])
    if not any(node.kind == "target" for node in nodes.values()):
        nodes["target"] = TAGNode(
            id="target",
            kind="target",
            description=str(raw.get("name", target_id)),
            source=_location(raw.get("source", {}) or {}),
        )
    return TargetSpec(
        id=target_id,
        name=str(raw.get("name", target_id)),
        language=str(raw.get("language", "go")),
        source=_location(raw.get("source", {}) or {}),
        requirement=str(raw.get("requirement", "")),
        nodes=nodes,
        edges=edges,
        metadata=dict(raw.get("metadata", {}) or {}),
    )


class TargetSuite:
    def __init__(self, targets: Iterable[TargetSpec]):
        self.targets = list(targets)
        self.by_id = {target.id: target for target in self.targets}
        self.by_name = {target.name: target for target in self.targets}

    def select(self, ids: Iterable[str]) -> List[TargetSpec]:
        requested = list(ids or [])
        if not requested:
            return list(self.targets)
        selected = []
        for item in requested:
            if item in self.by_id:
                selected.append(self.by_id[item])
            elif item in self.by_name:
                selected.append(self.by_name[item])
            else:
                raise KeyError(f"unknown target: {item}")
        return selected


def load_targets(path: Path) -> TargetSuite:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    items = raw if isinstance(raw, list) else raw.get("targets", [])
    if not items:
        raise ValueError(f"no targets found in {path}")
    return TargetSuite(_target(item) for item in items)

