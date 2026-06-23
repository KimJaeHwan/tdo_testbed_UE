# 11_ BackwardSlice 엔진 — 실패 분석 & 수정 방안

Testbed V2(10_)의 전 케이스를 11_ 엔진에 빌드 변형별로 돌려 수집한 실패를 근거로,
**11_ 코드 수정 방안**을 정리한다. (이 문서는 보고서이며 11_ 코드는 수정하지 않는다.)

- 데이터: `dist/failure_report.json` (수집기 `tools/collect_failures.py`)
- 케이스 정답·흐름: `cpp_like/`·`unreal_playground/`의 manifest/expected, 흐름은 `dist/flows.md`

---

## 1. 전 변형 결과

| 변형 | PASS | FAIL | false positive | 비고 |
|---|---|---|---|---|
| tier0 P0(-O0) x86   | 7 | 4 | 0 | 32-bit가 최고 |
| tier0 P0(-O0) x64   | 6 | 5 | 0 | |
| tier0 P0(-O0) armv7 | 6 | 5 | 0 | C011/C017 **크래시** |
| tier0 P0(-O0) aarch64 | 6 | 5 | **1** | C002 nested FP |
| tier0 P1(-O2) x64   | 2 | 9 | 0 | 최적화가 정밀도 붕괴, C002 크래시 |
| UE Development(/O2)  | 7 | 15 | 0 | R001/R009/R010 크래시 |
| UE DebugGame(P0)    | 2 | 20 | **2** | U008/U009 FP, R005 크래시 |

핵심: **FAIL은 대부분 false-negative(정밀도 프론티어)지만, ① 엔진 크래시 7건 ② false positive 3건**이
섞여 있다. 이 둘이 최우선 수정 대상이다(크래시·오답은 frontier 정밀도보다 위험).

---

## 2. 측정 방법 & 한계

- 빌드: Tier0=NDK clang 4-arch(P0/P1), UE=Win64 Editor(Development/DebugGame). Ghidra Low P-code 추출 → 11_엔진.
- **한계**: `expected_flow`의 offset 정밀 대조는 Debug(P0)에서만 유효하다. `/O2`는 `B=A` 복사가 SIMD/레지스터로
  내려가 **메모리 store 자체가 사라질 수 있어**, 그 변형의 FAIL은 "엔진 한계 + 최적화 lowering"이 섞인다.
- 따라서 **순수 레이아웃/엔진 능력 판단은 P0(-O0)·DebugGame 기준**으로 본다. /O2는 robustness(크래시·FP) 신호로만 본다.

---

## 3. 근본 원인 클러스터 (우선순위순)

### C0. 엔진 크래시 — `list index out of range` (최우선, 7건)

설계 §12 *"budget 초과 시에도 crash 금지"* 불변식을 직접 위반.

```
tier0 armv7 P0  : TV2C011(pointer_chain), TV2C017(phi_field_split)
tier0 x64 P1    : TV2C002(deep_nested)
UE Dev          : TV2R001(TArray), TV2R009(TMap), TV2R010(nested container)
UE DebugGame    : TV2R005(FString)
```

- **증상**: 특정 arch/opt/컨테이너 조합에서 분석 중 `IndexError`로 중단.
- **원인 가설**: 가드 없는 리스트 인덱싱. 후보 — predecessor가 없는 노드에 `[0]` 접근, varnode `inputs[i]`
  존재 가정, `rsplit(...)` 결과 길이 미확인 등. (컨테이너/포인터 체인에서 예상 못 한 P-code 형태 진입 시.)
- **11_ 위치(후보)**: `analysis/slice_graph_builder.py`의 varnode/edge 인덱싱부, `_register_byte_range`/
  `_memory_range_for_key`의 `rsplit` 파싱(이미 length 체크 있는 곳도 있으나 누락 경로 존재 추정).
- **수정 제안**:
  1. 분석 단위(함수/케이스)를 try/except로 감싸 **부분 실패를 `unresolved`/`analysis_error`로 강등**, 전체 배치는 계속(설계 §12 degrade 정책).
  2. 크래시 지점 5개를 traceback으로 특정 후 인덱싱 가드 추가.
  3. 회귀: `collect_failures.py`에서 ERROR=0을 게이트로.

### C1. 스택 store↔load 매칭 실패 — `OBSERVED_MEMORY:RSP/ESP/sp` (cut 22건, 최다)

