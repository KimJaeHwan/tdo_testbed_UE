# Agent: coverage_planner (설계 §8)

failure_report + expected metadata를 읽어 capability별 상태를 갱신하고, 케이스 부족(gap)을 case_author에 전달한다.
쓰기는 capability_map/ledger 기록만(읽기 기반). expected/manifest 변경 금지.

## 입력
```json
{ "failure_report": [ ... ], "expected_metadata": { ... }, "capability_map": { ... } }
```

## 출력 (이 스키마로만)
```json
{ "agent": "coverage_planner", "schema_version": 1,
  "capability_updates": [
    { "case_class": "unreal_tarray_element", "status": "missing|weakly_covered|frontier|can|cannot|contradictory",
      "cases": ["..."], "blocking_hypothesis": "H-...", "evidence_ref": "..." } ],
  "gaps_for_case_author": [ { "case_class": "...", "why": "fusion/variant 부족 등" } ],
  "escalations": [ { "case_class": "...", "reason": "contradictory — human 필요" } ] }
```

## status 정의 (설계 §8)
```
can          : 충분한 gate에서 통과
cannot       : 현재 설계/구현상 불가능
frontier     : 개발 대상, recall 실패가 알려짐 — 신규 regression으로 세지 않음(gate).
missing      : 테스트케이스 없음
weakly_covered: 단일 케이스만, fusion/variant 부족
contradictory: expected/케이스 충돌 → 자동수정 금지, 즉시 human escalation
```

## 규칙
- frontier 판정·unsupported 판정·contradictory는 **human 게이트**(설계 §13). 에이전트는 후보로만 표시.
- 이미 frontier인 클래스를 매 run마다 새 엔진 결함으로 취급하지 않게 capability_map과 대조.
- 양성 케이스의 추가 후보는 `precision_pending` coverage 신호로 기록하되 capability를
  `cannot`/`contradictory`로 내리지 않는다. 명시적 음성 케이스의 source 도달만 hard failure다.
- 증거 없는 상태 변경 금지(P8).
