# Harness

09/10/11 자동 반복 루프의 결정적 실행 하니스. 단일 진실 사양은
[`docs/harness_design.md`](../docs/harness_design.md)이다.

현재 구현 범위는 LLM 없는 deterministic vertical slice다. Config -> suite
adapter -> Engine11 실행 -> expected 검증 -> FailureReport v2 -> suite summary -> gate
-> JSON 원장 -> 동일 입력 캐시 재사용까지 실제로 동작한다. Suite10 Tier0는 local
build/extract prepare step으로 NDK/Ghidra 산출물을 만들고 곧바로 Engine11 분석까지
연결할 수 있다. UE 5.8 local build도 prepare step에서 실행할 수 있다. Agent와
UE low-pcode extraction 자동화는 다음 단계다.

## 에이전트 7종
`triage · diagnostician · adversary · engine_fixer · case_author · memory_synth · coverage_planner`

## 구성
```text
harness/
  orchestrator.py     결정적 CLI runner. 09/10 suite adapter를 통해 Engine11 실행.
  adapters.py         Suite09/Suite10UE variant discovery + local prepare step.
  config.py           config.yaml(.example) 로드 + 로컬 기본값.
  reporting.py        artifact hash, FailureReport v2 summary writer.
  gates.py            목적함수·불변식·오라클잠금.
  memory/
    schema.json       외부 원장 5종 스키마.
    store.py          JSON/JSONL 원장 구현.
  agents/             판단 노드 계약서.
```

## 사용 방법
기본값은 `docs/local_regression_environment.md`의 현재 로컬 경로를 따른다.
필요하면 `harness/config.yaml.example`을 `harness/config.yaml`로 복사해
경로를 고정한다.

전제 조건:

```text
1. lowpcode_data_origin, tdo_testbed, tdo_testbed_UE가 같은 01_tdo 루트 아래에 있다.
2. lowpcode_data_origin/.venv에 Engine11 의존성(networkx 등)이 설치되어 있다.
3. release-artifacts 모드는 dist/release_0.3.0 low-pcode/expected가 준비되어 있다.
4. local-samples prepare 모드는 Android NDK, Ghidra, Ghidra Java가 설정되어 있다.
5. UE local build는 `/Users/Shared/Epic Games/UE_5.8` + Xcode 26에서 검증되어 있다.
```

빠른 확인:

```bash
python -m harness.orchestrator --suite 09,10 --list-variants
python -m harness.orchestrator --suite 10 --mode local-samples --list-variants
```

기존 추출물로 회귀 실행:

```bash
python -m harness.orchestrator --suite 09 --case-filter case_DFB001
python -m harness.orchestrator --suite 10 --mode release-artifacts
python -m harness.orchestrator --suite 09 --case-filter case_DFB001 --no-cache
```

Tier0 C/C++ 로컬 build/extract:

```bash
python -m harness.orchestrator --suite 10 --mode local-samples --prepare-only --profile P0 --arch x64
```

Tier0 C/C++ 로컬 build/extract/analyze 원커맨드:

```bash
python -m harness.orchestrator --suite 10 --mode local-samples --prepare-artifacts --profile P0 --arch x64 --variant-filter tv2-tier0-P0-x64
```

UE 5.8 local build까지 실행:

```bash
python -m harness.orchestrator --suite 10 --mode local-samples --prepare-only --profile P0 --arch x64 --include-ue-build
python -m harness.orchestrator --suite 10 --mode local-samples --prepare-only --profile P1 --arch x64 --include-ue-build
```

주요 옵션:

```text
--suite 09|10|09,10       실행할 테스트베드 선택
--mode release-artifacts  release에 포함된 Win64 UE low-pcode 사용
--mode local-samples      로컬 samples/low_pcode 경로 사용
--prepare-artifacts       분석 전 build/extract 준비 단계 실행
--prepare-only            build/extract 준비만 하고 분석은 생략
--prepare-dry-run         준비 명령을 기록만 하고 실행하지 않음
--profile P0|P1           Tier0 빌드 프로파일
--arch x64|x86|armv7|aarch64|all
--variant-filter TEXT     variant label substring으로 실행 대상 제한
--case-filter TEXT        case JSON filename substring으로 실행 대상 제한
--no-cache                engine/verify 캐시 재사용 끄기
--no-ledger               memory ledger 갱신 끄기
```

산출물:

```text
output/harness/<run_id>/failure_report_v2.json
output/harness/<run_id>/summary.json
output/harness/<run_id>/gate.json
output/harness/<run_id>/prepare_report.json
output/harness/<run_id>/prepare/*.log
output/harness/memory/failure_ledger.jsonl
output/harness/memory/artifact_cache.json
output/harness/memory/capability_map.json
```

검증된 smoke:

