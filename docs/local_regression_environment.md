# Local Regression Environment

This file is the local source of truth for the four-repo TDO regression setup.
Check this before running tools so Python, Ghidra, and release artifact paths do
not drift between commands.

## Repositories

| Role | Path | Notes |
|---|---|---|
| Low P-code engine | `/Volumes/DO/00_gitProject/01_tdo/lowpcode_data_origin` | Main implementation repo. Use this repo's Python venv for analysis. |
| DFB testbed | `/Volumes/DO/00_gitProject/01_tdo/tdo_testbed` | Existing single-feature DataFlowBench-style regression suite. |
| UE/fusion testbed | `/Volumes/DO/00_gitProject/01_tdo/tdo_testbed_UE` | Large-struct, UE layout, container, recall, and precision-probe suite. |
| OLLVM testbed | `/Volumes/DO/00_gitProject/01_tdo/tdo_testbed_Obf` | Suite12 adversarial overlay; not a core-semantics design driver. |

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
rustworkx 0.18.1
numpy 2.5.2
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

The UE tier0 extraction script keeps Ghidra config/cache under the project by
default, which avoids accidental writes to `~/Library/ghidra`:

```bash
GHIDRA_XDG_CONFIG_HOME=cpp_like/build/ghidra_config
GHIDRA_XDG_CACHE_HOME=cpp_like/build/ghidra_cache
```

If `analyzeHeadless` is launched manually, pass equivalent
`XDG_CONFIG_HOME`/`XDG_CACHE_HOME` values or expect Ghidra to use the normal
user profile directories.

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
UE 5.8.0 Mac artifacts   : Mach-O arm64 dylibs
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

## Suite12 OLLVM

Suite12 lives at:

```bash
/Volumes/DO/00_gitProject/01_tdo/tdo_testbed_Obf
```

Current Docker OLLVM default is AArch64:

```text
OBF_OLLVM_ARCH=aarch64
image: tdo-testbed-obf-ollvm:llvm4
platform: linux/arm64
LLVM_TARGETS: AArch64
```

Architecture-specific OLLVM profiles use suffixes and separate sample roots:

```text
OLLVM_ALL          -> samples/low_pcode/OLLVM_ALL          -> AArch64
OLLVM_ALL_x64      -> samples/low_pcode/OLLVM_ALL_x64      -> x86_64
OLLVM_ALL_x86      -> samples/low_pcode/OLLVM_ALL_x86      -> x86
OLLVM_ALL_armv7    -> samples/low_pcode/OLLVM_ALL_armv7    -> armv7
OLLVM_ALL_aarch64  -> samples/low_pcode/OLLVM_ALL_aarch64  -> AArch64 explicit suffix
```

The original `tdo-testbed-obf-ollvm:llvm4` image was built with only the
AArch64 backend. Build suffix images before running non-AArch64 OLLVM profiles:

```bash
cd /Volumes/DO/00_gitProject/01_tdo/tdo_testbed_Obf
OBF_OLLVM_ARCH=x64 scripts/setup_ollvm_docker.sh
OBF_OLLVM_ARCH=x86 scripts/setup_ollvm_docker.sh
OBF_OLLVM_ARCH=armv7 scripts/setup_ollvm_docker.sh
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

Local UE 5.8 build/extract/analyze through the harness:

```bash
python3 -m harness.orchestrator \
  --suite 10 \
  --mode local-samples \
  --prepare-artifacts \
  --skip-tier0-prepare \
  --profile P1 \
  --include-ue-build \
  --include-ue-extract \
  --variant-filter ue-local-development

python3 -m harness.orchestrator \
  --suite 10 \
  --mode local-samples \
  --prepare-artifacts \
  --skip-tier0-prepare \
  --profile P0 \
  --include-ue-build \
  --include-ue-extract \
  --variant-filter ue-local-debuggame
