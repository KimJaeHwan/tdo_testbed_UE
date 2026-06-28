# Harness

09/10/11 자동 반복 루프의 결정적 실행 하니스. 단일 진실 사양은
[`docs/harness_design.md`](../docs/harness_design.md)이다.

현재 구현 범위는 LLM 없는 deterministic vertical slice다. Config -> suite
adapter -> Engine11 실행 -> expected 검증 -> FailureReport v2 -> suite summary -> gate
-> JSON 원장 -> 동일 입력 캐시 재사용까지 실제로 동작한다. Agent와 local build/extract
adapter는 다음 단계다.

## 에이전트 7종
`triage · diagnostician · adversary · engine_fixer · case_author · memory_synth · coverage_planner`

## 구성
```text
harness/
  orchestrator.py     결정적 CLI runner. 09/10 suite adapter를 통해 Engine11 실행.
  adapters.py         Suite09/Suite10UE variant discovery.
  config.py           config.yaml(.example) 로드 + 로컬 기본값.
  reporting.py        artifact hash, FailureReport v2 summary writer.
  gates.py            목적함수·불변식·오라클잠금.
  memory/
    schema.json       외부 원장 5종 스키마.
    store.py          JSON/JSONL 원장 구현.
  agents/             판단 노드 계약서.
```

## 실행
기본값은 `docs/local_regression_environment.md`의 현재 로컬 경로를 따른다.
필요하면 `harness/config.yaml.example`을 `harness/config.yaml`로 복사해
경로를 고정한다.

```bash
python -m harness.orchestrator --suite 10 --mode release-artifacts
python -m harness.orchestrator --suite 09 --case-filter case_DFB001
python -m harness.orchestrator --suite 09,10 --list-variants
python -m harness.orchestrator --suite 09 --case-filter case_DFB001 --no-cache
```

산출물:

```text
output/harness/<run_id>/failure_report_v2.json
output/harness/<run_id>/summary.json
output/harness/<run_id>/gate.json
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
```

## 결정적 vs STUB
| 완성(결정적) | STUB(배선 필요) |
|---|---|
| config + Suite09/Suite10UE adapters + Engine11 runner + FailureReport v2 + summary/gate | build/extract changed-only cache |
| artifact hash, engine commit, expected hash, run config hash 기록 | local build/extract adapter |
| cache hit 기반 engine/verify result skip | LLM agent loop, adversary panel |
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

## 다음 배선 순서
1. local build/extract mode에서 `build.sh`, `extract_lowpcode.sh`, Ghidra headless를 adapter로 이동한다.
2. build/pcode 단계 캐시 무효화를 붙여 changed-only 실행을 완성한다.
3. `agent()`를 LLM 런타임에 연결하고, 7개 계약서의 I/O 스키마를 그대로 강제한다.
4. 휴먼 게이트(오라클 변경/대형 패치/frontier 판정)를 큐로 노출한다.
