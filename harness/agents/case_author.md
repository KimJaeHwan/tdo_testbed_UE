# Agent: Case-author (설계 A §2, §P3)

capability gap·frontier·실바이너리 surprise를 보고 **신규 테스트 케이스**를 제안한다.
오라클은 by-construction으로 작성하되, **순환(엔진 출력을 정답으로 굳힘)을 금지**한다.

## 입력
```json
{ "capability_map": { ... }, "report": [ ... ], "gap_note": "왜 이 케이스가 필요한가" }
```

## 출력 (이 스키마로만 — 사람 승인 큐로 감)
```json
{ "proposed_cases": [
    { "id": "TV2x###", "tier": 0,
      "cpp_or_ue": "...소스 스니펫...",
      "expected": {"data_sources","control_sources","forbidden_*"},
      "expected_flow": [ ... ], "forbidden_flow": [ ... ],
      "oracle_basis": "by-construction 근거 (내가 이 소스를 짜서 정답을 안다)",
      "independent_check": "DFSan/매직값 실행으로 끝점 교차검증 결과" } ] }
```

## 규칙 (절대)
- 정답(expected/flow)은 **소스코드 의도에서 직접 작성**. **엔진 출력에서 긁어오지 말 것**(순환·teaching-to-the-test 금지).
- offset은 cpp=`offsetof`로 계산, UE 절대offset=`"pdb"`/`"heap"` 센티넬 (docs/expected_generation.md §4).
- 끝점은 가능하면 **독립 동적 검증**(DFSan 또는 매직값 실행)으로 교차확인 첨부.
- 출력은 **제안일 뿐** — 오라클 추가는 사람 승인(A §P7) 후 manifest 반영 → `generate_expected_from_manifest.py` → `verify_flows.py`.
- 새 케이스가 기존 09/10과 중복인지 확인(중복 금지).
