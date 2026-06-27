# Testbed V2 — Unreal / Engine-Oriented BackwardSlice Testbed

`11_tracing_Data_Origin_lowpcode`의 Low P-Code 기반 **BackwardSlice 엔진**이, 실제 게임 엔진형
**크고 복잡한 구조체**에서 field-/range-sensitive 데이터 흐름을 끝까지 보존하는지 검증하는
테스트 바이너리 + 정답(expected) 생성 프로젝트다. 정확도의 핵심은 *"맞는 source를 찾는 것"* 만이 아니라
*"틀린 source(forbidden)를 끌고 오지 않는 것"* 이다.

## 레포 관계

```
09_tdo_testbed                 단일 기능 격리 테스트 바이너리 생성 (DataFlowBench, DFB### 80개)
11_tracing_Data_Origin_lowpcode 실제 BackwardSlice 엔진 (V8/New V1, Low P-code, convention-free)
10_tdo_UE_testbed  (이 레포)    엔진형 큰/복잡 구조체 "최종 관문" — 09에 없는 fusion + UE 레이아웃
```

로컬 회귀 환경의 Python venv, Ghidra, NDK, UE, release artifact 경로는
[`docs/local_regression_environment.md`](docs/local_regression_environment.md)를 우선 확인한다.

엔진은 **convention-free + byte-range/offset 기반**이고 struct field 이름을 쓰지 않는다(PDB는 overlay).
따라서 "field-sensitive"는 *컴파일된 레이아웃의 byte-offset sensitive*를 뜻한다.

## 구조

```
10_tdo_UE_testbed/
  build.sh / build.ps1          원커맨드 빌드 (Win Git Bash / macOS Terminal)
  tools/detect_env.sh           OS·NDK·UE·Ghidra 자동 탐지
  run_all_coverage.sh           전 빌드변형 일괄 빌드+추출+검증
  docs/testbed_v2_case_matrix.md 케이스 매트릭스 (severity·arch·profile 설계)

  cpp_like/                     Tier0 — 순수 C++ fusion (UE 의존성 없음)
    include/ src/               tv2_types.h, cases_fusion.cpp, tv2_sources_sinks.*
    manifests/ expected/        정답 단일원본 → expected JSON 생성
    tools/                      generate_expected, run_v2_engine.py, inspect_cut.py
    scripts/                    build_4arch.sh, extract_lowpcode.sh
    build/<P0|P1>/<arch>/        산출 .so

  unreal_playground/TraceUnrealPlayground/   Tier2/3 — UE 5.1 C++ 모듈
    Source/.../TraceTypes.h TraceObjects.h   USTRUCT / UCLASS
                TraceCases.cpp TraceCases2.cpp 케이스 (extern "C")
    Binaries/Win64/             산출 DLL+PDB
```

## Tier 개요 (케이스 33개)

| Tier | 위치 | 케이스 | 내용 |
|---|---|---|---|
| 0 | cpp_like | 11 (fusion) | large struct copy/kill/wide-narrow/ptr-chain 등 — 09 단일기능을 한 흐름에 융합 |
| 2 | unreal_playground | 10 | USTRUCT/UCLASS 레이아웃 (UObject 헤더 offset 포함) |
| 3 | unreal_playground | 12 | FVector/FTransform/FName, TArray/TMap/FString/TObjectPtr/컴포넌트 체인 |

> 09와 중복되는 단일기능 케이스는 Tier0에서 제거했다(설계서 §2: 단일은 09가 통과, fusion에서 깨짐).
> 상세·severity·정답은 [`docs/testbed_v2_case_matrix.md`](docs/testbed_v2_case_matrix.md).

## 빌드 — 명령어 하나

**Windows** (Git Bash) 또는 **macOS** (Terminal):

```bash
./build.sh            # 전부: Tier0(P0) + UE(P0)
./build.sh tier0      # Tier0만 (NDK clang → x86/x64/armv7/aarch64 ELF)
./build.sh ue         # UE 모듈만
./build.sh all P1     # P1 = 최적화(-O2 / UE Development)
./build.sh env        # 환경 탐지 결과만
```

