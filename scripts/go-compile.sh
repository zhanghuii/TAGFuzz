#!/usr/bin/env bash
set -uo pipefail

WORK_DIR="${1:-}"
SOURCE_FILE="${2:-}"
CASE_ID="${3:-case}"

if [ -z "$WORK_DIR" ] || [ -z "$SOURCE_FILE" ]; then
  echo "Usage: $0 <work_dir> <source_file> <case_id>" >&2
  exit 1
fi

GOROOT_DIR="${TAGFUZZ_GOROOT:-}"
if [ -z "$GOROOT_DIR" ]; then
  echo "TAGFUZZ_GOROOT is not set" >&2
  exit 0
fi

GO_BIN="${GOROOT_DIR}/bin/go"
if [ ! -x "$GO_BIN" ]; then
  echo "Go binary not found: $GO_BIN" >&2
  exit 1
fi

export GOROOT="$GOROOT_DIR"
export PATH="${GOROOT}/bin:$PATH"
export GOEXPERIMENT="${TAGFUZZ_GOEXPERIMENT:-coverageredesign}"

COVER_ROOT="${WORK_DIR}/go-coverdata/cases/${CASE_ID}"
RAW_DIR="${COVER_ROOT}/raw"
mkdir -p "$RAW_DIR"
rm -f "$RAW_DIR"/cov*
export GOCOVERDIR="$RAW_DIR"

BIN_DIR="${WORK_DIR}/bin"
mkdir -p "$BIN_DIR"
"$GO_BIN" build -o "${BIN_DIR}/${CASE_ID}" "$SOURCE_FILE"
RET=$?
rm -f "${BIN_DIR}/${CASE_ID}"
exit "$RET"