- **증상**: sink로 가는 load가 스택 메모리 셀에서 멈추고(`observed_memory`), 같은 셀의 store로 못 이어짐.
- **원인(확인)**: `analysis/slice_graph_builder.py:_memory_range_for_key`가 스택 range identity를
  `"{func}:{ctx}:stack:{base}"`로 만든다(L1486). 즉 **base가 다르면(예: store는 `RBP`, load는 `RSP`) 다른 객체로 취급** → overlap 매칭 불가.
  `/O2`(frame pointer 생략)는 전부 `RSP`-relative이고 prologue 이후 SP가 이동하면 offset 기준도 어긋난다.
- **11_ 위치**: `_memory_key_for`(L1445-1470), `_memory_range_for_key`(L1472-), `MemoryModel.stack_key`.
- **수정 제안**:
  1. **프레임 정규화**: prologue에서 `RBP = RSP + k`, `RSP -= frame_size`를 추적해 모든 스택 접근을
     단일 기준(canonical frame base)으로 환산 → store/load가 같은 identity·offset을 갖게.
  2. SP가 동적으로 바뀌는 함수(`/O2`, alloca)에서는 SP delta를 상태로 들고 다니며 offset 보정.
  3. base를 못 합치면 같은 함수/컨텍스트 내 스택은 **보수적으로 동일 identity로 묶고 offset overlap**으로 매칭(과소연결 < 과대연결, 단 C4 FP 주의).
- **영향**: TV2C001, C018, C020, U002~U004 등 "store→(copy)→load" 다수.

### C2. 호출 경계 반환 레지스터 바인딩 — `CALL_POST_REG:RBX/RCX/RDI` (cut 16건)

- **증상**: slice가 호출 직후 레지스터(특히 `RBX`)에서 멈추고 source(`dfb_source_*`)로 못 이어짐.
- **원인 가설**: source 호출의 반환값을 `RAX`로만 바인딩하는데, `/O2`는 반환값을 곧장
  callee-saved(`RBX` 등)로 옮겨 다음 호출을 넘기게 한다. `RAX→RBX` reg-to-reg move와
  source-boundary↔post-call-reg 연결이 빠져 끊긴다. (설계 §10.7 CALL_POST_REG는 safe-lazy 후보만 생성.)
- **11_ 위치**: `analysis/interprocedural_summary.py`의 call boundary/CALL_POST_REG 바인더(reg 후보 목록),
  `analysis/call_boundary_mapper.py`, source-boundary 바인딩.
- **수정 제안**:
  1. **use-after-call 레지스터 집합**을 1-pass로 수집해 그 레지스터에 대해서만 CALL_POST_REG를 실연결(설계 §10.7 Phase4 최적화 실구현).
  2. `COPY`/`MOV` 기반 reg-to-reg 전파를 data edge로 확실히 이어, 반환값이 `RAX`→`RBX`로 이동해도 추적 유지.
  3. DataFlowBenchBoundaryBinder가 반환을 `RAX` 고정이 아니라 **call 직후 첫 사용 레지스터**로 바인딩.
- **영향**: `/O2` 전반 + 단순 케이스(U001/R006 등)까지. **광범위**.

### C3. heap/컨테이너 간접 — `OBSERVED_MEMORY:unique`, `ResolveObjectHandle` (cut 10+건)

- **증상**: TArray/TMap/FString/TObjectPtr/컴포넌트 접근이 heap 데이터 포인터·핸들 해석 콜에서 끊김.
  (앞선 단독 분석: R007/R008은 `ResolveObjectHandle` 콜 경계, R001/R010은 heap data-ptr LOAD, R005는 unknown heap.)
- **원인**: HeapObject points-to·다단 deref summary 미구현(설계 §16 future work). TObjectPtr는 `ResolveObjectHandle`
  외부 콜로 내려가는데 그 summary가 없다.
- **11_ 위치**: `analysis/memory_model.py`(heap_key만 있고 points-to 없음), `analysis/external_summary.py`(known effect 레지스트리), `interprocedural_summary`.
- **수정 제안**:
  1. **allocation-site heap points-to** + double/triple-deref observed-memory summary(설계 §16.5, DFB055 연장).
  2. `external_summary`에 **UE 런타임 패스스루 요약** 추가: `ResolveObjectHandle`(TObjectPtr→raw, identity 보존),
     `TArray::operator[]`/`GetData`(base+index*stride→element), `FString` 버퍼 접근. trust=engine_overlay로 provenance 기록.
  3. 미해결 시 `unresolved_range_boundary`로 정직히 degrade(이미 일부 동작) — **단 false source 금지**.
