#!/usr/bin/env bash
# Unreal Testbed V2 — Ghidra headless Low P-code extraction for local UE build outputs.
# Usage: bash unreal_playground/scripts/extract_lowpcode.sh [P0|P1]
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
cd "$HERE"
source "$ROOT/tools/detect_env.sh"
PYTHON_BIN="${PYTHON_BIN:-python3}"

PROFILE="${1:-P0}"
case "$PROFILE" in
  P0)
    UE_CONFIG="DebugGame"
    BIN="$HERE/TraceUnrealPlayground/Binaries/Mac/libUnrealEditor-TraceUnrealPlayground-Mac-DebugGame.dylib"
    OUT="$HERE/TraceUnrealPlayground/samples/low_pcode_P0"
    ;;
  P1)
    UE_CONFIG="Development"
    BIN="$HERE/TraceUnrealPlayground/Binaries/Mac/libUnrealEditor-TraceUnrealPlayground.dylib"
    OUT="$HERE/TraceUnrealPlayground/samples/low_pcode"
    ;;
  *)
    echo "profile must be P0 or P1"
    exit 1
    ;;
esac

[ -f "$BIN" ] || { echo "build first: bash build.sh ue $PROFILE"; exit 1; }
[ -n "${GHIDRA_DIR:-}" ] || { echo "GHIDRA_DIR not found. Set GHIDRA_DIR or GHIDRA_INSTALL_DIR."; exit 1; }
[ -n "${TDO_DUMPER_DIR:-}" ] && [ -d "$TDO_DUMPER_DIR" ] || {
  echo "TDO_DUMPER_DIR not found. Set TDO_ENGINE_ROOT or TDO_DUMPER_DIR."
  exit 1
}

PROJ_DIR="$HERE/TraceUnrealPlayground/Build/GhidraProjects"
PROJ="tv2_ue58_mac_${PROFILE}"
mkdir -p "$PROJ_DIR" "$OUT"

# Avoid stale local samples being mistaken for fresh UE build results.
find "$OUT" -maxdepth 1 -type f \( -name 'case_TV2*_low_pcode.json' -o -name '*_low_pcode.json' -o -name 'low_pcode_extraction_manifest.json' \) -delete

if [ "$TV2_OS" = "windows" ]; then
  echo "UE local extraction currently targets Mac UE 5.8 dylib outputs."
  exit 1
fi

AH="$GHIDRA_DIR/support/analyzeHeadless"
[ -x "$AH" ] || { echo "analyzeHeadless not executable: $AH"; exit 1; }

echo "=== extracting UE [$PROFILE/$UE_CONFIG] -> $OUT ==="
if [ -n "${GHIDRA_JAVA_HOME:-}" ]; then
  JAVA_HOME="$GHIDRA_JAVA_HOME" "$AH" "$PROJ_DIR" "$PROJ" -import "$BIN" -overwrite \
    -scriptPath "$TDO_DUMPER_DIR" \
    -postScript lowpcode_json_dumper.py --output-dir "$OUT" --root-prefix _case_TV2 --max-depth 8 \
    -deleteProject
else
  "$AH" "$PROJ_DIR" "$PROJ" -import "$BIN" -overwrite \
    -scriptPath "$TDO_DUMPER_DIR" \
    -postScript lowpcode_json_dumper.py --output-dir "$OUT" --root-prefix _case_TV2 --max-depth 8 \
    -deleteProject
fi

"$PYTHON_BIN" "$HERE/tools/normalize_macho_lowpcode.py" "$OUT"

echo "--- produced ---"
find "$OUT" -maxdepth 1 -type f -name 'case_TV2*_low_pcode.json' | sort | sed 's#^#  #'
