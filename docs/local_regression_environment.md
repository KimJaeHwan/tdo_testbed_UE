# Local Regression Environment

This file is the local source of truth for the three-repo TDO regression setup.
Check this before running tools so Python, Ghidra, and release artifact paths do
not drift between commands.

## Repositories

| Role | Path | Notes |
|---|---|---|
| Low P-code engine | `/Volumes/DO/00_gitProject/01_tdo/lowpcode_data_origin` | Main implementation repo. Use this repo's Python venv for analysis. |
| DFB testbed | `/Volumes/DO/00_gitProject/01_tdo/tdo_testbed` | Existing single-feature DataFlowBench-style regression suite. |
| UE/fusion testbed | `/Volumes/DO/00_gitProject/01_tdo/tdo_testbed_UE` | Large-struct, UE layout, container, and false-positive regression suite. |

## Python

Use the engine virtualenv for analysis. It has `networkx` and the engine's
current dependencies installed.

```bash
/Volumes/DO/00_gitProject/01_tdo/lowpcode_data_origin/.venv/bin/python
```

Verified:

```text
Python 3.14.3
networkx 3.6.1
```

The UE testbed runner tools call `tools/tdo_paths.py`, which auto-detects the
engine repo and re-execs with this venv when launched via system `python3`.

## Ghidra

```bash
GHIDRA_DIR=/opt/homebrew/Cellar/ghidra/12.0.4/libexec
GHIDRA_JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home"
```

Use `GHIDRA_JAVA_HOME` to force Ghidra onto Android Studio's JBR 21 instead of
the system JDK.

Headless:

```bash
"$GHIDRA_DIR/support/analyzeHeadless"
```

Codex sandbox note: Ghidra reads/writes under `~/Library/ghidra`, so headless
extraction from Codex usually needs escalated filesystem permission.

## Android NDK

```bash
ANDROID_HOME=/Users/test2000/Library/Android/sdk
ANDROID_NDK_HOME=/Users/test2000/Library/Android/sdk/ndk/30.0.14904198
NDK_CLANG=/Users/test2000/Library/Android/sdk/ndk/30.0.14904198/toolchains/llvm/prebuilt/darwin-x86_64/bin/clang
```

Verified by `./build.sh env`: `NDK clang ... OK`.

## Unreal Engine

```bash
UE_ROOT="/Users/Shared/Epic Games/UE_5.8"
```

Installed local UE versions:

```text
UE 5.8.0  local Mac build target
UE 5.1.1  legacy/release artifact reference
```

Current Xcode:

```text
Xcode 26.6
MacOSX26.5.sdk
```

Important: UE 5.1.1's UBT validator allows Apple SDK versions only up to
`14.9.9`, so local UE Mac builds are blocked with Xcode 26. UE 5.8.0 builds
with Xcode 26 after the testbed target files explicitly set C++20 and allow the
Editor target build-environment override.

```text
UE 5.8.0 DebugGame/P0    : build succeeded
UE 5.8.0 Development/P1  : build succeeded
```

Use GitHub Release Win64 binaries for the existing release-artifacts regression
baseline. Use UE 5.8.0 for local Mac build/extract development.

## UE Release Artifacts

Release used:

```text
KimJaeHwan/tdo_testbed_UE 0.3.0
```

Local extracted root:

```bash
/Volumes/DO/00_gitProject/01_tdo/tdo_testbed_UE/dist/release_0.3.0
```

Downloaded assets:

```text
testbed-ue-win64.zip
testbed-flows-and-expected.zip
testbed-tier0-elf.zip
```

Important paths:

```bash
dist/release_0.3.0/extracted/ue-win64/UnrealEditor-TraceUnrealPlayground.dll
dist/release_0.3.0/extracted/ue-win64/UnrealEditor-TraceUnrealPlayground.pdb
dist/release_0.3.0/extracted/ue-win64/UnrealEditor-TraceUnrealPlayground-Win64-DebugGame.dll
dist/release_0.3.0/extracted/ue-win64/UnrealEditor-TraceUnrealPlayground-Win64-DebugGame.pdb
dist/release_0.3.0/extracted/expected/tv2_unreal.expected.json
dist/release_0.3.0/extracted/expected/tv2_cpp_like.expected.json
```

Generated low-pcode roots:

```bash
dist/release_0.3.0/low_pcode/ue_win64_dev
dist/release_0.3.0/low_pcode/ue_win64_debuggame
```

Extraction baseline:

```text
UE Win64 Development: root cases 22, extracted functions 69, success=69 fail=0
UE Win64 DebugGame : root cases 22, extracted functions 116, success=116 fail=0
```

Validation baseline with current engine:

```text
UE Win64 Development: PASS 7 / FAIL 15
UE Win64 DebugGame : PASS 2 / FAIL 20
```

Known DebugGame false-positive reproduction:

```text
TV2U008 and TV2U009 reach forbidden dfb_source_B.ret
```

## Common Commands

Environment check:

```bash
cd /Volumes/DO/00_gitProject/01_tdo/tdo_testbed_UE
./build.sh env
```

Tier0 build:

```bash
./build.sh tier0 P0
```

Tier0 x64 low-pcode extraction:

```bash
./cpp_like/scripts/extract_lowpcode.sh x64 P0
```

Harness Tier0 x64 build/extract only:

```bash
python3 -m harness.orchestrator \
  --suite 10 \
  --mode local-samples \
  --prepare-only \
  --profile P0 \
  --arch x64
```

Harness Tier0 x64 build/extract/analyze:

```bash
python3 -m harness.orchestrator \
  --suite 10 \
  --mode local-samples \
  --prepare-artifacts \
  --profile P0 \
  --arch x64 \
  --variant-filter tv2-tier0-P0-x64
```

Local UE 5.8 build through the harness:

```bash
python3 -m harness.orchestrator \
  --suite 10 \
  --mode local-samples \
  --prepare-only \
  --profile P0 \
  --arch x64 \
  --include-ue-build

python3 -m harness.orchestrator \
  --suite 10 \
  --mode local-samples \
  --prepare-only \
  --profile P1 \
  --arch x64 \
  --include-ue-build
```

UE release Development validation:

```bash
python3 cpp_like/tools/run_v2_engine.py \
  dist/release_0.3.0/low_pcode/ue_win64_dev \
  dist/release_0.3.0/extracted/expected/tv2_unreal.expected.json
```

UE release DebugGame validation:

```bash
python3 cpp_like/tools/run_v2_engine.py \
  dist/release_0.3.0/low_pcode/ue_win64_debuggame \
  dist/release_0.3.0/extracted/expected/tv2_unreal.expected.json
```

## Policy

- Do not commit generated `dist/`, `samples/`, binaries, PDBs, or low-pcode JSON.
- Keep expected JSON under source control only when it is part of the testbed's
  source-of-truth manifest/generated expected set.
- For UE regression on this Mac, prefer release binaries until a compatible
  local UE/Xcode build profile is intentionally established.
