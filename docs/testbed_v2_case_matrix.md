# Testbed V2 — Case Matrix (BackwardSlice 최종 관문)

> 목적: BackwardSlice 엔진이 **충분히 크고 복잡한 구조체 / 엔진형 레이아웃**에서
> field-sensitive · range-sensitive 데이터 흐름을 끝까지 보존하는지 검증한다.
> 정확도의 핵심은 **"맞는 source를 찾는 것"** 만이 아니라 **"틀린 source(forbidden)를 끌고 오지 않는 것"** 이다.
>
> 정합성: 케이스 스키마는 **`11_tracing_Data_Origin_lowpcode`의 V8 §24 스키마**를 따른다.
> (`expected_data_sources / expected_control_sources / expected_global_sources /
>  forbidden_data_sources / forbidden_control_sources / expected_features / allowed_warnings`)
> + V2 확장 필드(`expected_memory_ranges / forbidden_memory_ranges`).
> 09식 `expected_sources / forbidden_sources`는 호환 규칙으로 각각 data로 간주된다.

---

## 엔진 현황 기반 판정 (11_tracing_Data_Origin_lowpcode V8/New V1, Phase 6, PASS 370/FAIL 118)

이 매트릭스는 추측이 아니라 **엔진이 실제로 통과/실패시키는 케이스**에 맞춰 severity를 부여한다.
엔진은 **convention-free + byte-range/offset 기반**이며 **struct field 이름을 쓰지 않는다**(PDB=Phase 7 overlay).
따라서 "field-sensitive"는 **컴파일된 레이아웃의 byte-offset sensitive**를 의미한다.

| 질문 | 엔진이 이미 하는 것 | 본 매트릭스 결정 |
|---|---|---|
| **Q1 phi 머지** | data=union, 분기 조건=별도 `control` edge. DFB010/014 PASS. data-only slice는 control edge 제외 | **`TV2C004`로 통합** — struct field에 phi(data union {A,B}) + control(C) 동시. C는 data로 forbidden |
| **Q2 strong-update kill** | **YES, byte 단위.** latest-byte coverage + byte-lane narrowing. partial-overwrite gate PASS 60 (DFB046/049) | `TV2C005`/`TV2U006` = **`[core-regression]` PASS 필수** (warning 완화 아님) |
| **Q3 heap/컨테이너 deref** | 1-deref heap(030/031)·return-buffer(053) PASS, double-deref 추가됨. **nested deep-field passthrough(DFB055) = 현재 FAIL 프론티어** | Tier3 deref 깊이로 등급화: 0-deref=`[core-regression]`, 1-deref=`[target]`, 2+deref=`[frontier]` |
| **Q4 field/element sensitivity** | offset/byte/bitfield sensitive (DFB034/035 PASS). 단 배열 index는 offset 기반→상수 index만 분리, 변수 index는 widened | 단일 bitfield/array-index는 09(DFB034/043/044)에 위임. V2는 fusion만: `C006`(wide-copy 분리)·`U007`·`R002`(컨테이너 상수 index)=`[core-regression]` |

**severity 태그 정의**:
```text
[core-regression] = 엔진이 이미 통과하는 능력의 확장. 모든 빌드 프로파일에서 PASS 필수.
[target]          = 근접 능력(double-deref 등). PASS 목표, 미달 시 정직한 partial 허용.
[frontier]        = DFB055류 현재 개발 프론티어. "최소 1차 연결 또는 정직한 unresolved/widened".
[degrade-ok]      = widened 허용(변수 index/budget 초과). false source만 절대 금지.
공통 불변식: 어떤 등급에서도 forbidden source 도달 = FAIL. widened여도 false source 금지.
```

---

## 0. 공통 규약

```cpp
extern "C" __declspec(noinline) int  dfb_source_A();   // 추적 대상 source
extern "C" __declspec(noinline) int  dfb_source_B();   // 보통 forbidden (오염 분리 검증용)
extern "C" __declspec(noinline) int  dfb_source_C();   // 3-way 분기/머지용
extern "C" __declspec(noinline) int  dfb_sink_int(int);// anchor = (callee=dfb_sink_int, arg_index=0)
```