Windows에서 PowerShell만 쓴다면: `./build.ps1 all P0` (내부적으로 Git Bash 호출).

### 사전 준비
- **공통**: Python 3, Android Studio + NDK (Tier0 크로스컴파일), Unreal Engine 5.1 (Tier2/3)
- **Windows**: Git for Windows(Git Bash), Visual Studio 2022 (C++; UBT가 MSVC 14.29~ 자동선택)
- **macOS**: Xcode command line tools

### 툴체인 경로
`detect_env.sh`가 자동 탐지한다. 못 찾거나 버전을 고정하려면 환경변수로 오버라이드:

```bash
ANDROID_NDK_HOME="/path/to/ndk/25.1.8937393" \
UE_ROOT="/path/to/UE_5.1" \
./build.sh all
```

11_ Low P-code 엔진과 Ghidra dumper는 레포가 같은 상위 디렉터리에 있으면 자동 탐지한다.
다른 위치라면 명시한다:

```bash
TDO_ENGINE_ROOT="/path/to/lowpcode_data_origin" \
GHIDRA_DIR="/path/to/ghidra" \
./run_all_coverage.sh
```

Python 검증 도구는 `TDO_ENGINE_ROOT/.venv`가 있으면 자동으로 그 Python으로 재실행하여
엔진 의존성과 같은 런타임에서 동작한다.

> NDK는 Windows·macOS 모두 동일 4-arch ELF를 만든다(host와 무관, 11_ 엔진 샘플과 정합).
> UE 빌드는 Windows=Win64, macOS=Mac 타깃. Windows에서 UBT는 .NET 6 런타임이 필요해
> build.sh가 UE 번들 dotnet(6.0.302)을 자동으로 PATH 앞에 둔다.

## 전체 파이프라인 (빌드 → 추출 → 검증)

빌드 외에 엔진 검증까지 하려면 Ghidra + 11_ 엔진이 필요하다.

```bash
# 1) 빌드
./build.sh all

# 2) Ghidra Low P-code 추출 (GHIDRA_DIR 자동탐지)
bash cpp_like/scripts/extract_lowpcode.sh x64           # Tier0
#  UE DLL은 run_all_coverage.sh 참고

# 3) 11_ 엔진으로 expected 대조
python cpp_like/tools/run_v2_engine.py <samples_dir> <expected.json>
python cpp_like/tools/inspect_cut.py <case_..._low_pcode.json>   # 끊긴 지점

# 전부 한 번에:
bash run_all_coverage.sh
```

## 현재 결과 (x64 기준, 요약)

| 빌드 변형 | PASS/FAIL | false positive | 메모 |
|---|---|---|---|
| Tier0 P0 (-O0) x86/armv7 | 7/4 | 0 | 32-bit가 약간 우세 |
| Tier0 P0 (-O0) x64/aarch64 | 6/5 | 0 | |
| Tier0 P1 (-O2) x64 | 2/9 | 0 | 최적화가 정밀도 붕괴 |
| UE Development (/O2) | 7/15 | 0 | |
| UE DebugGame (P0) | 2/20 | **2** | U008/U009 UObject 포인터 field offset 혼동 |

**판정 불변식**: 어떤 등급/빌드에서도 forbidden source 도달 = FAIL. FAIL은 대부분 false-negative
(정밀도 프론티어, 엔진의 다음 작업 목록). false positive는 backward-slice에서 가장 위험 — UE DebugGame
U008/U009에서 유일하게 발생(11_ 엔진 1순위 버그).

핵심 발견: ① 최적화 축(-O2)이 정밀도의 주 변수, ② arch마다 결과 편차, ③ 과한 비최적화(DebugGame)는
helper 콜 폭증으로 콜 경계 병목 → 양극단 모두 unresolved boundary가 문제.
