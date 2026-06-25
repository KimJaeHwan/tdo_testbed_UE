# Harness 설계 (A) — 09/10/11 자동 반복 루프 멀티에이전트

테스트베드(10_) ↔ BackwardSlice 엔진(11_) 개발의 반복 루프
(테스트→실패→진단→수정→회귀→케이스 추가→빌드→추출→반복)를 자동화하는 하니스의 1장 사양.
구현 스켈레톤은 `harness/`(B). 본 문서가 단일 진실 사양이며 B는 이를 따른다.

## 1. 설계 원칙 (불변)

```
P1 agent화 최소화   : 루프의 80%(build/extract/run/diff/회귀)는 결정적 파이프라인.
                      LLM은 "판단 노드" 4곳(triage/diagnose/adversary/fix/author)에만.
P2 반박 필수        : 모든 원인가설·엔진수정은 독립 adversary가 증거로 반박을 시도해 통과해야 채택.
P3 오라클 무결성    : 테스트를 통과시키려고 expected/manifest를 절대 수정 금지(=gaming 차단).
P4 목적함수 사전식  : PASS 단일 최대화 금지. 아래 §5 순서.
P5 결정성·버전핀    : 툴체인(NDK/UE/Ghidra/MSVC) 버전 핀 + env를 결과에 기록.
P6 외부 구조화 메모리: 컨텍스트가 아니라 쿼리 가능한 원장(JSON/sqlite)에 상태 보존.
P7 휴먼 게이트      : 고레버리지 지점에만(오라클 변경/대형 엔진 패치/frontier 판정).
```

## 2. 컴포넌트 (결정적 vs 에이전트)

| 종류 | 컴포넌트 | 책임 |
|---|---|---|
| 결정적 | **Orchestrator** | 루프·작업큐·게이트 호출. LLM 아님. |
| 결정적 | **Test Runner** | build.sh→extract_lowpcode.sh→run_v2_engine/collect_failures→diff. 구조화 리포트. |
| 결정적 | **Regression Gate** | 09+10 전수 재실행, 회귀·신규 FP·크래시 차단. |
| 결정적 | **Gates** | 목적함수(§5)·오라클잠금·검증 판정. |
| 에이전트 | **Triage** | 실패 4분류: engine_defect / harness_defect / known_frontier / env_artifact. |
| 에이전트 | **Diagnostician** | `diagnose_case.py` 증거 덤프 + 원인가설(**증거 인용 필수**). |
| 에이전트 | **Adversary×N** | 진단·수정을 서로 다른 렌즈(correctness/regression/FP-risk)로 반박. 다수결. |
| 에이전트 | **Engine-fixer** | 11_ worktree/브랜치에 수정(격리). |
| 에이전트 | **Case-author** | 신규 케이스 + 오라클(by-construction) + 독립검증(DFSan/매직값). |
| 에이전트 | **Memory/Synth** | 원장 갱신·정리. |

## 3. 데이터 흐름 (1 iteration)

```
run_tests(changed_only)            # Test Runner. 산출: failure_report.json
  └ 불변검사: crash(ERROR)=0?  아니면 즉시 멈춤·에스컬레이트
for f in triage(failures):         # Triage
  if f.category != engine_defect:  route(harness/frontier/env); continue
  diag = diagnose(f)               # Diagnostician (증거 인용)
  if not adversary.confirm(diag):  memory.mark_refuted(diag); continue       # P2
  fix = engine_fix(diag)           # Engine-fixer (worktree)
  if not adversary.confirm_fix(fix): discard; continue                       # P2
  if regression_gate(fix) and objective.improves(fix):  merge; memory.log    # P4/P5
  else: discard(fix)
maybe_author_cases(capability_map) # Case-author (gap/frontier 기반) + 오라클 휴먼게이트  # P3/P7
memory.update(capability_map, ledgers)
```

## 4. 메모리 스키마 (외부 원장, P6)

```
failure_ledger   : case×commit×variant → verdict, missing, forbidden_found, cut, root_cause_ref
hypothesis_ledger: id → claim, evidence_ref, status(proposed|refuted|confirmed|fixed)   # 신뢰의 원장
decision_log     : engine_change → why, cites(failure_ids), evidence, adversary_votes
artifact_cache   : binary_hash → pcode_path → engine_result   # Ghidra/빌드 스킵 키
capability_map   : case_class → can|cannot|frontier  (예: deep_field=frontier)
```
규칙: 각 에이전트는 **필요한 슬라이스만** 읽는다(컨텍스트 비대화 방지). "검증됨 vs 가설"을 hypothesis_ledger가 관장.

## 5. 목적함수 (사전식, P4) & 불변식

```
점수 = ( -crashes, -false_positives, -regressions, +pass_P0_DebugGame, +pass_other, honest_degrade )
  사전식 비교: 앞 항이 동률일 때만 다음 항 비교.
불변식(어기면 수정 거부):
  I1 crash(ERROR)=0            I2 false_positive=0
  I3 기존 통과 케이스 회귀=0    I4 오라클(expected/manifest) 미변경(P3)
```
`/O2` 변형은 PASS 목표가 아니라 "FP 없음 + 정직한 degrade(unresolved/widened)"로 평가.

## 6. 휴먼 게이트 (P7) / 자율 범위

```
사람 승인 필요: 오라클(expected/manifest) 변경 · 엔진 아키텍처 변경 큰 패치 · "frontier라 안 고침" 선언
완전 자율    : 테스트 실행 · 증거기반 진단 · 수정 제안(merge 전) · 케이스 초안(오라클 제외)
```

## 7. 종료 / 에스컬레이션

```
종료: false_positive=0 AND P0/DebugGame PASS 목표 도달 AND frontier 문서화 완료
에스컬레이션: 같은 케이스 N회 수정 실패 / 회귀 게이트 반복 실패 / 오라클 변경 필요 → 사람 호출
```

## 8. 기존 자산 매핑 (B는 새로 안 만들고 이걸 호출)

```
Test Runner  ← build.sh · cpp_like/scripts/extract_lowpcode.sh · tools/collect_failures.py · run_v2_engine.py
Diagnostician← tools/diagnose_case.py (경로·메모리키 증거)
오라클 검사  ← tools/verify_flows.py (정답 정합) + git diff(expected/manifest 변경 감지)
```
