#!/usr/bin/env bash
set -euo pipefail

GO_VERSION="${GO_VERSION:-1.20.6}"
PREFIX="${1:-$PWD/toolchains/go${GO_VERSION}-tagfuzz}"
WORK_ROOT="${PREFIX}/srcroot"
BOOTSTRAP="${PREFIX}/bootstrap"
GOROOT_DIR="${PREFIX}/goroot"

mkdir -p "$PREFIX"

download() {
  local url="$1"
  local out="$2"
  if command -v curl >/dev/null 2>&1; then
    curl -L "$url" -o "$out"
  else
    wget "$url" -O "$out"
  fi
}

if [ ! -d "$BOOTSTRAP/go" ]; then
  mkdir -p "$BOOTSTRAP"
  TARBALL="${BOOTSTRAP}/go${GO_VERSION}.linux-amd64.tar.gz"
  if [ ! -f "$TARBALL" ]; then
    download "https://go.dev/dl/go${GO_VERSION}.linux-amd64.tar.gz" "$TARBALL"
  fi
  tar -C "$BOOTSTRAP" -xzf "$TARBALL"
fi

if [ ! -d "$GOROOT_DIR" ]; then
  mkdir -p "$WORK_ROOT"
  SRC_TARBALL="${WORK_ROOT}/go${GO_VERSION}.src.tar.gz"
  if [ ! -f "$SRC_TARBALL" ]; then
    download "https://go.dev/dl/go${GO_VERSION}.src.tar.gz" "$SRC_TARBALL"
  fi
  tar -C "$WORK_ROOT" -xzf "$SRC_TARBALL"
  mv "$WORK_ROOT/go" "$GOROOT_DIR"
fi

export GOROOT_BOOTSTRAP="${BOOTSTRAP}/go"
export PATH="${GOROOT_BOOTSTRAP}/bin:$PATH"
export GOEXPERIMENT=coverageredesign

cd "${GOROOT_DIR}/src"
./make.bash

GO_BIN="${GOROOT_DIR}/bin/go"
GOOS_VALUE="$("$GO_BIN" env GOOS)"
GOARCH_VALUE="$("$GO_BIN" env GOARCH)"
TOOLDIR="${GOROOT_DIR}/pkg/tool/${GOOS_VALUE}_${GOARCH_VALUE}"
ORIG_COMPILE="${TOOLDIR}/compile"
BACKUP_COMPILE="${TOOLDIR}/compile.orig"
COVER_COMPILE="${TOOLDIR}/compile.cover"
COVERPKG_LIST="${PREFIX}/go-coverpkg.txt"

if [ ! -f "$BACKUP_COMPILE" ]; then
  cp "$ORIG_COMPILE" "$BACKUP_COMPILE"
fi

cd "${GOROOT_DIR}/src"
"$GO_BIN" list \
  cmd/compile/... \
  cmd/internal/... \
  internal/abi \
  internal/buildcfg \
  internal/coverage/... \
  internal/goarch \
  internal/goexperiment \
  internal/goversion \
  internal/platform \
  > "$COVERPKG_LIST"

COVERPKG="$(paste -sd, "$COVERPKG_LIST")"
"$GO_BIN" build \
  -cover \
  -covermode=atomic \
  -coverpkg="$COVERPKG" \
  -o "$COVER_COMPILE" \
  cmd/compile

cp "$COVER_COMPILE" "$ORIG_COMPILE"
chmod +x "$ORIG_COMPILE" "$COVER_COMPILE" "$BACKUP_COMPILE"

cat <<EOF
Instrumented Go compiler is ready.
export TAGFUZZ_GOROOT=${GOROOT_DIR}
EOF