- 모든 케이스는 `dfb_sink_int(...)` 호출의 **arg0**을 anchor로 backward slice.
- source 함수는 `NOINLINE` + 반환값을 `volatile`로 한 번 받아 옵티마이저가 죽이지 못하게 한다.
- ID 체계: `TV2C###` (Tier0 pure C++) · `TV2U###` (Tier2 USTRUCT) · `TV2R###` (Tier3 runtime container).

판정 기준:
```text
PASS  = expected_sources 전부 도달 AND forbidden_sources 0개 도달
FAIL  = forbidden 1개라도 도달(false positive)  OR  expected 누락(false negative)
DEGRADE-OK = budget 초과 시 crash 없이 partial_summary + warning (Tier4/5)
```

---

## 1. Tier 0 — Pure C++ Synthetic Fusion (`TV2C`)

**Tier0는 fusion 전용이다.** 09_testbed가 단일 기능(union·bitfield·array-index·sret·swap·double-ptr 등)을
이미 격리 검증하므로, V2 Tier0는 그것들을 **하나의 large/nested struct 흐름에 섞은 경우**만 다룬다
(설계서 §2 전제: "단일은 09가 통과, fusion에서 깨진다"). 단일 기능 재테스트는 전부 제거했다.
모두 `samples/testbed_v2/cpp_like/` 에 일반 C++로 빌드.

| ID | severity | 케이스 | 융합(09 단일 → V2 fusion) | expected (data/control) | forbidden | features |
|---|---|---|---|---|---|---|
| **TV2C001** | core-regression | LargeStructCopy (`B = A`) | DFB040 field + DFB053 large → wide copy 후 `B.Inner.Secret` **narrow demand 보존** | data: A | B | large_struct, range_copy, demand_range |
| **TV2C002** | core-regression | DeepNested 4-depth (`A.T.Trans.X` 등) | DFB045 nested → 더 깊은 chain을 large struct 안에서 | data: A | B | nested_struct, field_offset |
| **TV2C004** | core-regression | **ControlVsDataStructPhi** (`B.Inner.Secret = cond? src_A: src_B; cond=src_C()`) | DFB010 phi + DFB014 control을 struct field에 **동시** → 값은 data{A,B}, 분기조건은 control{C}, **C는 data로 forbidden** | data: A, B · control: C | **data: C** | branch_phi, control_dependency, struct_merge |
| **TV2C005** | core-regression | **PartialOverwriteKill** (`B=A; B.Inner.Secret=src_C(); sink(...)`) | DFB053 copy + DFB005 kill + DFB046 partial **3중 fusion** → 옛 source(A) **죽어야** | data: C | **A**, B | partial_overwrite, kill, range_subtract |
| **TV2C006** | core-regression | **WideCopyNarrowForbidden** (`B=A; sink(B.Other)`, A.Inner만 오염) | 신규 — wide copy가 무관 field로 **번지면 안 됨** | data: (B.Other 값) | **A** | range_copy, field_sensitive, false_positive_guard |
| **TV2C011** | frontier | **IntraProcPointerChain** (`p->q->r->Secret`, 함수 내 3단) | DFB055는 interproc deep-field; 이건 **intra-proc** 3-deref 변형 | data: A | B | pointer_chain, indirect_load |
| **TV2C012** | core-regression | **RefAliasIntoField** (`int& r = A.Inner.Secret; r = src_A();`) | DFB033 must-alias + struct field → reference 별칭이 large-struct 슬롯 갱신 | data: A | B | alias, reference, field_sensitive |
| **TV2C013** | core-regression | **SubStructMemcpy** (`memcpy(&B.Inner, &A.Inner, sizeof Inner)`) | DFB120-123 memcpy + nested field → **sub-struct만** 부분 복사 | data: A | B | external_memcpy, range_copy, partial_range |
| **TV2C017** | core-regression | **DiamondPhiFieldSplit** (분기마다 *다른* field에 source) | 신규 — phi + field 분리, sink하는 field에 따라 source 선택 | data: (sink field 의존) | (반대 field) | branch_phi, field_sensitive |
| **TV2C018** | core-regression | **CallOutMemMutate** (helper가 `&bigstruct` 받아 한 field만 set) | DFB058 outparam summary + large struct → call_out_mem boundary | data: A | B | call_out_mem, summary |
| **TV2C020** | target | **VeryLargeStruct (16KB+, 수십 field)** | 신규(scale) — 거대 struct에서 range edge 폭발/budget 안 함 | data: A | B | large_struct, scale, range_copy |

