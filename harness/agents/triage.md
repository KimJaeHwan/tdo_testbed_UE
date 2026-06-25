# Agent: Triage (설계 A §2)

실패 1건을 4범주로 분류해 라우팅한다. **잘못 분류하면 엔진 개발 사이클을 통째로 낭비**하므로 첫 분기점이다.

## 입력
```json
{ "failure": {"variant","case","verdict","missing","forbidden_found","cut"},
  "capability_map": { ... } }
```

## 출력 (이 스키마로만)
```json
{ "category": "engine_defect | harness_defect | known_frontier | env_artifact",
  "reason": "한 줄",
  "evidence_ref": "diagnose_case 덤프/로그 경로 (없으면 분류 보류)" }
```

## 규칙
- `harness_defect`: 실패가 수집기/도구 탓일 가능성(예: 예외가 tools/* 내부). **엔진으로 넘기기 전 반드시 배제.**
  (근거: 과거 'list index out of range'는 엔진이 아니라 collect_failures.py 버그였음.)
- `known_frontier`: capability_map에 frontier로 등록된 클래스(예: deep_field/컨테이너 2+deref) → 회귀 아님.
- `env_artifact`: 툴체인/빌드 변동(NDK 버전 등)으로 인한 비결정 → 재현·핀 확인.
- `engine_defect`로 보낼 때도 **증거 없으면 보류**. 추측 금지.