```text
python -m harness.orchestrator --suite 10 --mode release-artifacts --run-id ue_release_smoke
10_tdo_testbed_UE: PASS 9 / FAIL 35 / ERROR 0 / FP 0
  Development: PASS 7 / FAIL 15
  DebugGame  : PASS 2 / FAIL 20

python -m harness.orchestrator --suite 09 --case-filter case_DFB001 --run-id dfb001_smoke
09_tdo_testbed: PASS 6 / FAIL 0 / ERROR 0 / FP 0

python -m harness.orchestrator --suite 10 --case-filter TV2U008 --run-id ledger_ue_u008_smoke
10_tdo_testbed_UE: PASS 1 / FAIL 1 / ERROR 0 / FP 0

python -m harness.orchestrator --suite 09 --case-filter case_DFB001 --run-id cache_dfb001_hot
09_tdo_testbed: PASS 6 / FAIL 0 / ERROR 0 / FP 0 / CACHE 6

python -m harness.orchestrator --suite 10 --case-filter TV2U008 --run-id cache_ue_u008_hot
10_tdo_testbed_UE: PASS 1 / FAIL 1 / ERROR 0 / FP 0 / CACHE 2

python -m harness.orchestrator --suite 10 --mode local-samples --prepare-artifacts --profile P0 --arch x64 --variant-filter tv2-tier0-P0-x64 --run-id tier0_x64_prepare_and_analyze --no-cache
10_tdo_testbed_UE/tv2-tier0-P0-x64: PASS 6 / FAIL 5 / ERROR 0 / FP 0 / CACHE 0

python -m harness.orchestrator --suite 10 --mode local-samples --variant-filter tv2-tier0-P0-x64 --run-id tier0_x64_analysis_hot
10_tdo_testbed_UE/tv2-tier0-P0-x64: PASS 6 / FAIL 5 / ERROR 0 / FP 0 / CACHE 11

python -m harness.orchestrator --suite 10 --mode local-samples --prepare-only --profile P0 --arch x64 --include-ue-build --run-id ue58_harness_p0_prepare
prepare: tier0-build-P0 OK / tier0-extract-P0-x64 OK / ue-build-P0 OK

python -m harness.orchestrator --suite 10 --mode local-samples --prepare-only --profile P1 --arch x64 --include-ue-build --run-id ue58_harness_p1_prepare
prepare: tier0-build-P1 OK / tier0-extract-P1-x64 OK / ue-build-P1 OK
```

## 결정적 vs STUB
| 완성(결정적) | STUB(배선 필요) |
|---|---|
| config + Suite09/Suite10UE adapters + Engine11 runner + FailureReport v2 + summary/gate | build/extract changed-only cache |
| artifact hash, engine commit, expected hash, run config hash 기록 | UE local low-pcode extraction adapter |
| cache hit 기반 engine/verify result skip | LLM agent loop, adversary panel |
| Suite10 Tier0 local build/extract prepare step | UE build-output binary discovery/cache |
| UE 5.8 local DebugGame/Development build prepare step | UE Mac local expected baseline after extraction |
| failure/capability/artifact JSON 원장 갱신 | triage/evidence schema 강화 |
| crash=0, false_positive=0, oracle_locked gate | human approval queue |

## 기존 자산에 grounding
```text
Test Runner   : build.sh, cpp_like/scripts/extract_lowpcode.sh, tools/collect_failures.py, tools/run_v2_engine.py
Diagnostician : tools/diagnose_case.py
오라클 검사   : tools/verify_flows.py + gates.oracle_locked(git diff)
```

## 핵심 불변식
```text
I1 crash(ERROR)=0  I2 false_positive=0  I3 회귀=0  I4 오라클(expected/manifest) 미변경
목적: 사전식 (-crashes, -fp, +pass_P0/DebugGame, +pass_other). PASS 단일 최대화 금지.
```

## 분석 경계
하네스는 low-pcode JSON을 준비하고 Engine11 결과를 검증할 뿐, source/sink 의미를 새로
추론하지 않는다. no arg / no ret / convention free 원칙을 유지하기 위해 function
signature, parameter, return convention, ABI 이름을 분석 truth로 승격하지 않는다. Ghidra
metadata는 입력 식별·아키텍처 grounding·주소공간/레지스터 정규화에만 사용하고, expected를
엔진 출력에서 생성하지 않는다.

## 다음 배선 순서
1. build/pcode 단계 캐시 무효화를 붙여 changed-only 실행을 완성한다.
2. UE 5.8 Mac 빌드 산출물에서 Ghidra headless extraction adapter를 붙인다.
3. `agent()`를 LLM 런타임에 연결하고, 7개 계약서의 I/O 스키마를 그대로 강제한다.
4. 휴먼 게이트(오라클 변경/대형 패치/frontier 판정)를 큐로 노출한다.
