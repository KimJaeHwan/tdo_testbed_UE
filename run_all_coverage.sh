#!/usr/bin/env bash
# Testbed V2 coverage runner: build, extract low-pcode, and run the engine.
#
# The script is intentionally environment-driven.  It works from a checkout
# next to lowpcode_data_origin, and also supports explicit overrides:
#   ANDROID_NDK_HOME=... GHIDRA_DIR=... TDO_ENGINE_ROOT=... ./run_all_coverage.sh
set +e

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CPP="$ROOT/cpp_like"
UEPROJ="$ROOT/unreal_playground/TraceUnrealPlayground"
RUNV2="$CPP/tools/run_v2_engine.py"
source "$ROOT/tools/detect_env.sh"

run_step() {
  echo
  echo "============================================================"
  echo "$1"
  echo "============================================================"
}

run_engine() {
  local label="$1" samples="$2" expected="$3"
  echo "### $label"
  if [ ! -d "$samples" ]; then
    echo "skip: no samples at $samples"
    return 0
  fi
  python3 "$RUNV2" "$samples" "$expected" 2>&1 | grep -E "counts|FAIL|ERROR|PASS" | tail -20
}

extract_tier0() {
  local arch="$1" profile="$2"
  bash "$CPP/scripts/extract_lowpcode.sh" "$arch" "$profile" 2>&1 | grep -iE "success=|fail=|ERROR|Exception|produced|extracting" | tail -20
}

extract_binary() {
  local binary="$1" out="$2" proj="$3" prefix="$4"
  [ -f "$binary" ] || { echo "skip: binary not found: $binary"; return 0; }
  [ -n "${GHIDRA_DIR:-}" ] || { echo "skip: GHIDRA_DIR missing"; return 0; }
  [ -n "${TDO_DUMPER_DIR:-}" ] && [ -d "$TDO_DUMPER_DIR" ] || { echo "skip: TDO_DUMPER_DIR missing"; return 0; }
  mkdir -p "$out" "$ROOT/build_ghidra_proj"

  if [ "$TV2_OS" = "windows" ]; then
    local ah_win bin_win out_win proj_win dumper_win bat
    ah_win="$(cygpath -w "$GHIDRA_DIR/support/analyzeHeadless.bat")"
    bin_win="$(cygpath -w "$binary")"
    out_win="$(cygpath -w "$out")"
    proj_win="$(cygpath -w "$ROOT/build_ghidra_proj")"
    dumper_win="$(cygpath -w "$TDO_DUMPER_DIR")"
    bat="$ROOT/build_ghidra_proj/_ah_${proj}.bat"
    cat > "$bat" <<EOF
@echo off
"$ah_win" "$proj_win" $proj -import "$bin_win" -overwrite ^
  -scriptPath "$dumper_win" ^
  -postScript lowpcode_json_dumper.py --output-root "$out_win" --root-prefix $prefix --max-depth 8 ^
  -deleteProject
EOF
    MSYS_NO_PATHCONV=1 cmd.exe /c "$(cygpath -w "$bat")" 2>&1 | grep -iE "success=|fail=|ERROR|Exception" | tail -20
  else
    local ah="$GHIDRA_DIR/support/analyzeHeadless"
    [ -x "$ah" ] || { echo "skip: analyzeHeadless not executable: $ah"; return 0; }
    if [ -n "${GHIDRA_JAVA_HOME:-}" ]; then
      JAVA_HOME="$GHIDRA_JAVA_HOME" "$ah" "$ROOT/build_ghidra_proj" "$proj" -import "$binary" -overwrite \
        -scriptPath "$TDO_DUMPER_DIR" \
        -postScript lowpcode_json_dumper.py --output-root "$out" --root-prefix "$prefix" --max-depth 8 \
        -deleteProject 2>&1 | grep -iE "success=|fail=|ERROR|Exception" | tail -20
    else
      "$ah" "$ROOT/build_ghidra_proj" "$proj" -import "$binary" -overwrite \
        -scriptPath "$TDO_DUMPER_DIR" \
        -postScript lowpcode_json_dumper.py --output-root "$out" --root-prefix "$prefix" --max-depth 8 \
        -deleteProject 2>&1 | grep -iE "success=|fail=|ERROR|Exception" | tail -20
    fi
  fi
}

run_step "Environment"
tv2_env_summary

run_step "Tier0 build: P0 and P1"
bash "$ROOT/build.sh" tier0 P0
P0_STATUS=$?
bash "$ROOT/build.sh" tier0 P1
P1_STATUS=$?

run_step "Tier0 extract"
if [ "$P0_STATUS" -eq 0 ]; then
  for arch in x86 x64 armv7 aarch64; do
    extract_tier0 "$arch" P0
  done
else
  echo "skip P0 extraction: Tier0 P0 build failed"
fi
if [ "$P1_STATUS" -eq 0 ]; then
  extract_tier0 x64 P1
else
  echo "skip P1 extraction: Tier0 P1 build failed"
fi

run_step "UE build and extract"
if [ -n "${UE_ROOT:-}" ] && [ -d "$UE_ROOT" ]; then
  bash "$ROOT/build.sh" ue P0
  UE_STATUS=$?
  if [ "$UE_STATUS" -eq 0 ]; then
    UE_BIN="$(find "$UEPROJ/Binaries" -type f \( -name '*TraceUnrealPlayground*.dll' -o -name '*TraceUnrealPlayground*.dylib' -o -name '*TraceUnrealPlayground*.so' \) 2>/dev/null | head -1)"
    extract_binary "$UE_BIN" "$UEPROJ/samples/low_pcode_P0" "ue_p0" "case_TV2"
  else
    echo "skip UE extraction: UE build failed"
  fi
else
  echo "skip UE build: UE_ROOT missing"
fi

run_step "Engine verification"
run_engine "Tier0 cpp P0 x64" "$CPP/samples/low_pcode/x64" "$CPP/expected/tv2_cpp_like.expected.json"
run_engine "Tier0 cpp P0 x86" "$CPP/samples/low_pcode/x86" "$CPP/expected/tv2_cpp_like.expected.json"
run_engine "Tier0 cpp P0 armv7" "$CPP/samples/low_pcode/armv7" "$CPP/expected/tv2_cpp_like.expected.json"
run_engine "Tier0 cpp P0 aarch64" "$CPP/samples/low_pcode/aarch64" "$CPP/expected/tv2_cpp_like.expected.json"
run_engine "Tier0 cpp P1 x64" "$CPP/samples/low_pcode/P1_x64" "$CPP/expected/tv2_cpp_like.expected.json"
run_engine "UE P0" "$UEPROJ/samples/low_pcode_P0" "$ROOT/unreal_playground/expected/tv2_unreal.expected.json"

run_step "Failure report"
python3 "$ROOT/tools/collect_failures.py"
