# Harness 스켈레톤 (B)

09/10/11 자동 반복 루프 멀티에이전트의 **구현 스켈레톤**. 단일 진실 사양은 [`docs/harness_design.md`](../docs/harness_design.md)(A).
이 스켈레톤은 **결정적 control flow는 완성**, **LLM 호출·빌드 배선은 STUB**로 두어 GPT5.5가 자기 런타임에 배선한다.

## 구성
```
harness/
  orchestrator.py     결정적 메인 루프 (A §3). agent()·run_tests()는 STUB.
  gates.py            목적함수·불변식·오라클잠금 (A §5, §P3). 완성(결정적).
  memory/
    schema.json       외부 원장 5종 스키마 (A §4)
    store.py          원장 접근 인터페이스 (STUB)
  agents/             판단 노드 6종 계약서 (I/O 스키마·규칙)
    triage.md diagnostician.md adversary.md engine_fixer.md case_author.md memory_synth.md
```

## 결정적 vs STUB (A §P1)
| 완성(결정적) | STUB(배선 필요) |
|---|---|
| `gates.py` 전체 / `orchestrator.loop` control flow·게이트 호출·불변검사 | `agent(role,payload)` → LLM 런타임 |
| 기존 도구 호출(build/extract/collect/diagnose/verify) | `run_tests`의 changed-only 캐시(artifact_cache) |
| 회귀·목적함수·오라클잠금 판정 | `memory/store.py` 원장 구현(JSON/sqlite) |

## 기존 자산에 grounding (A §8 — 새로 안 만듦)
```
Test Runner   : build.sh, cpp_like/scripts/extract_lowpcode.sh, tools/collect_failures.py, tools/run_v2_engine.py
Diagnostician : tools/diagnose_case.py
오라클 검사   : tools/verify_flows.py + gates.oracle_locked(git diff)
```

## 핵심 불변식 (gates.py가 강제, A §5)
```
I1 crash(ERROR)=0  I2 false_positive=0  I3 회귀=0  I4 오라클(expected/manifest) 미변경
목적: 사전식 (-crashes, -fp, +pass_P0/DebugGame, +pass_other). PASS 단일 최대화 금지(gaming).
```

## 배선 순서 (GPT5.5)
1. `agent()`를 LLM 런타임에 연결, 6개 계약서의 I/O 스키마를 그대로 강제(구조화 출력).
2. `memory/store.py`를 schema.json대로 구현(JSON로 시작 가능).
3. `run_tests`에 artifact_cache(binary_hash→스킵) 배선 + 툴체인 버전 핀(A §P5).
4. 휴먼 게이트(오라클 변경/대형 패치/frontier 판정)를 큐로 노출(A §P7).
5. adversary 패널을 **서로 다른 모델/온도**로 구성하면 맹점 분산에 유리.

## 비-목표 (이 스켈레톤은 안 함)
- 실제 LLM 호출/엔진 코드 작성 — 런타임/엔진 에이전트 몫.
- 결정적 파이프라인을 LLM으로 대체 — 금지(A §P1).
