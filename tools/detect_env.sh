#!/usr/bin/env bash
# detect_env.sh — OS와 툴체인(NDK clang / Unreal / Ghidra)을 자동 탐지한다. source 해서 사용.
# 오버라이드: ANDROID_NDK_HOME, UE_ROOT, GHIDRA_DIR 환경변수가 있으면 그것을 우선한다.

# ── OS ────────────────────────────────────────────────
case "$(uname -s)" in
	MINGW*|MSYS*|CYGWIN*) TV2_OS=windows; EXE=.exe; NDK_HOST=windows-x86_64 ;;
	Darwin)               TV2_OS=mac;     EXE="";   NDK_HOST=darwin-x86_64 ;;
	Linux)                TV2_OS=linux;   EXE="";   NDK_HOST=linux-x86_64 ;;
	*)                    TV2_OS=unknown; EXE="";   NDK_HOST=linux-x86_64 ;;
esac

# ── Android NDK (Tier0 4-arch 크로스컴파일용) ──────────
if [ -z "${ANDROID_NDK_HOME:-}" ]; then
	for base in "${ANDROID_HOME:-}" "$HOME/AppData/Local/Android/Sdk" "$HOME/Library/Android/sdk" "$HOME/Android/Sdk" "$HOME/Android/sdk"; do
		if [ -n "$base" ] && [ -d "$base/ndk" ]; then
			_ver="$(ls "$base/ndk" 2>/dev/null | sort -V | tail -1)"
			[ -n "$_ver" ] && ANDROID_NDK_HOME="$base/ndk/$_ver" && break
		fi
	done
fi
NDK_BIN="${ANDROID_NDK_HOME:-}/toolchains/llvm/prebuilt/$NDK_HOST/bin"
NDK_CLANG="$NDK_BIN/clang$EXE"

# ── Unreal Engine ─────────────────────────────────────
if [ -z "${UE_ROOT:-}" ]; then
	for c in \
		"/c/Program Files/Epic Games/UE_5.1" "C:/Program Files/Epic Games/UE_5.1" \
		"/Users/Shared/Epic Games/UE_5.1" "$HOME/UnrealEngine" "$HOME/UE_5.1"; do
		[ -d "$c" ] && UE_ROOT="$c" && break
	done
fi

# ── Ghidra (추출 단계, 선택) ──────────────────────────
if [ -z "${GHIDRA_DIR:-}" ]; then
	for c in \
		"C:/ghidra/ghidra_12.0_PUBLIC/ghidra_12.0_PUBLIC" "/c/ghidra/ghidra_12.0_PUBLIC/ghidra_12.0_PUBLIC" \
		"$HOME/ghidra" "/opt/ghidra"; do
		[ -e "$c/support/analyzeHeadless" ] || [ -e "$c/support/analyzeHeadless.bat" ] && GHIDRA_DIR="$c" && break
	done
fi

export TV2_OS EXE NDK_HOST ANDROID_NDK_HOME NDK_BIN NDK_CLANG UE_ROOT GHIDRA_DIR

tv2_env_summary() {
	echo "OS        : $TV2_OS"
	echo "NDK clang : ${NDK_CLANG:-(없음)}  $( [ -x "$NDK_CLANG" ] && echo OK || echo MISSING )"
	echo "UE_ROOT   : ${UE_ROOT:-(없음)}    $( [ -n "${UE_ROOT:-}" ] && [ -d "$UE_ROOT" ] && echo OK || echo MISSING )"
	echo "GHIDRA_DIR: ${GHIDRA_DIR:-(없음, 추출 단계에만 필요)}"
}
