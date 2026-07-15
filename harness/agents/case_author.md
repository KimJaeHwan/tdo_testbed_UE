# Agent: Case-author (설계 A §2, §P3)

capability gap·frontier·실바이너리 surprise를 보고 **신규 테스트 케이스**를 제안한다.
오라클은 by-construction으로 작성하되, **순환(엔진 출력을 정답으로 굳힘)을 금지**한다.

## 입력
```json
{
  "capability_map": { ... },
  "report": [ ... ],
  "gap_note": "왜 이 케이스가 필요한가",
  "allowed_targets": ["suite10-cpp", "suite10-ue"],
  "disallowed_targets": ["suite12-obf"],
  "existing_case_ids": ["..."],
  "case_id_policy": { "do_not_reuse_existing_case_ids": true, ... }
}
```

## 출력 (이 스키마로만 — 사람 승인 큐로 감)
```json
{ "proposed_cases": [
    { "id": "TV2x### | OBF###", "tier": 0,
      "target": "suite10-cpp | suite10-ue | suite12-obf",
      "cpp_or_ue": "...소스 스니펫...",
      "expected": {
        "tier": 0,
        "severity": "proposed-regression",
        "binary": "tv2_cpp_like | tv2_unreal | dfbench_obf_basic",
        "name": "...",
        "function": "case_...",
        "source_file": "src/cases_fusion.cpp | Source/TraceUnrealPlayground/TraceCases2.cpp | src/cases_basic_obf.c",
        "anchor": {"callee": "dfb_sink_int", "arg_index": 0, "storage": "test-wrapper-only"},
        "expected_no_sources": false,
        "expected_data_sources": ["..."],
        "expected_sources": ["..."],
        "expected_control_sources": [],
        "expected_global_sources": [],
        "forbidden_data_sources": ["..."],
        "forbidden_sources": ["..."],
        "forbidden_control_sources": [],
        "expected_features": ["fusion", "..."],
        "allowed_warnings": [],
        "manifest_case": {
          "id": "TV2x### | OBF###",
          "tier": 0,
          "severity": "proposed-regression",
          "binary": "tv2_cpp_like | tv2_unreal | dfbench_obf_basic",
          "name": "...",
          "function": "case_...",
          "source_file": "src/cases_fusion.cpp | Source/TraceUnrealPlayground/TraceCases2.cpp | src/cases_basic_obf.c",
          "anchor": {"callee": "dfb_sink_int", "arg_index": 0, "storage": "test-wrapper-only"},
          "expected_no_sources": false,
          "expected_data_sources": ["..."],
          "expected_sources": ["..."],
          "expected_control_sources": [],
          "expected_global_sources": [],
          "forbidden_data_sources": ["..."],
          "forbidden_sources": ["..."],
          "forbidden_control_sources": [],
          "expected_features": ["fusion", "..."],
          "allowed_warnings": []
        }
      },
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
- 입력에 `allowed_targets`가 있으면 반드시 그 안의 target만 사용한다. `disallowed_targets`에 포함된 target은 현재 루프의 관심 밖이므로 제안하지 않는다.
- `existing_case_ids`에 있는 ID를 재사용하지 않는다. Suite12는 기존 최대 `OBF###` 다음 번호를 고른다.
- `anchor`는 테스트 하네스 wrapper가 sink 위치를 찾기 위한 정보다. Engine11 코어 설계에는 arg/ret/calling convention 의미를 새로 주입하지 않는다.
- proposed case는 Engine11을 특정 helper/function/case/source label에 맞춰 고치라고 유도하면 안 된다.
- 금지 예: `TV2...`, `DFB...`, `case_...`, `write_expected`, `dfb_source_A/B/C`, 고정 field offset을 Engine11 core 로직에 넣으라는 제안.
- 허용 경계: source/sink marker와 manifest anchor는 wrapper/BoundaryProvider 계층의 테스트 하네스 입력으로만 사용한다.
- `dfb_sink_*` marker는 void sink다. `return dfb_sink_int(...)`처럼 return 값으로 쓰지 말고, `dfb_sink_int(value);` statement로 호출한다.
- `suite10-ue`의 `cpp_or_ue`는 `Source/TraceUnrealPlayground/TraceCases2.cpp`에 들어가는 독립 C 심볼이어야 한다. `extern "C" TV2_NOINLINE void case_TV2...()` 형태로 정의하고, `UTraceCases2::case_...` 같은 클래스 멤버 메서드를 만들지 않는다.
- `suite10-ue` 케이스는 apply 단계에서 `TraceRunAll2()` keep-alive에 자동 등록된다. snippet 안에는 함수 본문과 필요한 local helper/type만 넣고, UObject 클래스 선언이나 새 UFUNCTION을 만들지 않는다.
- `suite12-obf`의 `cpp_or_ue`는 `tdo_testbed_Obf/src/cases_basic_obf.c`에 들어가는 C 스니펫이다. `DFB_CASE void case_OBF###_...(void)`와 필요한 `DFB_HELPER`/typedef만 넣고, include나 runtime registry를 직접 편집하지 않는다.
- `suite12-obf` manifest oracle은 `expected_sources` / `forbidden_sources`를 사용한다. apply 후 하네스가 registry와 expected JSON을 manifest에서 재생성한다.
- `suite12-obf` 케이스는 OLLVM 변형에서도 풀려야 하므로 opaque predicate, flattened control, helper thunk, field/noise distraction을 섞되 정답은 by-construction이어야 한다.
- 좋은 케이스는 특정 이름을 외우지 않아도 low-pcode graph, observed storage, metadata, summary evidence만으로 풀려야 한다.
- fully green을 목표로 오라클을 약하게 만들지 말 것. FP를 유발할 수 있는 forbidden source를 반드시 설계하고 근거를 적는다.
- negative-only 케이스도 허용된다. 단, 정말 어떤 source도 sink에 도달하면 안 되는 by-construction 케이스일 때만 `expected_no_sources: true`를 expected와 manifest_case 둘 다에 넣고, `expected_data_sources`/`expected_sources`/`expected_control_sources`/`expected_global_sources`는 비워라. 이 경우 `forbidden_data_sources` 또는 `forbidden_sources`는 반드시 하나 이상 있어야 한다.
- source label은 반드시 `dfb_source_A.ret`, `dfb_source_B.ret`, `dfb_source_C.ret`처럼 `.ret` suffix까지 쓴다. `dfb_source_A` 같은 shorthand를 출력하지 않는다.
