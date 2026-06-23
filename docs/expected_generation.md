# Expected 정답지 생성 가이드

11_ BackwardSlice 엔진을 개발/검증할 때 기준이 되는 **정답지(`expected/*.expected.json`)** 를
어떻게 만드는지 설명한다. 끝점(source/sink)뿐 아니라 **중간 slice 흐름**까지 정답에 담는다.

---

## 0. 핵심 원리 — 분석한 게 아니라 "의도를 적은 것"

정답지는 바이너리를 분석해서 만드는 게 **아니다.** 케이스를 우리가 직접 C++로 짜기 때문에
**정답을 처음부터 안다(by construction).**

```c
B.Inner.Secret = dfb_source_A();   // A를 여기 넣었다
...
dfb_sink_int(B.Inner.Secret);      // 여기서 그걸 읽게 했다
```
→ 정답은 자명: *"A가 `B.Inner.Secret`(offset 256)를 거쳐 sink에 도달, B는 무관."*

> **소스코드라서 쉽다.** 어려운 일(스트립된 바이너리에서 흐름 복원)은 **11_엔진의 몫**이고,
> 테스트베드는 *의도적으로 만든 흐름을 그대로 기록*할 뿐이다. 컴파일러가 `memcpy`·SIMD·레지스터로
> 바꿔도 **의미적 흐름(어느 source가 어느 field 거쳐 sink로 가나)은 불변** — 그게 정답이다.
> 이것이 DataFlowBench류 테스트베드의 원리: *입력을 통제해 정답을 아는 상태로 만들고, 분석기가 복원하는지 본다.*

---

## 1. 파이프라인

```
manifests/cases_v2_manifest.json   ← 단일 진실 원본(정답을 손으로 작성)
        │  python tools/generate_expected_from_manifest.py
        ▼
expected/<binary>.expected.json    ← 11_엔진이 읽는 정답지 (자동 생성, 직접 수정 금지)
```

- `cpp_like/` (Tier0)와 `unreal_playground/` (Tier2/3)가 각각 같은 generator·구조를 가진다.
- generator는 **변환기**일 뿐 — manifest의 케이스를 expected JSON으로 옮겨 적는다. 정답값 자체는 manifest에 사람이 작성한다.
- `build.sh`가 빌드 시 generator를 자동 호출한다.

---

## 2. 정답 스키마 (case 1개)

```jsonc
{
  "id": "TV2C005",
  "function": "case_TV2C005_partial_overwrite_kill",  // 바이너리에서 찾을 심볼
  "anchor": { "callee": "dfb_sink_int", "arg_index": 0 },  // slice 시작점
  "tier": 0, "severity": "core-regression",

  // ── 끝점 정답 (11_ ExpectedValidator가 채점) ──
  "expected_data_sources":    ["dfb_source_C.ret"],   // 반드시 도달
  "expected_control_sources": [],                     // 분기조건 등 control source
  "expected_global_sources":  [],
  "forbidden_data_sources":   ["dfb_source_A.ret", "dfb_source_B.ret"],  // 도달하면 FAIL
  "forbidden_control_sources":[],
  "expected_features":        ["fusion","partial_overwrite","kill"],
  "allowed_warnings":         [],

  // ── 중간 흐름 정답 (사람/미래 경로검사용. "우연 정답" 방지) ──
  "expected_flow": [
    { "op":"source", "label":"dfb_source_C.ret" },
    { "op":"store",  "field":"B.Inner.Secret", "offset":256, "size":4,
      "carries":"dfb_source_C", "detail":"B=A 이후 덮어쓰기(strong-update)" },
    { "op":"load",   "field":"B.Inner.Secret", "offset":256, "size":4 },
    { "op":"sink",   "label":"dfb_sink_int.arg0" }
  ],
  "forbidden_flow": [
    { "node":"store", "field":"B.Inner.Secret", "offset":256, "carries":"dfb_source_A",
      "reason":"복사로 들어온 옛 값(A)은 덮어쓰기로 kill됨 — 경로에 남으면 안 됨" }
  ]
}
```

---

## 3. `expected_flow` step 종류 (source → sink 순서)

