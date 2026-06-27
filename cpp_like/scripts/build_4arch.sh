#!/usr/bin/env bash
# Testbed V2 Tier0 — NDK clang 단일 툴체인으로 x86/x64/armv7/aarch64 빌드 (P0 = Debug/-O0 -g)
# 산출물: build/P0/<arch>/libtv2_cpp_like.so (ELF). Ghidra Low P-code 추출 대상.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$HERE"
source "$HERE/../tools/detect_env.sh"

[ -x "$NDK_CLANG" ] || { echo "ERROR: NDK clang not found. Set ANDROID_NDK_HOME."; exit 1; }

PROFILE="${1:-P0}"
case "$PROFILE" in
  P0) OPT="-O0 -g" ;;
  P1) OPT="-O2 -g" ;;
  *)  echo "unknown profile $PROFILE (use P0|P1)"; exit 1 ;;
esac

for arch in x86 x64 armv7 aarch64; do
  T="$(tv2_target_triple "$arch")" || { echo "unknown arch: $arch"; exit 1; }
  OUT="build/$PROFILE/$arch"
  mkdir -p "$OUT"
  echo "=== [$PROFILE/$arch] target=$T ==="
  "$NDK_CLANG" --target="$T" -fPIC $OPT -I include -c src/tv2_sources_sinks.c -o "$OUT/ss.o"
  "$NDK_CLANG" --target="$T" -fPIC $OPT -fno-exceptions -fno-rtti -x c++ -I include \
           -c src/cases_fusion.cpp -o "$OUT/cases.o"
  "$NDK_CLANG" --target="$T" -shared -o "$OUT/libtv2_cpp_like.so" "$OUT/ss.o" "$OUT/cases.o"
  echo "    -> $OUT/libtv2_cpp_like.so"
done

echo "[done] $PROFILE build complete."
