#!/usr/bin/env bash
set -euo pipefail

WORK_DIR="${1:-}"
CASE_ID="${2:-case}"

GOROOT_DIR="${TAGFUZZ_GOROOT:-}"
if [ -z "$GOROOT_DIR" ] || [ ! -x "${GOROOT_DIR}/bin/go" ]; then
  printf '{"lines":[]}\n'
  exit 0
fi

RAW_DIR="${WORK_DIR}/go-coverdata/cases/${CASE_ID}/raw"
TEXT_FILE="${WORK_DIR}/go-coverdata/cases/${CASE_ID}/coverage.out"
if [ ! -d "$RAW_DIR" ] || ! compgen -G "${RAW_DIR}/covmeta.*" > /dev/null; then
  printf '{"lines":[]}\n'
  exit 0
fi

"${GOROOT_DIR}/bin/go" tool covdata textfmt -i="$RAW_DIR" -o="$TEXT_FILE" >/dev/null 2>&1 || {
  printf '{"lines":[]}\n'
  exit 0
}

python3 - "$TEXT_FILE" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
covered = set()
for raw in path.read_text(errors="replace").splitlines():
    line = raw.strip()
    if not line or line.startswith("mode:"):
        continue
    try:
        location, count_text = line.rsplit(" ", 1)
        if int(count_text) <= 0:
            continue
        filename, span = location.rsplit(":", 1)
        start, end = span.split(",", 1)
        first = int(start.split(".", 1)[0])
        last = int(end.split(".", 1)[0])
    except Exception:
        continue
    for lineno in range(first, last + 1):
        covered.add((filename, lineno))
print(json.dumps({"lines": sorted([list(item) for item in covered])}))
PY

