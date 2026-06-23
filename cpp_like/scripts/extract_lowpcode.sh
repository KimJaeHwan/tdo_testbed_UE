#!/usr/bin/env bash
# Ghidra headless로 Low P-code JSON 추출 → 11_엔진 입력 레이아웃(samples/low_pcode/<arch>/)에 저장.
# 사용: bash scripts/extract_lowpcode.sh <arch>   (arch: x86|x64|armv7|aarch64)
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$HERE"

ARCH="${1:-x64}"
SO_WIN="$(cygpath -w "$HERE/build/P0/$ARCH/libtv2_cpp_like.so")"
[ -f "$HERE/build/P0/$ARCH/libtv2_cpp_like.so" ] || { echo "build first: scripts/build_4arch.sh"; exit 1; }

GHIDRA="${GHIDRA_INSTALL_DIR:-C:/ghidra/ghidra_12.0_PUBLIC/ghidra_12.0_PUBLIC}"
AH_WIN="$(cygpath -w "$GHIDRA/support/analyzeHeadless.bat")"
DUMPER_DIR_WIN="$(cygpath -w "D:/01_gitproject/11_tracing_Data_Origin_lowpcode/trace_data_origin_lowpcode/scripts")"

PROJ_WIN="$(cygpath -w "$HERE/build/ghidra_proj")"
OUT="$HERE/samples/low_pcode/$ARCH"
OUT_WIN="$(cygpath -w "$OUT")"
mkdir -p "$HERE/build/ghidra_proj" "$OUT"

BAT="$HERE/build/_run_ah_${ARCH}.bat"
cat > "$BAT" <<EOF
@echo off
"$AH_WIN" "$PROJ_WIN" tv2_${ARCH} -import "$SO_WIN" -overwrite ^
  -scriptPath "$DUMPER_DIR_WIN" ^
  -postScript lowpcode_json_dumper.py --output-root "$OUT_WIN" --root-prefix case_TV2C --max-depth 8 ^
  -deleteProject
EOF

echo "=== extracting [$ARCH] -> $OUT ==="
MSYS_NO_PATHCONV=1 cmd.exe /c "$(cygpath -w "$BAT")"
echo "--- produced ---"
ls -1 "$OUT" 2>/dev/null | head