```

Current local UE 5.8 case-scoped regression baseline:

```text
Development/P1: PASS 65 / FAIL 0 / ERROR 0 / FP 0
DebugGame/P0 : PASS 65 / FAIL 0 / ERROR 0 / FP 0
Combined     : PASS 130 / FAIL 0 / ERROR 0 / FP 0
```

P0 full-directory compose remains useful for debug comparison, but the normal
local harness path uses case-scoped low-pcode closure materialization because it
keeps Engine11 semantics unchanged while avoiding unrelated UE helper graph
composition.

Mach-O symbol note: Ghidra names C exported symbols with a leading underscore on
Mac (`_case_TV2...`, `_dfb_...`). The UE extraction script normalizes only this
object-format spelling at the extraction boundary, so Engine11 does not learn a
new call-convention or source/sink naming convention.

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

## Scaled Regression

The optimized path is opt-in so the NetworkX full-program path remains usable
as a reference. Recommended flags are:

```text
--parsed-cache --graph-backend rustworkx --demand-closure
```

Use case-level process parallelism for a complete matrix. Eight workers are
appropriate for Suite09 and tier0 on this host; use four for the larger local
UE scopes to limit peak memory:

```bash
python3 -m harness.orchestrator \
  --config harness/config.yaml.example \
  --suite 09,10 \
  --mode local-samples \
  --include-proposed-regression \
  --case-scope auto \
  --case-jobs 6 \
  --parsed-cache \
  --graph-backend rustworkx \
  --demand-closure \
  --run-id scaled_full_09_10
```

`--function-build-jobs` is useful when one target contains many independent
functions. Do not combine it with case-level workers for a full matrix; the
harness automatically reduces nested function workers to one to prevent CPU
and memory oversubscription.

Validated 2026-08-17 strict-policy optimized regression baselines:

```text
Suite09                 PASS 488 / FAIL 0 / ERROR 0 / FP 0
Suite10 tier0 P0/P1     PASS 712 / FAIL 0 / ERROR 0 / FP 0
Suite10 local UE 5.8    PASS 130 / FAIL 0 / ERROR 0 / FP 0
Combined                PASS 1330 / FAIL 0 / ERROR 0 / FP 0
```

Saved reports:

```text
output/harness/scaling_full_09_scope_fixed
output/harness/scaling_full_10_tier0_scope_fixed
output/harness/scaling_full_10_ue_scope_fixed
output/harness/scaling_full_09_10_networkx_reference
```

The final path is the uncached NetworkX/full-program reference run. It also
passed all 1,330 cases with zero errors and zero false positives, confirming
that the opt-in scaling path preserves the reference result.

## Recall-First Validation

The active validator policy is `recall_first`:

- Positive cases PASS when every expected data/control source is present.
- All sources outside the expected set, including `forbidden_*` matches, are recorded as
  `REFINEMENT_PENDING` in `precision_report.json`; they do not fail the primary
  regression or trigger an automatic core repair.
- Cases with `expected_no_sources: true` remain strict negative controls. Any
  observed data/control source fails `I5_negative_controls_clean`.
- Crash, missing expected source, negative-control violation, and prior-PASS
  regression remain hard gates.

This separates candidate generation from future forward-taint and
path-feasibility refinement without adding argument, return, or ABI semantics
to the backward-slice core. The old `false_positive` count remains only as a
compatibility alias for `precision_pending` in report consumers.

Validated recall-first full matrix (`recall_first_full_09_10`, 2026-08-17):

```text
Suite09                 PASS 488 / FAIL 0 / ERROR 0 / PRECISION_PENDING 30
Suite10                 PASS 842 / FAIL 0 / ERROR 0 / PRECISION_PENDING 5
Combined                PASS 1330 / FAIL 0 / ERROR 0 / NEGATIVE_FAIL 0
Explicit negative cases PASS 32 / FAIL 0
```

The 35 pending rows are non-gating refinement evidence. They cluster in
DFB010/011/013/014/016 and Tier0 P0 TV2C637/TV2C649. The primary engine repair
loop must not narrow the conservative core solely to remove these candidates.

For automated case-author and engine-development loops, pass
`--regression-case-jobs 6` together with the same parsed-cache, graph-backend,
and closure options. Keep a periodic no-cache NetworkX reference run as an A/B
correctness gate.

Case-scope paths are semantically significant. The engine must preserve the
scope directory instead of resolving the target symlink back to the original
full sample directory. The loader may still resolve each JSON symlink when it
opens the file.

## Policy

- Do not commit generated `dist/`, `samples/`, binaries, PDBs, or low-pcode JSON.
- Keep expected JSON under source control only when it is part of the testbed's
  source-of-truth manifest/generated expected set.
- For UE regression on this Mac, release binaries remain the stable historical
  baseline. UE 5.8 local Mac artifacts are now the active local build/extract
  development path because UE 5.1.1 is blocked by Xcode 26 SDK validation.