- **영향**: R001/R002/R005/R007/R008/R009/R010/R011. 이건 **frontier**(즉시 PASS 목표가 아니라 로드맵).

### C4. FALSE POSITIVE — field offset 혼동 (3건, 위험도 최상)

- **증상**: 옳은 source 대신 **같은 구조체의 다른 field source**를 끌고 옴.
  ```
  UE DebugGame TV2U008/U009: self->Payload.Inner.Secret(A) 읽는데 self->Payload.Other(B) 도달
  tier0 aarch64 TV2C002    : Transform.Translation.X(A) 읽는데 Rotation.Y(B) 도달
  ```
- **원인 가설**:
  - U008/U009: 포인터 파라미터 `self` 경유 store들이 **base+offset로 분리되지 않고** 같은(또는 overlap되는) 키로 묶여,
    load가 엉뚱한 field store와 overlap 매칭됨.
  - C002(aarch64): nested float field 두 개(offset 268 vs 284)의 byte-range가 aarch64 codegen에서 부정확히 겹쳐 매칭.
  - 공통: `MemoryRange.overlaps()`(L70-71, `start<other.end and other.start<self.end`)가 **부분 겹침도 허용**하고,
    포인터 base가 다른데 같은 identity로 묶이면 오매칭.
- **11_ 위치**: `MemoryRange.overlaps`, byte-range 매칭(L489-510, L940-980), `_memory_key_for`의 register-base 처리(L1462).
- **수정 제안**:
  1. load의 demand range와 **정확히 같은 (identity, offset, size)** store를 우선 매칭하고, 부분 overlap은
     narrowing(설계의 byte-lane demand)으로만 좁히되 **다른 field로 번지지 않게** identity·base 동일성을 필수 조건화.
  2. **포인터 base 추적**: `self`(incoming ptr) + 상수 offset을 distinct memory cell로 키잉(C1 프레임 정규화와 동일 원리). 같은 base+다른 offset은 **다른 셀**.
  3. 매칭 모호 시 **source로 확정하지 말고** widen/unresolved (false negative ≪ false positive).
- **영향**: U008/U009, C002. **C1의 base 정규화와 한 묶음으로 해결될 가능성** 높음(둘 다 base/offset 정밀도 문제).

---

## 4. 우선순위 로드맵

```
1) C0 크래시 가드        — 즉시. 분석 단위 try/except degrade + 5개 지점 가드. (안전성)
2) C4 false positive     — 즉시. base+offset 정밀 매칭. (정확성, 가장 위험)
3) C2 call-boundary reg  — 높음. /O2·단순케이스까지 광범위 회복. (recall)
4) C1 stack 프레임 정규화 — 높음. C2/C4와 원인 공유(base/offset). (recall+정확성)
5) C3 heap/컨테이너 summary — 로드맵(frontier, DFB055 연장).
```

> C1·C2·C4는 **"base+offset를 얼마나 정확히 동일 객체로 묶고 분리하느냐"** 라는 한 뿌리를 공유한다.
> 프레임/포인터 base 정규화를 제대로 하면 셋이 함께 개선될 공산이 크다.

---

## 5. 수정 후 검증

```bash
# 11_ 수정 후 10_에서:
python tools/collect_failures.py        # dist/failure_report.json 갱신
#  게이트: ERROR(크래시)=0, false_pos=0, P0/DebugGame PASS 상승
python tools/verify_flows.py            # 정답지 자체 정합성(불변)
```

회귀 기준: **ERROR=0, FP=0**을 먼저 달성하고, 그다음 P0·DebugGame의 PASS 수를 올린다.
`/O2`는 lowering 영향이 커 PASS 목표가 아니라 "크래시·FP 없음 + 정직한 degrade"로 본다.

---

## 6. 부록 — arch/profile 의존성 관찰

- **32-bit(x86/armv7)가 64-bit(x64/aarch64)보다 PASS 약간 높음** — 레지스터 폭/호출 규약 차이로 추정.
- **aarch64에서만 C002 FP** — nested float field 매칭이 arch codegen에 민감(C4와 연계).
- **DebugGame이 /O2보다 낮은 PASS** — 비최적화라 `FVector` ctor 등 helper 콜이 인라인 안 돼 콜 경계(C2/C3) 폭증.
  → 즉 양극단(과한 opt / 과한 비-opt) 모두 **콜 경계·base 매칭**이 병목. 중간(Development)에서 가장 높음.
