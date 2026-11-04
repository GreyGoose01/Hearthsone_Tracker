#!/usr/bin/env bash
# Builds AutoTavern's compiled simulator for bundling into the .deb.
#   packaging/build-autotavern.sh [OUT_DIR]   (default: dist/autotavern)
# Needs git, rustup and python3 with pip. Produces OUT_DIR/_core.abi3.so (stripped)
# plus AutoTavern's LICENSE and NOTICE. packaging/build-deb.sh picks them up via
# AUTOTAVERN_DIR=OUT_DIR.
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck source=autotavern.env
source packaging/autotavern.env
OUT=$(realpath -m "${1:-dist/autotavern}")
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

git init -q "$WORK/src"
git -C "$WORK/src" fetch -q --depth 1 "$AUTOTAVERN_REPO" "$AUTOTAVERN_REF"
git -C "$WORK/src" checkout -q FETCH_HEAD

rustup toolchain install "$AUTOTAVERN_RUST" --profile minimal >/dev/null
# CI keeps the compiled crates between runs here
export CARGO_TARGET_DIR="${CARGO_TARGET_DIR:-$WORK/target}"
python3 -m venv "$WORK/venv"
"$WORK/venv/bin/pip" install -q "maturin>=1.15,<2"
(cd "$WORK/src" && RUSTUP_TOOLCHAIN="$AUTOTAVERN_RUST" "$WORK/venv/bin/maturin" build --release --strip \
    --compatibility off --out "$WORK/wheels" >/dev/null)

mkdir -p "$OUT"
python3 - "$WORK/wheels" "$OUT" <<'PY'
import sys, zipfile
from pathlib import Path
wheel = next(Path(sys.argv[1]).glob("*.whl"))
with zipfile.ZipFile(wheel) as z:
    name = next(n for n in z.namelist() if n.startswith("taverngym/_core") and n.endswith(".so"))
    Path(sys.argv[2], "_core.abi3.so").write_bytes(z.read(name))
PY
cp "$WORK/src/LICENSE" "$OUT/LICENSE"
cp "$WORK/src/NOTICE" "$OUT/NOTICE"
echo "$AUTOTAVERN_REF" > "$OUT/REVISION"
ls -la "$OUT"