> **09 중복으로 제거된 케이스** (단일 기능은 09가 이미 커버): `ReturnBuffer→DFB053`,
> `Union→DFB042`, `Bitfield→DFB034/035`, `ArrayConstIdx→DFB043`, `ArrayVarIdx→DFB044`,
> `SwapSelfOverlap→DFB066`, `DoublePtrOutParam→DFB023`, `OffsetPadding/Packed→DFB047`,
> `ControlOnly→DFB014`(C004에 융합). → 필요 시 09 회귀로 검증.
>
> Tier 0 false-positive 관문: **C005·C006·C017 = `core-regression`** (forbidden 새면 회귀).
> **C011(intra-proc 3-deref)만 `frontier`** (DFB055 사촌). C020은 scale `target`.

---

## 2. Tier 2 — Unreal USTRUCT / UCLASS (`TV2U`)

UHT/UPROPERTY/PDB 심볼이 붙은 native PE에서 Tier0 패턴 재현 + UE 빌드 통과.
`samples/testbed_v2/unreal_playground/` 의 `ATraceCases` Actor에 `UFUNCTION()`으로 배치.

> **Tier2/3는 09와 중복 0** — 09에는 UE 타입이 전무하다. 같은 로직을 **UE 실제 레이아웃**에서 재현해
> "vtable@0 / GENERATED_BODY / 정렬 / 큰 패딩이 byte-offset 모델을 깨는가"를 본다(아래 §대응 = 동일 로직 출처).

| ID | 케이스 | 대응 로직 (Tier0/09) | features |
|---|---|---|---|
| **TV2U001** | DirectField (`USTRUCT` 단일 field) | — | unreal_ustruct, field_offset |
| **TV2U002** | USTRUCT LargeStructCopy | TV2C001 | unreal_ustruct, large_struct, range_copy |
| **TV2U003** | Nested USTRUCT (`FTraceLarge.Inner.Secret`) | TV2C002 | unreal_ustruct, nested_struct |
| **TV2U004** | USTRUCT ReturnBuffer (UE 레이아웃 sret) | DFB053 (09) | unreal_ustruct, sret |
| **TV2U005** | ControlVsDataStructPhi (USTRUCT) | TV2C004 | unreal_ustruct, branch_phi, control_dependency |
| **TV2U006** | **USTRUCT PartialOverwriteKill** | TV2C005 | unreal_ustruct, partial_overwrite, kill |
| **TV2U007** | **USTRUCT WideCopyNarrowForbidden** | TV2C006 | unreal_ustruct, field_sensitive, false_positive_guard |
| **TV2U008** | GENERATED_BODY 패딩 뒤 field (vtable/UObject 헤더 오프셋) | DFB047 (09) + UE 헤더 | unreal_ustruct, uobject_header, large_offset |
| **TV2U009** | UObject 멤버 경유 (`this->MemberStruct.Inner.Secret`) | TV2C011 | uclass, member_access, pointer_chain |
| **TV2U010** | UPROPERTY 다수 + 일부만 오염 (overlay 이름 vs core range 분리) | TV2C006 | unreal_ustruct, field_sensitive, type_overlay |

> allowed_warnings에 `type_overlay_missing` 허용. **core는 PDB field name 없이 offset/size만으로 PASS 해야 한다** (설계서 §13 금지조항).

---

## 3. Tier 3 — Unreal Container / Runtime Layout (`TV2R`)

실제 엔진 자료구조. 내부 레이아웃(heap indirection, inline allocator 등)을 코어 range 모델로 견디는지.

deref 깊이 = 엔진 능력 등급. **0-deref(in-struct 값)=`core-regression`, 1-deref(heap ptr+offset)=`target`, 2+deref=`frontier`(DFB055).**

