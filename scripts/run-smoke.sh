#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

python -m tagfuzz.cli validate-targets targets/go/fse20.yaml
python -m tagfuzz.cli run configs/go-fse20.example.yaml \
  --target ssa_decompose_slice_phi \
  --budget-calls 2 \
  --work-dir runs/smoke

test -s runs/smoke/logs/candidate_rewards.jsonl
echo "TAGFuzz smoke test completed."

