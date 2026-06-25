# Agent: Triage (설계 A §2)

실패 1건을 4범주로 분류해 라우팅한다. **잘못 분류하면 엔진 개발 사이클을 통째로 낭비**하므로 첫 분기점이다.

## 입력
```json
{ "failure": {"variant","case","verdict","missing","forbidden_found","cut"},
  "capability_map": { ... } }
```

## 출력 (이 스키마로만) — 8 범주 + unknown 폴백 (설계 §7)
```json
{ "category": "engine_defect | harness_defect | extractor_defect | testcase_defect | oracle_defect | environment_defect | known_frontier | unsupported | unknown",
  "reason": "한 줄",
  "evidence_ref": "diagnose_case 덤프/로그 경로" }
```

## 범주 정의
```
engine_defect   : 11_ 엔진 결함 (증거 필수)
harness_defect  : 오케스트레이터/수집·검증 도구 자체 버그 (예: 예외가 tools/* 내부)
extractor_defect: Ghidra dumper(lowpcode/metadata 추출) 결함
testcase_defect : 케이스 C++ 자체가 잘못/모호
oracle_defect   : expected/flow가 틀림 → human(자동수정 금지)
environment_defect: 툴체인/버전 변동(NDK 등) 비결정
known_frontier  : capability_map에 frontier 등록됨 → 회귀 아님
unsupported     : 엔진 설계상 불가(cannot)
unknown         : 모호 → needs_human (8개 중 억지선택 금지)
```

## 규칙 (설계 §7/P8)
- **모든 비-frontier 범주는 evidence 필수.** 재현 증거 없으면 `engine_defect` 단정 금지 → `unknown`.
  (근거: 과거 'list index out of range'는 엔진 아닌 collect_failures.py 버그였음 — harness_defect.)
- 운영상 제일 중요한 건 "engine이냐 아니냐". 게이트는 라벨이 아니라 **증거**다(evidence_required).