| ID | severity | 케이스 | 대상 타입 | deref | 검증 포인트 | features |
|---|---|---|---|---|---|---|
| **TV2R003** | core-regression | FVector field (`V.X`만 오염) | `FVector` | 0 | float field, 16B 정렬 | engine_struct, float_field |
| **TV2R004** | core-regression | FTransform Translation 왕복 | `FTransform` | 0 | `SetTranslation/GetTranslation` 경유 | engine_struct, nested_struct, call_out_mem |
| **TV2R006** | core-regression | FName 비교/저장 | `FName` | 0 | ComparisonIndex 정수 레이아웃 | engine_struct, name_index |
| **TV2R001** | target | TArray element field [상수 index] | `TArray<FTraceItem>` | 1 | `Items[0].ItemId` — heap data ptr + element offset | container_layout, array_index, heap_indirection |
| **TV2R002** | target | **TArray wrong-index forbidden** [상수] | `TArray<FTraceItem>` | 1 | `Items[0]` 오염, `Items[1]` read → 분리. **forbidden 도달 시 FAIL** | container_layout, element_sensitive, false_positive_guard |
| **TV2R007** | target | **TObjectPtr 체인** | `TObjectPtr<UObj>` | 1 | obj ptr → field 로드, 1단 역참조 | pointer_chain, object_ptr |
| **TV2R012** | target | FVector SIMD copy (Development opt) | `FVector` | 0~1 | movaps/memcpy intrinsic lowering | engine_struct, simd_copy, range_copy |
| **TV2R005** | frontier | FString 문자버퍼 | `FString` | 2 | TArray<TCHAR> heap 버퍼 indirection | container_layout, heap_indirection, string |
| **TV2R008** | frontier | **Component pointer chain** | `UActorComponent*` | 2 | `Comp->SubStruct.Secret` 2단 체인 (DFB055류) | pointer_chain, component, indirect_load |
| **TV2R009** | frontier | TMap value field | `TMap<int,FTraceItem>` | 2 | `Map[k].ItemId` — bucket 레이아웃 | container_layout, map, heap_indirection |
| **TV2R010** | frontier | **Nested container** | `TArray<TArray<int>>` | 3 | `Outer[0][0]` 2중 indirection | container_layout, nested_container |
| **TV2R011** | frontier | TArray of large struct (16KB elem) | `TArray<FTraceLarge>` | 1+ | element copy + range, scale | container_layout, large_struct, scale |

> `frontier` 케이스 성공 기준 = **"최소 1차 dataflow 연결 또는 정직한 `unresolved_call_boundary`/`widened`"**.
> 어떤 등급에서도 **forbidden 도달 = FAIL** (widened여도 false source 금지). R002 wrong-index는 `target`이지만 false-positive 관문이라 forbidden 엄격 적용.

---

## 4. Tier 4 — Build Variant (2종 풀 + 1종 스모크)

새 케이스가 아니라 **Tier0~3 케이스를 빌드 프로파일별로 재빌드**해 lowering 차이를 본다.
프로파일 축이 바꾸는 것은 **최적화 정도** 하나뿐이고, 결정적 분기점은 **Debug vs Optimized**다.
**11_엔진 core는 convention-free + 심볼 비의존**(PDB=Phase 7 overlay)이므로, Shipping이 Development과
다른 부분(심볼 stripping)은 core가 어차피 보지 않는다. 따라서 4종 풀매트릭스는 과하며 아래로 줄인다.

| 프로파일 | 컴파일 옵션 | 적용 범위 | 시험 대상 |
|---|---|---|---|
| **P0 DebugGame+PDB** | `/Od /Zi` UE DebugGame | **전 케이스 (풀)** | 기준선. 경계·심볼 보존. 여기서 FAIL = 최적화 무관 **core 버그**(설계 sanity) |
| **P1 Development+PDB** | `/O2 /Zi` UE Development | **전 케이스 (풀)** | **핵심 관문.** memcpy 인라인/SIMD lowering, byte-range / inline-copy / range summary (cf. DFB120-123 PASS) |
| **P3 Shipping** | 심볼 최소, aggressive inline/LTCG | **대표 5~8개 (스모크)** | graceful degradation + source/sink 하드닝(NOINLINE/volatile) 생존 확인 |

**제외**: 기존 P2(Development-opt/LTCG-ish)는 작은 case 함수에선 P1과 codegen이 사실상 동일하여 중복 → 삭제.

