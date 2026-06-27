#!/usr/bin/env bash
# Ghidra headless로 Low P-code JSON 추출 → 엔진 입력 레이아웃(samples/low_pcode/<arch>/)에 저장.
# 사용: bash scripts/extract_lowpcode.sh <arch> [profile]
#   arch: x86|x64|armv7|aarch64, profile: P0|P1
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$HERE"
source "$HERE/../tools/detect_env.sh"

ARCH="${1:-x64}"
PROFILE="${2:-P0}"
BIN="$HERE/build/$PROFILE/$ARCH/libtv2_cpp_like.so"
[ -f "$BIN" ] || { echo "build first: scripts/build_4arch.sh $PROFILE"; exit 1; }
[ -n "${GHIDRA_DIR:-}" ] || { echo "GHIDRA_DIR not found. Set GHIDRA_DIR or GHIDRA_INSTALL_DIR."; exit 1; }
[ -n "${TDO_DUMPER_DIR:-}" ] && [ -d "$TDO_DUMPER_DIR" ] || {
  echo "TDO_DUMPER_DIR not found. Set TDO_ENGINE_ROOT or TDO_DUMPER_DIR."
  exit 1
}

OUT="$HERE/samples/low_pcode/$ARCH"
[ "$PROFILE" = "P0" ] || OUT="$HERE/samples/low_pcode/${PROFILE}_${ARCH}"
PROJ_DIR="$HERE/build/ghidra_proj"
PROJ="tv2_${PROFILE}_${ARCH}"
mkdir -p "$PROJ_DIR" "$OUT"

if [ "$TV2_OS" = "windows" ]; then
  command -v cygpath >/dev/null || { echo "cygpath is required on Windows Git Bash"; exit 1; }
  AH_WIN="$(cygpath -w "$GHIDRA_DIR/support/analyzeHeadless.bat")"
  BIN_WIN="$(cygpath -w "$BIN")"
  DUMPER_DIR_WIN="$(cygpath -w "$TDO_DUMPER_DIR")"
  PROJ_WIN="$(cygpath -w "$PROJ_DIR")"
  OUT_WIN="$(cygpath -w "$OUT")"

  BAT="$HERE/build/_run_ah_${PROFILE}_${ARCH}.bat"
  cat > "$BAT" <<EOF
@echo off
"$AH_WIN" "$PROJ_WIN" $PROJ -import "$BIN_WIN" -overwrite ^
  -scriptPath "$DUMPER_DIR_WIN" ^
  -postScript lowpcode_json_dumper.py --output-root "$OUT_WIN" --root-prefix case_TV2C --max-depth 8 ^
  -deleteProject
EOF

  echo "=== extracting [$PROFILE/$ARCH] -> $OUT ==="
  MSYS_NO_PATHCONV=1 cmd.exe /c "$(cygpath -w "$BAT")"
else
  AH="$GHIDRA_DIR/support/analyzeHeadless"
  [ -x "$AH" ] || { echo "analyzeHeadless not executable: $AH"; exit 1; }
  echo "=== extracting [$PROFILE/$ARCH] -> $OUT ==="
  if [ -n "${GHIDRA_JAVA_HOME:-}" ]; then
    JAVA_HOME="$GHIDRA_JAVA_HOME" "$AH" "$PROJ_DIR" "$PROJ" -import "$BIN" -overwrite \
      -scriptPath "$TDO_DUMPER_DIR" \
      -postScript lowpcode_json_dumper.py --output-root "$OUT" --root-prefix case_TV2C --max-depth 8 \
      -deleteProject
  else
    "$AH" "$PROJ_DIR" "$PROJ" -import "$BIN" -overwrite \
      -scriptPath "$TDO_DUMPER_DIR" \
      -postScript lowpcode_json_dumper.py --output-root "$OUT" --root-prefix case_TV2C --max-depth 8 \
      -deleteProject
  fi
fi
echo "--- produced ---"
ls -1 "$OUT" 2>/dev/null | head
