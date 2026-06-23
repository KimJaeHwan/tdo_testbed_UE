#!/usr/bin/env bash
# Testbed V2 — 커버리지 일괄 실행: 남은 빌드 + 추출 + 엔진검증을 한 번에.
#  (A) Tier0 P1(-O2) 4-arch 빌드   (B) UE DebugGame(P0) 빌드
#  (C) 추출: cpp P0 x86/armv7/aarch64, cpp P1 x64, UE P0 x64
#  (D) 엔진 실행 → 통합 요약
# UE Android APK는 제외(무겁고 위험). 실패해도 다음 단계 계속.
set +e

ROOT="D:/01_gitproject/10_tdo_UE_testbed"
CPP="$ROOT/cpp_like"
UEDIR="$ROOT/unreal_playground/TraceUnrealPlayground"
NDK="$HOME/AppData/Local/Android/Sdk/ndk/25.1.8937393/toolchains/llvm/prebuilt/windows-x86_64/bin"
GHIDRA="C:/ghidra/ghidra_12.0_PUBLIC/ghidra_12.0_PUBLIC"
AH_WIN="$(cygpath -w "$GHIDRA/support/analyzeHeadless.bat")"
DUMPER_WIN="$(cygpath -w "D:/01_gitproject/11_tracing_Data_Origin_lowpcode/trace_data_origin_lowpcode/scripts")"
RUNV2="$CPP/tools/run_v2_engine.py"
DOTNET_DIR="C:\\Program Files\\Epic Games\\UE_5.1\\Engine\\Binaries\\ThirdParty\\DotNet\\6.0.302\\windows"
BUILD_BAT="C:\\Program Files\\Epic Games\\UE_5.1\\Engine\\Build\\BatchFiles\\Build.bat"

ghidra_extract() {  # $1=binary(win path) $2=outdir(unix) $3=projname $4=prefix
  local bin_win="$1" out="$2" proj="$3" prefix="$4"
  local out_win proj_win bat
  mkdir -p "$out" "$ROOT/build_ghidra_proj"
  out_win="$(cygpath -w "$out")"
  proj_win="$(cygpath -w "$ROOT/build_ghidra_proj")"
  bat="$ROOT/build_ghidra_proj/_ah_${proj}.bat"
  cat > "$bat" <<EOF
@echo off
"$AH_WIN" "$proj_win" $proj -import "$bin_win" -overwrite ^
  -scriptPath "$DUMPER_WIN" ^
  -postScript lowpcode_json_dumper.py --output-root "$out_win" --root-prefix $prefix --max-depth 8 ^
  -deleteProject
EOF
  echo ">>> EXTRACT $proj -> $out"
  MSYS_NO_PATHCONV=1 cmd.exe /c "$(cygpath -w "$bat")" 2>&1 | grep -iE "success=|fail=" | tail -2
}

echo "============================================================"
echo "(A) Tier0 P1(-O2) 4-arch 빌드"
echo "============================================================"
bash "$CPP/scripts/build_4arch.sh" P1 2>&1 | grep -iE "===|done|error" | tail -8

echo "============================================================"
echo "(B) UE DebugGame(P0) 빌드"
echo "============================================================"
UPROJ_WIN="$(cygpath -w "$UEDIR/TraceUnrealPlayground.uproject")"
cat > "$UEDIR/_build_debuggame.bat" <<EOF
@echo off
set "DOTNET_ROOT=$DOTNET_DIR"
set "PATH=$DOTNET_DIR;%PATH%"
call "$BUILD_BAT" TraceUnrealPlaygroundEditor Win64 DebugGame -project="$UPROJ_WIN" -waitmutex -NoHotReloadFromIDE
EOF
MSYS_NO_PATHCONV=1 cmd.exe /c "$(cygpath -w "$UEDIR/_build_debuggame.bat")" 2>&1 | grep -iE "Compile Trace|Link .*\.dll|error|Total execution" | tail -10

echo "============================================================"
echo "(C) 추출"
echo "============================================================"
# cpp Tier0 P0 — 빠진 3 arch
for a in x86 armv7 aarch64; do
  ghidra_extract "$(cygpath -w "$CPP/build/P0/$a/libtv2_cpp_like.so")" "$CPP/samples/low_pcode/$a" "cpp_p0_$a" "case_TV2"
done
# cpp Tier0 P1 x64
ghidra_extract "$(cygpath -w "$CPP/build/P1/x64/libtv2_cpp_like.so")" "$CPP/samples/low_pcode/P1_x64" "cpp_p1_x64" "case_TV2"
# UE DebugGame(P0) x64
UE_DBG_DLL="$UEDIR/Binaries/Win64/UnrealEditor-TraceUnrealPlayground-Win64-DebugGame.dll"
[ -f "$UE_DBG_DLL" ] || UE_DBG_DLL="$(ls "$UEDIR/Binaries/Win64/"*DebugGame*.dll 2>/dev/null | head -1)"
ghidra_extract "$(cygpath -w "$UE_DBG_DLL")" "$UEDIR/samples/low_pcode_P0" "ue_p0_x64" "case_TV2"

echo "============================================================"
echo "(D) 엔진 실행 — 통합 요약"
echo "============================================================"
echo "### Tier0 cpp — P0 (x86)";    python "$RUNV2" "$CPP/samples/low_pcode/x86"     "$CPP/expected/tv2_cpp_like.expected.json" 2>&1 | grep -E "counts|FAIL|PASS" | tail -14
echo "### Tier0 cpp — P0 (armv7)";  python "$RUNV2" "$CPP/samples/low_pcode/armv7"   "$CPP/expected/tv2_cpp_like.expected.json" 2>&1 | grep -E "counts"
echo "### Tier0 cpp — P0 (aarch64)";python "$RUNV2" "$CPP/samples/low_pcode/aarch64" "$CPP/expected/tv2_cpp_like.expected.json" 2>&1 | grep -E "counts"
echo "### Tier0 cpp — P1 (x64,-O2)";python "$RUNV2" "$CPP/samples/low_pcode/P1_x64"  "$CPP/expected/tv2_cpp_like.expected.json" 2>&1 | grep -E "counts|FAIL"
echo "### UE Tier2/3 — P0 DebugGame (x64)"; python "$RUNV2" "$UEDIR/samples/low_pcode_P0" "$ROOT/unreal_playground/expected/tv2_unreal.expected.json" 2>&1 | grep -E "counts|PASS|FAIL"
echo "[ALL DONE]"