**왜 2종 + 스모크인가**:
```text
프로파일이 바꾸는 유일한 축 = 최적화 정도.
  Debug → Optimized 가 큰 분기 (memcpy가 call로 남느냐 / 인라인·SIMD로 펼쳐지느냐).
  Optimized 내부(Development vs Shipping)는 codegen이 비슷하고 차이는 심볼 stripping.
  core는 심볼을 안 보므로 Shipping 고유 시험거리는 케이스마다 반복할 필요 없는 2가지뿐:
    (1) 심볼 없을 때 crash/false-source 안 내는가  (2) NOINLINE/volatile 하드닝이 버티는가
  → 따라서 Shipping은 대표 subset 스모크로 충분.
```

**P3 스모크 대표 케이스** (각 능력군 1개씩): `TV2C002`(nested), `TV2C005`(partial-overwrite kill),
`TV2C013`(sub-struct memcpy), `TV2C017`(phi field-split), `TV2R001`(TArray 1-deref), `TV2C020`(거대 struct).

판정:
```text
P0  : 전 케이스 PASS 필수 (기준선)
P1  : 전 케이스 PASS 필수 (핵심)
P3  : 스모크 subset — 정확도 유지 또는 정직한 partial+warning 이면 OK.
      어떤 프로파일에서도 silent skip / false source 도달 = FAIL.
```

빌드 산출물: `samples/testbed_v2/build_profiles/{P0,P1,P3}/*.exe + *.pdb`

> arch 축과 직교: arch 검증은 **P0(Debug) 한 프로파일로 4-arch**, profile 검증은 **x64 한 arch로 P0/P1/P3**.
> 두 축을 곱하지 않는다 (§Architecture Coverage 참조).

---

## 4.5 Architecture Coverage (x86 / x64 / armv7 / aarch64)

11_엔진은 `ArchitectureSpec`으로 멀티아치(progress_log: x86/x86_64/AArch64/ARMv7 sample root) 회귀 중이므로
V2도 4-arch를 내야 한다. 단 **UE5는 32비트를 전부 버렸다**(Win32·armeabi-v7a 미지원, arm64 전용).
따라서 4-arch는 **2개 레이어로 분담**한다.

| arch | Tier 0 (pure C++, 알고리즘 검증) | Tier 2/3 (UE 레이아웃 검증) |
|---|---|---|
| **x64** | clang/mingw native (PE) | **UE Win64** native (PE+PDB) |
| **aarch64** | NDK clang `aarch64-linux-android` (ELF) | **UE Android arm64** (`lib<Proj>-arm64.so`, ELF) |
| **x86 (32)** | NDK clang `i686-linux-android` (ELF) | ✗ UE5 미지원 → **Tier0로만 커버** |
| **armv7 (32)** | NDK clang `armv7a-linux-androideabi` (ELF) | ✗ UE5 미지원 → **Tier0로만 커버** |

근거 / 무손실 논리:
```text
- 알고리즘의 멀티아치 검증(32비트 포인터·정렬·패딩 포함)은 Tier0가 4-arch로 전담.
  → 같은 struct 정의를 4타깃으로 빌드하면 32비트 레이아웃까지 그대로 시험됨.
- Tier2/3은 "UE 실제 레이아웃(vtable@0, GENERATED_BODY, 정렬, 큰 패딩)이 byte-offset 모델을 깨는가"가 관심사.
  x64(데스크톱) + arm64(모바일) 두 대표 레이아웃이면 충분.
  32비트 UE 레이아웃은 타깃 자체가 없어 검증 대상이 없음 → 잃는 것 없음.
```

차원 축소 (arch × profile 직교, 곱하지 않음):
```text
arch 검증     : P0(DebugGame) 한 프로파일로 4-arch.
profile 검증  : x64 한 arch로 P0/P1 + P3 스모크.
→ 전 케이스 × 4-arch × 전-profile 카르테시안(과대)을 피한다.
```

Tier0 NDK clang 빌드 예 (단일 툴체인, 4타깃):
```bash
NDK=$ANDROID_HOME/ndk/25.1.8937393/toolchains/llvm/prebuilt/windows-x86_64/bin
$NDK/clang --target=i686-linux-android24      -O0 -g case.c -o case.x86.elf
$NDK/clang --target=x86_64-linux-android24    -O0 -g case.c -o case.x64.elf
$NDK/clang --target=armv7a-linux-androideabi24 -O0 -g case.c -o case.armv7.elf
$NDK/clang --target=aarch64-linux-android24   -O0 -g case.c -o case.arm64.elf
```

