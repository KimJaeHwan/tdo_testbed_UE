#!/usr/bin/env bash
# Testbed V2 — 원커맨드 빌드 (Windows: Git Bash / macOS: Terminal 공용)
#
#   ./build.sh            # 전부: Tier0(P0) + UE(P0)
#   ./build.sh tier0      # Tier0만 (NDK clang, x86/x64/armv7/aarch64)
#   ./build.sh ue         # UE 모듈만
#   ./build.sh all P1     # 프로파일 지정 (P0=Debug/-O0/DebugGame, P1=Release/-O2/Development)
#   ./build.sh env        # 환경 탐지 결과만 출력
#
# 툴체인 경로는 자동 탐지. 필요시 오버라이드:
#   ANDROID_NDK_HOME=... UE_ROOT=... ./build.sh
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"
source "$HERE/tools/detect_env.sh"

TARGET="${1:-all}"
PROFILE="${2:-P0}"
case "$PROFILE" in
	P0) CC_OPT="-O0 -g"; UE_CONFIG="DebugGame" ;;
	P1) CC_OPT="-O2 -g"; UE_CONFIG="Development" ;;
	*) echo "프로파일은 P0|P1"; exit 1 ;;
esac

declare -A TRIPLE=(
	[x86]="i686-linux-android24"
	[x64]="x86_64-linux-android24"
	[armv7]="armv7a-linux-androideabi24"
	[aarch64]="aarch64-linux-android24"
)

build_tier0() {
	[ -x "$NDK_CLANG" ] || { echo "!! NDK clang 없음 ($NDK_CLANG). ANDROID_NDK_HOME 설정 필요."; return 1; }
	local cpp="$HERE/cpp_like"
	for arch in x86 x64 armv7 aarch64; do
		local t="${TRIPLE[$arch]}" out="$cpp/build/$PROFILE/$arch"
		mkdir -p "$out"
		echo "  [Tier0 $PROFILE/$arch] $t"
		"$NDK_CLANG" --target="$t" -fPIC $CC_OPT -I "$cpp/include" -c "$cpp/src/tv2_sources_sinks.c" -o "$out/ss.o"
		"$NDK_CLANG" --target="$t" -fPIC $CC_OPT -fno-exceptions -fno-rtti -x c++ -I "$cpp/include" -c "$cpp/src/cases_fusion.cpp" -o "$out/cases.o"
		"$NDK_CLANG" --target="$t" -shared -o "$out/libtv2_cpp_like.so" "$out/ss.o" "$out/cases.o"
	done
	python "$cpp/tools/generate_expected_from_manifest.py"
	echo "  -> $cpp/build/$PROFILE/<arch>/libtv2_cpp_like.so"
}

build_ue() {
	[ -n "${UE_ROOT:-}" ] && [ -d "$UE_ROOT" ] || { echo "!! UE_ROOT 없음. UE_ROOT 설정 필요."; return 1; }
	local uedir="$HERE/unreal_playground/TraceUnrealPlayground"
	local uproj="$uedir/TraceUnrealPlayground.uproject"
	python "$HERE/unreal_playground/tools/generate_expected_from_manifest.py"
	if [ "$TV2_OS" = "mac" ]; then
		echo "  [UE $UE_CONFIG / Mac]"
		"$UE_ROOT/Engine/Build/BatchFiles/Mac/Build.sh" TraceUnrealPlaygroundEditor Mac "$UE_CONFIG" -project="$uproj" -waitmutex
	else
		echo "  [UE $UE_CONFIG / Win64]"
		local dn="$UE_ROOT/Engine/Binaries/ThirdParty/DotNet/6.0.302/windows"
		local dn_win bb_win uproj_win bat
		dn_win="$(cygpath -w "$dn")"; bb_win="$(cygpath -w "$UE_ROOT/Engine/Build/BatchFiles/Build.bat")"
		uproj_win="$(cygpath -w "$uproj")"; bat="$uedir/_build_${UE_CONFIG}.bat"
		cat > "$bat" <<EOF
@echo off
set "DOTNET_ROOT=$dn_win"
set "PATH=$dn_win;%PATH%"
call "$bb_win" TraceUnrealPlaygroundEditor Win64 $UE_CONFIG -project="$uproj_win" -waitmutex -NoHotReloadFromIDE
EOF
		MSYS_NO_PATHCONV=1 cmd.exe /c "$(cygpath -w "$bat")"
	fi
	echo "  -> $uedir/Binaries/"
}

echo "== Testbed V2 build ($TARGET, $PROFILE) =="
tv2_env_summary
echo "-----------------------------------------"
case "$TARGET" in
	env)   : ;;
	tier0) build_tier0 ;;
	ue)    build_ue ;;
	all)   build_tier0; build_ue ;;
	*) echo "사용: ./build.sh [all|tier0|ue|env] [P0|P1]"; exit 1 ;;
esac
echo "== done =="
