# A↔B 정합성 감사

설계 A(`docs/harness_design.md`)를 기준으로 스켈레톤 B(`harness/`)가 충실히 구현됐는지 점검한 결과.
GPT5.5 검수 전 1차 자체 감사.

## 방법
- A의 모든 원칙·컴포넌트·메모리·불변식·게이트·종료조건을 B의 위치로 추적(traceability).
- 코드 참조 일치 실검사: `agent(role)`↔계약서 파일명, orchestrator↔gates/store 심볼, 구문 검사.

## Traceability (A → B)

| A 항목 | B 위치 | 상태 |
|---|---|---|
| P1 agent화 최소화 | orchestrator(결정적 loop) + agents/(판단 6노드만) | ✓ |
| P2 반박 필수 | `adversary_panel()` 다수결 + agents/adversary.md(증거없는 confirm 무효) | ✓ |
| P3 오라클 무결성 | `gates.oracle_locked()` (I4) + engine_fixer.md 금지조항 | ✓ |
| P4 목적함수 사전식 | `gates.objective_vector/objective_improves` | ✓ |
| P5 결정성·버전핀 | artifact_cache(schema) + README 배선4 | ✓(스키마/지침), 배선 STUB |
| P6 외부 구조화 메모리 | memory/schema.json(5원장) + store.py | ✓(스키마), 구현 STUB |
| P7 휴먼 게이트 | `mem.queue_for_human_approval` + case_author.md + design §6 | ✓ |
| §2 Test Runner(결정적) | `run_tests()` → build.sh/collect_failures.py | ✓(호출), 캐시 STUB |
| §2 Triage/Diag/Adv/Fix/Author/Memory | agents/*.md 6종 + orchestrator 호출 | ✓ |
| §2 Regression Gate | `regression_ok()` + loop 전수 재실행 | ✓ |
| §3 데이터 흐름 | `orchestrator.loop()` 순서 = A §3과 1:1 | ✓ |
| §4 메모리 5원장 | schema.json: failure/hypothesis/decision/artifact/capability | ✓ |
| §5 불변식 I1~I4 | I1 loop 크래시검사 · I2/I3 objective_improves · I4 oracle_locked | ✓ |
| §7 종료/에스컬레이션 | `done()` + `mem.escalate()` | ✓(로직), 목표치 STUB |
| §8 기존자산 매핑 | run_tests/diagnostician/oracle검사가 실제 도구 호출 | ✓ |

## 발견 & 조치
- **[수정됨] role↔파일명 불일치**: orchestrator가 `agent("diagnose")`/`agent("engine_fix")`를 호출했으나
  계약서는 `diagnostician.md`/`engine_fixer.md`. `agents/{role}.md` 규칙 위반 → role을 `diagnostician`/`engine_fixer`로 정정.
  (재검사: orchestrator의 5개 role이 계약서 파일과 정확히 일치. memory_synth는 Memory 계층으로 호출.)
- **[확인] 심볼 정합**: orchestrator의 gates import 5개·`mem.*` 호출 8개가 모두 gates.py/store.py에 존재.
- **[확인] 구문**: gates.py / store.py / orchestrator.py `py_compile` 통과(결정적 파트 유효).

## 잔여 STUB (의도된 미구현 — A §P1 경계)
```
agent(role)           : LLM 런타임 배선 (B의 비-목표)
memory/store.py 본체  : schema.json대로 JSON/sqlite 구현
run_tests 캐시        : artifact_cache(binary_hash) 스킵 + 툴체인 핀
done() 목표치/frontier : P0·DebugGame PASS 목표·frontier 문서화 판정 수치
```
이들은 B 스켈레톤의 책임 경계 밖(런타임/정책 값)이며 README "배선 순서"에 명시됨.

## 판정
**B는 A를 충실히 반영함.** 결정적 안전장치(게이트·불변식·반박 패널·오라클잠금)는 완성·검증됐고,
LLM/정책 배선만 STUB로 남아 GPT5.5가 채우면 된다. 불일치 1건은 발견·수정 완료.

> 주의(정직): 이 감사는 **구조·참조 정합**을 보장한다. 런타임 동작(에이전트 판단 품질·실제 회귀 수렴)은
> 배선 후 실측해야 하며, 본 문서가 보장하지 않는다.