UE Android(arm64) 빌드 사전 설정 (1회):
```text
1. Engine\Extras\Android\SetupAndroid.bat 실행 (또는 UE Project Settings → Android SDK 경로 지정)
2. NDK 경로 = ...\Android\Sdk\ndk\25.1.8937393  (r25b, UE5.1 권장과 일치)
3. NDKROOT / NDK_ROOT 환경변수 비어 있으면 설정
```

---

## 5. Tier 5 — Scale Profiling (pass/fail 아님, 측정)

`YourGameModule` subset(= `Case_*` / `Trace_*` / `dfb_*` 만 추출)에서 병목 측정.

측정 항목: function count · pcode op count · graph node/edge · memory-overlap candidate · range-copy effect · query time · peak RSS · unresolved call · budget_exceeded count.

Scale Guard(설계서 §12) 초과 시 반드시: `budget_exceeded` / `partial_summary` / `unresolved_range_boundary` / `widened_memory_range` 중 하나를 내보내고 **crash·silent-skip·false-source 금지**.

권장 추출/분석 옵션:
```bash
--include-function "Case_*" --include-function "Trace_*" --include-function "dfb_*"
--summary-first --no-full-graph-export --export-query-subgraph-only
--max-pcode-ops-per-function 50000 --max-memory-overlap-candidates 64
--max-range-copy-effects 10000 --max-demand-splits 256
```

---

## 6. Expected JSON 예시 (V2 확장 포함)

```json
{
  "id": "TV2U006",
  "binary": "TraceUnrealPlayground",
  "function": "ATraceCases::Case_TV2U006_PartialOverwriteKill",
  "severity": "core-regression",
  "anchor": { "callee": "dfb_sink_int", "observed_storages": [0] },
  "expected_data_sources": ["dfb_source_C.ret"],
  "expected_control_sources": [],
  "expected_global_sources": [],
  "forbidden_data_sources": ["dfb_source_A.ret", "dfb_source_B.ret"],
  "forbidden_control_sources": [],
  "expected_features": ["unreal_ustruct", "partial_overwrite", "kill", "range_subtract"],
  "expected_edge_kinds": ["memory", "call_out_mem"],
  "expected_memory_ranges": [
    { "semantic": "B.Inner.Secret", "offset_hint": "auto", "size": 4, "source": "dfb_source_C" }
  ],
  "forbidden_memory_ranges": [
    { "semantic": "B.Inner.Secret(old)", "source": "dfb_source_A" }
  ],
  "allowed_warnings": ["type_overlay_missing"]
}
```
> `semantic`은 overlay/debug 힌트일 뿐, **core 판정은 source 도달 + edge/range 동작이 우선**(설계서 §10 주의).

---

## 7. 커버리지 요약

| Tier | 케이스 수 | core-regression | target | frontier |
|---|---|---|---|---|
| 0 Pure C++ fusion | 11 | C001, C002, C004, C005, C006, C012, C013, C017, C018 | C020 | C011 |
| 2 USTRUCT | 10 | U001~U010 (Tier0 대응) | — | — |
| 3 Container | 12 | R003, R004, R006 | R001, R002, R007, R012 | R005, R008, R009, R010, R011 |
| 4 Build variant | (0~3) × {P0,P1 풀 + P3 스모크} | P0/P1 PASS 필수 | — | P3 정직한 partial 허용 |
| 5 Scale | 측정 | — | — | budget/degrade guard |

> Tier0는 09 단일 중복 ~11개를 제거한 **fusion 전용 11개**. 단일 기능 회귀는 09_testbed가 담당.

**최종 관문 판정 (엔진 현황 반영)**:
1. **`core-regression` 전체가 모든 빌드 프로파일에서 PASS** = 엔진의 기존 능력(byte-range·kill·control/data 분리)이 큰 구조체로 안전하게 확장됨.
2. **false-positive 관문**(C005·C006·C017·U006·U007·R002)에서 **forbidden 0 도달**.
3. **`frontier`(C011, R005/R008/R009/R010)에서 false source 0** — 연결을 못 해도 `unresolved`/`widened`로 정직하게. 이게 DFB055 다음 개발 타깃과 정렬됨.

→ 1·2 달성 = "크고 복잡한 구조체 대응 완료". 3은 엔진 로드맵(Phase 6→deep-field)과 함께 전진.