| op | 의미 | 주요 필드 |
|---|---|---|
| `source` | source 경계 | `label`, `role`("control") |
| `store` | 메모리 기록 | `field`, `offset`, `size`, `carries`, `branch` |
| `load` | 메모리 읽기 | `field`, `offset`, `size` |
| `copy` | 구조체/범위 복사 | `edge`("range_copy"/"external_memcpy"), `detail` |
| `phi` | 분기 병합 | `field`, `offset`, `note` |
| `deref` | 포인터 역참조 체인 | `detail` (예: "2-deref") |
| `call_out_mem` | 외부/헬퍼가 메모리에 기록 | `detail` |
| `branch_cond` | 분기 조건 (control) | `carries`, `note` |
| `sink` | sink 도달점 | `label` |

`forbidden_flow`: 거치면 안 되는 경유점. `node`/`field`/`offset`/`carries`/`reason`.
→ **끝점이 우연히 맞아도, 엉뚱한 경유점으로 도달하면 틀린 것**임을 명시한다(예: kill된 store, 다른 field).

---

## 4. `offset` 규약 (의미명 + offset 병기)

`field`는 사람이 읽는 의미명, `offset`은 convention-free 엔진이 쓰는 byte 위치다. 둘 다 적는다.

- **Tier0 (cpp_like)**: 정확한 byte offset. 표준 레이아웃이라 `offsetof`로 계산 가능.
  - 예: `FTraceLargeLike` → `Inner.Secret`=256(0x100), `Other`=264, `Transform.Translation.X`=268, `FHugeLike.Fields[10]`=16424.
- **Tier2/3 (UE)**: 절대 offset은 **빌드/UHT가 결정** → 센티넬 사용.
  - `"offset": "pdb"`  — UObject 헤더/FTransform 뒤 등 빌드 결정 offset (PDB overlay 영역, 매트릭스 §13)
  - `"offset": "heap"` — TArray/TMap/FString 등 heap 간접 너머
  - 안정적인 within-struct offset은 정수로(예: `FVector.X`=0, `.Y`=8; `FTraceItem.ItemId`=0, `.Count`=4).

> 엔진 core는 field 이름을 쓰지 않으므로(이름=overlay), 채점의 본질은 `carries`(어느 source) + `op`/`edge` + 순서다.

---

## 5. 새 케이스 추가 절차

1. C++ 케이스 작성 (`cpp_like/src/cases_fusion.cpp` 또는 `unreal_playground/.../TraceCases*.cpp`).
   - source/sink는 `dfb_source_A/B/C`, `dfb_sink_int` 사용. `TV2_NOINLINE`로 하드닝.
2. `manifests/cases_v2_manifest.json`에 케이스 항목 추가:
   - 끝점 정답(`expected_*` / `forbidden_*`)과 **의도된 흐름**(`expected_flow` / `forbidden_flow`)을 손으로 작성.
   - offset은 §4 규약대로 (cpp는 `offsetof`로 확인 권장).
3. `python tools/generate_expected_from_manifest.py` → expected JSON 재생성.
4. `build.sh` → Ghidra 추출 → `tools/run_v2_engine.py`로 11_엔진 대조.

---

## 6. 11_ 엔진과의 호환

- 현재 11_ `ExpectedValidator`는 `expected_data_sources / control / global / forbidden_*`만 읽어 PASS/FAIL을 낸다.
- `expected_flow` / `forbidden_flow`는 **모르는 필드라 무시**되므로 기존 채점을 깨지 않는다(additive).
- 용도: ① 11_ 개발자가 "엔진이 이 경로로 가야 한다"를 보고 맞추는 사양서, ② 향후 11_에 **경로 검사기**를 붙이면
  실제 slice 경로가 `expected_flow`를 거치고 `forbidden_flow`를 피하는지까지 자동 검증 가능 → 우연 정답 차단.

---

## 7. 왜 흐름까지 담는가

끝점만 검사하면, 분석기가 **틀린 경로로 우연히 맞는 source**에 도달해도 PASS가 된다(과대근사 등).
중간 흐름을 정답에 박으면 *"진짜 그 길로 갔는가"* 를 사양으로 못 박을 수 있다.
특히 `forbidden_flow`는 실제로 발견된 버그(예: `TV2U008`이 UObject 포인터 경유로 옆 field `Other`(B)를
끌고 온 false positive)를 정답지 차원에서 명시적으로 금지한다.
