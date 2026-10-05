from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

CoverageLine = Tuple[str, int]


@dataclass
class CompileResult:
    returncode: int
    stdout: str
    stderr: str
    coverage: set[CoverageLine]
    crash: bool = False
    crash_reason: str = ""
    oracle: Dict = None

    @property
    def output(self) -> str:
        return (self.stdout or "") + "\n" + (self.stderr or "")


def expand_command(template: Iterable[str], **values) -> List[str]:
    return [str(part).format(**values) for part in template]


def run_command(command: List[str], cwd: Path, timeout: int) -> subprocess.CompletedProcess:
    return subprocess.run(
        command,
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout,
    )


def parse_coverage_json(text: str) -> set[CoverageLine]:
    try:
        raw = json.loads(text or "{}")
    except ValueError:
        return set()
    return {(str(path), int(line)) for path, line in raw.get("lines", [])}


GENERIC_CRASH_RE = re.compile(
    r"(?i)(internal compiler error|compiler: internal error|panic:|fatal error:|"
    r"nil pointer dereference|segmentation fault|sigsegv|sigbus|go tool compile: signal:)"
)


class CompilerRunner:
    def __init__(self, config):
        self.config = config
        self.work_dir = Path(config.work_dir)
        self.command_cwd = Path(config.command_cwd)
        self.work_dir.mkdir(parents=True, exist_ok=True)

    def compile(self, source: Path, case_id: str, target_id: str) -> CompileResult:
        values = {
            "work_dir": str(self.work_dir),
            "source": str(source),
            "case_id": case_id,
            "target_id": target_id,
        }
        compile_cmd = expand_command(self.config.compile_command, **values)
        proc = run_command(compile_cmd, cwd=self.command_cwd, timeout=self.config.timeout_seconds)
        coverage = self.coverage(case_id, target_id)
        output = (proc.stdout or "") + "\n" + (proc.stderr or "")
        crash = bool(GENERIC_CRASH_RE.search(output))
        reason = "generic compiler crash signature" if crash else ""
        return CompileResult(
            returncode=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
            coverage=coverage,
            crash=crash,
            crash_reason=reason,
            oracle={"status": "not_run"},
        )

    def coverage(self, case_id: str, target_id: str) -> set[CoverageLine]:
        if not self.config.coverage_command:
            return set()
        values = {
            "work_dir": str(self.work_dir),
            "case_id": case_id,
            "target_id": target_id,
        }
        cmd = expand_command(self.config.coverage_command, **values)
        proc = run_command(cmd, cwd=self.command_cwd, timeout=self.config.timeout_seconds)
        if proc.returncode != 0:
            return set()
        return parse_coverage_json(proc.stdout)
