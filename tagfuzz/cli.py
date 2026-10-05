from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

from .compiler import CompilerRunner
from .config import load_config
from .engine import TAGFuzzEngine
from .grpo import build_grpo_adapter
from .llm import build_generator
from .tag_graph import load_targets


def run(args) -> int:
    config = load_config(Path(args.config))
    if args.target:
        config.tagfuzz.target_ids = [args.target]
    if args.budget_calls is not None:
        config.tagfuzz.calls_budget = int(args.budget_calls)
    if args.work_dir:
        config.runner.work_dir = Path(args.work_dir).expanduser().resolve()
    suite = load_targets(config.tagfuzz.targets_file)
    targets = suite.select(config.tagfuzz.target_ids)
    generator = build_generator(config.model)
    runner = CompilerRunner(config.runner)
    grpo_adapter = build_grpo_adapter(config.tagfuzz) if config.tagfuzz.grpo_enabled else None
    engine = TAGFuzzEngine(config, generator, runner, grpo_adapter=grpo_adapter)
    summaries = [engine.run_target(target) for target in targets]
    print(json.dumps(summaries, indent=2, ensure_ascii=False))
    return 0


def validate_targets(args) -> int:
    suite = load_targets(Path(args.targets))
    errors = []
    for target in suite.targets:
        if target.target_node_id not in target.nodes:
            errors.append(f"{target.id}: missing target node")
        for edge in target.edges:
            if edge.src not in target.nodes:
                errors.append(f"{target.id}: edge source not found: {edge.src}")
            if edge.dst not in target.nodes:
                errors.append(f"{target.id}: edge destination not found: {edge.dst}")
        if not target.requirement.strip():
            errors.append(f"{target.id}: missing requirement")
    result = {
        "targets": len(suite.targets),
        "errors": errors,
        "ok": not errors,
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if not errors else 1


def package_release(args) -> int:
    script = Path(__file__).resolve().parents[1] / "scripts" / "package_release.py"
    cmd = [sys.executable, str(script), "--output", args.output]
    proc = subprocess.run(cmd, text=True)
    return int(proc.returncode)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="tagfuzz")
    sub = parser.add_subparsers(dest="command", required=True)
    run_p = sub.add_parser("run", help="run TAGFuzz")
    run_p.add_argument("config")
    run_p.add_argument("--target", default="")
    run_p.add_argument("--budget-calls", type=int, default=None)
    run_p.add_argument("--work-dir", default="")
    run_p.set_defaults(func=run)

    validate_p = sub.add_parser("validate-targets", help="validate TAG target YAML")
    validate_p.add_argument("targets")
    validate_p.set_defaults(func=validate_targets)

    package_p = sub.add_parser("package", help="build a clean TAGFuzz release zip")
    package_p.add_argument("--output", default="TAGFuzz-release.zip")
    package_p.set_defaults(func=package_release)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
