#!/usr/bin/env bash
# detect_env.sh — OS와 툴체인(NDK clang / Unreal / Ghidra)을 자동 탐지한다. source 해서 사용.
# 오버라이드: ANDROID_NDK_HOME, UE_ROOT, GHIDRA_DIR 환경변수가 있으면 그것을 우선한다.

# ── OS ────────────────────────────────────────────────
case "$(uname -s)" in
	MINGW*|MSYS*|CYGWIN*) TV2_OS=windows; EXE=.exe; NDK_HOST_DEFAULT=windows-x86_64 ;;
	Darwin)               TV2_OS=mac;     EXE="";   NDK_HOST_DEFAULT=darwin-x86_64 ;;
	Linux)                TV2_OS=linux;   EXE="";   NDK_HOST_DEFAULT=linux-x86_64 ;;
	*)                    TV2_OS=unknown; EXE="";   NDK_HOST_DEFAULT=linux-x86_64 ;;
esac
NDK_HOST="${NDK_HOST:-$NDK_HOST_DEFAULT}"

# ── Android NDK (Tier0 4-arch 크로스컴파일용) ──────────
if [ -z "${ANDROID_NDK_HOME:-}" ]; then
	for base in "${ANDROID_HOME:-}" "$HOME/AppData/Local/Android/Sdk" "$HOME/Library/Android/sdk" "$HOME/Android/Sdk" "$HOME/Android/sdk"; do
		if [ -n "$base" ] && [ -d "$base/ndk" ]; then
			_ver="$(find "$base/ndk" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | sort | tail -1)"
			[ -n "$_ver" ] && ANDROID_NDK_HOME="$_ver" && break
		fi
	done
fi
if [ -n "${ANDROID_NDK_HOME:-}" ]; then
	for host in "$NDK_HOST" darwin-arm64 darwin-x86_64 linux-x86_64 windows-x86_64; do
		if [ -x "$ANDROID_NDK_HOME/toolchains/llvm/prebuilt/$host/bin/clang$EXE" ]; then
			NDK_HOST="$host"
			break
		fi
	done
	NDK_BIN="$ANDROID_NDK_HOME/toolchains/llvm/prebuilt/$NDK_HOST/bin"
	NDK_CLANG="$NDK_BIN/clang$EXE"
else
	NDK_BIN=""
	NDK_CLANG=""
fi

# ── Unreal Engine ─────────────────────────────────────
if [ -z "${UE_ROOT:-}" ]; then
	for c in \
		"/c/Program Files/Epic Games/UE_5.8" "C:/Program Files/Epic Games/UE_5.8" \
		"/Users/Shared/Epic Games/UE_5.8" "$HOME/UE_5.8" \
		"/c/Program Files/Epic Games/UE_5.1" "C:/Program Files/Epic Games/UE_5.1" \
		"/Users/Shared/Epic Games/UE_5.1" "$HOME/UnrealEngine" "$HOME/UE_5.1"; do
		[ -d "$c" ] && UE_ROOT="$c" && break
	done
fi

# ── Ghidra (추출 단계, 선택) ──────────────────────────
if [ -z "${GHIDRA_JAVA_HOME:-}" ]; then
	for c in \
		"/Applications/Android Studio.app/Contents/jbr/Contents/Home" \
		"/Library/Java/JavaVirtualMachines/jdk-21.jdk/Contents/Home"; do
		[ -x "$c/bin/java" ] && GHIDRA_JAVA_HOME="$c" && break
	done
fi
if [ -z "${GHIDRA_DIR:-}" ] && [ -n "${GHIDRA_HOME:-}" ]; then
	GHIDRA_DIR="$GHIDRA_HOME"
fi
if [ -z "${GHIDRA_DIR:-}" ] && [ -n "${GHIDRA_INSTALL_DIR:-}" ]; then
	GHIDRA_DIR="$GHIDRA_INSTALL_DIR"
fi
if [ -z "${GHIDRA_DIR:-}" ]; then
	for c in \
		"/opt/homebrew/opt/ghidra/libexec" "/opt/homebrew/Cellar/ghidra/12.0.4/libexec" \
		"C:/ghidra/ghidra_12.0_PUBLIC/ghidra_12.0_PUBLIC" "/c/ghidra/ghidra_12.0_PUBLIC/ghidra_12.0_PUBLIC" \
		"$HOME/ghidra" "/opt/ghidra" "/Applications/ghidra" "/Applications/ghidra_12.0_PUBLIC" \
		"/Applications/ghidra_12.0_PUBLIC/ghidra_12.0_PUBLIC"; do
		if [ -e "$c/support/analyzeHeadless" ] || [ -e "$c/support/analyzeHeadless.bat" ]; then
			GHIDRA_DIR="$c"
			break
		fi
	done
fi

# ── 11_ Low P-code engine / Ghidra dumper ─────────────
if [ -z "${TDO_ENGINE_ROOT:-}" ]; then
	TV2_ENV_HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
	for c in \
		"$TV2_ENV_HERE/../lowpcode_data_origin" \
		"$TV2_ENV_HERE/../trace_data_origin_lowpcode" \
		"$TV2_ENV_HERE/../11_tracing_Data_Origin_lowpcode/trace_data_origin_lowpcode" \
		"D:/01_gitproject/11_tracing_Data_Origin_lowpcode/trace_data_origin_lowpcode"; do
		[ -e "$c/analysis/interprocedural_summary.py" ] && TDO_ENGINE_ROOT="$c" && break
	done
fi
if [ -z "${TDO_DUMPER_DIR:-}" ] && [ -n "${TDO_ENGINE_ROOT:-}" ]; then
	TDO_DUMPER_DIR="$TDO_ENGINE_ROOT/scripts"
fi

tv2_target_triple() {
	case "$1" in
		x86) echo "i686-linux-android24" ;;
		x64) echo "x86_64-linux-android24" ;;
		armv7) echo "armv7a-linux-androideabi24" ;;
		aarch64) echo "aarch64-linux-android24" ;;
		*) return 1 ;;
	esac
}

export TV2_OS EXE NDK_HOST ANDROID_NDK_HOME NDK_BIN NDK_CLANG UE_ROOT GHIDRA_DIR GHIDRA_JAVA_HOME TDO_ENGINE_ROOT TDO_DUMPER_DIR

tv2_env_summary() {
	echo "OS        : $TV2_OS"
	echo "NDK clang : ${NDK_CLANG:-(없음)}  $( [ -x "$NDK_CLANG" ] && echo OK || echo MISSING )"
	echo "UE_ROOT   : ${UE_ROOT:-(없음)}    $( [ -n "${UE_ROOT:-}" ] && [ -d "$UE_ROOT" ] && echo OK || echo MISSING )"
	echo "GHIDRA_DIR: ${GHIDRA_DIR:-(없음, 추출 단계에만 필요)}"
	echo "GHIDRA_JAVA: ${GHIDRA_JAVA_HOME:-(시스템 기본)} $( [ -n "${GHIDRA_JAVA_HOME:-}" ] && [ -x "$GHIDRA_JAVA_HOME/bin/java" ] && echo OK || true )"
	echo "TDO_ENGINE: ${TDO_ENGINE_ROOT:-(없음)} $( [ -n "${TDO_ENGINE_ROOT:-}" ] && [ -e "$TDO_ENGINE_ROOT/analysis/interprocedural_summary.py" ] && echo OK || echo MISSING )"
}
