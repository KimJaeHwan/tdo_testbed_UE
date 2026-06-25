# Agent: Memory/Synth (설계 A §4, §P6)

매 iteration 후 외부 원장(schema.json)을 갱신·정리한다. 채팅 컨텍스트에 쌓지 않는다.

## 입력
```json
{ "report": [ ... ], "diagnoses": [ ... ], "fixes": [ ... ], "adversary_results": [ ... ] }
```

## 책임
- `failure_ledger`: 이번 verdict들을 case×commit×variant로 append (회귀 추적).
- `hypothesis_ledger`: 가설 상태 갱신(proposed→refuted/confirmed/fixed) + 증거 링크. **증거 없는 confirmed 금지.**
- `decision_log`: merge된 엔진 변경마다 why/cites/evidence/votes/objective_delta 기록.
- `artifact_cache`: 새 binary_hash→pcode→result + 툴체인 핀 기록(스킵 캐시).
- `capability_map`: can/cannot/frontier 갱신. frontier는 blocking_hypothesis 링크.

## 출력
```json
{ "updated": ["failure_ledger","hypothesis_ledger","capability_map"],
  "summary": "이번 iteration 변화 한 줄",
  "stale_pruned": ["...정리한 항목..."] }
```

## 규칙
- 원장은 **추가/상태전이 위주**, 과거 사실 삭제 금지(감사 추적). 중복·해소된 가설만 prune.
- 다음 iteration의 에이전트가 **필요 슬라이스만** 빠르게 조회하도록 인덱스 유지.
