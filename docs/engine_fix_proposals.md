# 11_ BackwardSlice 엔진 — 실패 분석 & 수정 방안 (증거 기반)

> 2026-06-28 status: M1의 `unknown unique` field-collapse false positive는
> `lowpcode_data_origin` 엔진에 반영됐다. 관측된 general-register pointer
> arithmetic은 이제 `unknown:register:<base>:offset:<n>` 셀로 분리되며,
> stack/frame pointer는 이 fallback에서 제외된다. UE DebugGame의
> TV2U008/TV2U009 forbidden `dfb_source_B.ret` 경로는 제거됐고, 현재는
> 보수적인 false negative로 남는다. M3/M4의 store/load 복원, container/heap,
> UE runtime summary 분석은 아직 참고 가치가 있어 이 문서는 유지한다.

Testbed V2(10_)의 전 케이스를 11_ 엔진에 빌드 변형별로 돌리고, **각 실패의 실제 slice 경로·메모리
키를 덤프해 원인을 확정**한 보고서다. (11_ 코드는 수정하지 않는다.)

**문장마다 출처 등급을 단다**: `[측정]`=실제 실행/덤프로 관찰, `[코드]`=11_ 소스 직접 확인,
`[가설]`=미검증 추론. 가설은 11_ 개발자가 traceback/계측으로 확인 후 채택할 것.

- 데이터: `dist/failure_report.json` (`tools/collect_failures.py`)
- 경로 증거: `tools/diagnose_case.py <case.json>` 로 재현 가능
- 정답·흐름: manifest/expected, `dist/flows.md`

> **정정 기록**: 초안은 7건을 "엔진 크래시(IndexError)"로 적었으나, 재확인 결과 그것은 엔진이 아니라
> 수집기(`collect_failures.py`)의 라벨 포맷 버그였다(수정 후 ERROR=0). 또 초안의 클러스터 C1을
> "스택 base(RSP/RBP) 불일치"로 적었으나, 실제 키를 덤프하니 **전부 RSP-relative**라 그 설명도 틀렸다.
> 아래는 그런 추정을 걷어내고 **덤프 증거만으로** 다시 쓴 것이다.

---

## 1. 결과 데이터 [측정]

| 변형 | PASS | FAIL | false positive |
|---|---|---|---|
| tier0 P0(-O0) x86   | 7 | 4 | 0 |
| tier0 P0(-O0) x64   | 6 | 5 | 0 |
| tier0 P0(-O0) armv7 | 7 | 4 | 0 |
| tier0 P0(-O0) aarch64 | 6 | 5 | **1** (C002) |
| tier0 P1(-O2) x64   | 2 | 9 | 0 |
| UE Development(/O2)  | 7 | 15 | 0 |
| UE DebugGame(P0)    | 2 | 20 | **2** (U008/U009) |

엔진 크래시(분석 예외) 0건. false positive 3건.

---

## 2. 핵심 발견 — 단일 근본 약점: 메모리 셀 해석 & store↔load 매칭 [측정]

PASS 케이스와 FAIL 케이스의 backward 경로는 **모양이 동일하고, STORE_VAL 노드의 메모리 키 한 곳만
다르다.** 아래는 `diagnose_case.py` 실제 덤프(주소는 빌드별로 다름):

**C005 (PASS)** — 해석된 스택 셀로 store↔load가 이어짐:
```
sink ← COPY(RDI) ← LOAD(unique) ←[memory] STORE_VAL mem:...:root:stack:RSP:-360:4
       ←[memory] COPY ←[data] SOURCE dfb_source_C        ← 정상 도달
```

**U008 (false positive)** — 같은 경로지만 STORE_VAL이 `unknown` 셀이라 **옆 field(B)의 store에 오매칭**:
```
sink ← COPY(RCX) ← LOAD(unique) ←[memory] STORE_VAL mem:unknown:unique:00004880:4
       ←[memory] COPY ←[data] SOURCE dfb_source_B        ← B(Other) 오답
```

**U001 / C001 / R007 / R001 (false negative)** — load한 셀에 **들어오는 store 엣지 자체가 없어 끊김**:
```
U001  CUT: OBSERVED_MEMORY mem:...:root:stack:RSP:-40:4      (해석된 스택셀인데 store 미연결)
C001  CUT: OBSERVED_MEMORY mem:...:root:stack:RSP:-360:4     (B=A memcpy 후 dest 셀, store 미연결)
R007  CUT: OBSERVED_MEMORY mem:global:18000aede:4            (TObjectPtr가 global 주소로 해석됨)
R001  CUT: OBSERVED_MEMORY mem:unknown:unique:00004a80:4     (TArray heap 셀)
```

**결론 [측정+코드]**: 엔진은 메모리 store↔load를 잇는 능력이 **있다**(C005). 단,
주소가 **포인터(`self`)·wide copy(memcpy)·컨테이너/heap**을 거치면 셀이
`mem:unknown:...` 또는 `mem:global:...`로 뭉개지거나(`[코드]` `_memory_key_for`가 미해결 시
`unknown_key`/`global_key`로 폴백, slice_graph_builder.py L1468-1470), 해석된 스택 셀이라도
store가 같은 키로 안 잡혀 매칭이 깨진다. 그 결과 두 실패 모드가 갈린다.

---

## 3. 실패 모드 (증거별)

### M1. false positive — 셀 뭉개짐으로 옆 field 오매칭 (최우선) [측정]

- **U008/U009**: `self->Payload.Inner.Secret`(A) 읽기인데, `self`(포인터) 경유 store들이 전부
  `mem:unknown:unique:...`로 뭉개져 **field offset이 구분되지 않는다.** load가 같은 unknown 클래스의
  **다른 field store(`Other`=B)** 에 매칭 → `dfb_source_B` 오답. (위 U008 덤프가 증거.)
- **원인 [측정+코드]**: 포인터 base+offset가 distinct 셀로 분리되지 않아 한 클래스로 합쳐짐.
  `MemoryRange.overlaps()`(`[코드]` L70-71)는 부분 겹침도 매칭하므로, 같은 unknown 클래스 안에서
  엉뚱한 store와 연결될 수 있다.
- **수정 방향 [가설]**:
  1. 포인터 파라미터(`self`)+상수 offset을 **distinct 셀 키**로 분리(스택 셀처럼). 같은 base 다른 offset = 다른 셀.
  2. `unknown`/포인터-경유 클래스에서는 **정확 (offset,size) 일치만 매칭**, 부분 overlap만으로 **source 확정 금지**
     (모호하면 widen/unresolved). false negative ≪ false positive.

### M2. false positive — 반환 레지스터 과연결 (aarch64) [측정]

- **C002(aarch64)**: `Translation.X`(A) 읽기인데 경로가 `SOURCE dfb_source_B.ret --[data]--> SINK`로
  **메모리(float store/load)를 안 거치고 두 번째 source 호출의 반환 레지스터가 sink에 직결**된다.
- **원인 [가설]**: 호출별 반환 레지스터가 재버전되지 않아, 나중 호출(B)의 반환값이 sink 인자 레지스터로
  과연결. (x64에선 미발생 → arch-specific codegen 의존.)
- **수정 방향 [가설]**: 각 CALL 직후 반환/clobber 레지스터를 새 버전으로 끊고(설계 §9.4 CALL_POST 재버전),
  sink 값은 실제 load한 메모리 셀로 라우팅. (M1과 함께 "값을 잘못된 곳에서 가져옴" 계열.)

### M3. false negative — store↔load 미연결 (recall, 광범위) [측정]

- **U001(단순 USTRUCT)**: load `stack:RSP:-40:4`에 store 엣지 없음 → 가장 단순한 케이스조차 실패.
- **C001/C020(wide copy)**: `B=A`가 memcpy로 내려가, dest 셀(`stack:RSP:-360`)에 **copy/store 엣지가 없음.**
  → wide-copy summary가 목적지 셀을 원본 셀로 못 매핑. (load는 만들되 source 측이 비어 끊김.)
- **원인 [가설]**: (a) store 노드가 load와 다른 키(offset/size/타이밍)로 등록돼 range-overlap이 못 잡거나,
  (b) memcpy/range-copy summary가 dest 바이트 레인지를 채우지 않음. (정확 원인은 store 노드 존재/키를
  11_ 측에서 덤프해 확인 필요 — 본 보고서는 "load 셀에 incoming 없음"까지만 [측정].)
- **수정 방향 [가설]**:
  1. store/load 키 정규화 일치(특히 /O2 SP-relative offset, 같은 셀이 같은 키 갖게).
  2. memcpy/struct-copy를 **dest[off..off+n] ← src[off..off+n] 범위 매핑**으로 요약(설계 byte-range overlap 확장).

### M4. false negative — heap/컨테이너/포인터 간접 (frontier) [측정]

- **R001/R009/R010/R011(TArray/TMap/nested)**: load 셀이 `mem:unknown:unique:...`(heap) → store 미연결.
- **R007/R008(TObjectPtr/컴포넌트)**: 객체가 `mem:global:...`로 해석(`ResolveObjectHandle` 경유) → 미연결.
- **R005(FString)**: heap 문자버퍼 unknown 셀.
- **원인 [코드+가설]**: heap allocation-site points-to·다단 deref summary 미구현(설계 §16 future work),
  TObjectPtr 해석 콜(`ResolveObjectHandle`)·`TArray::operator[]` summary 부재.
- **수정 방향 [가설]**: allocation-site points-to + double/triple-deref summary, UE 런타임 external summary
  (`ResolveObjectHandle` identity 보존, `TArray::GetData`+index→element). DFB055 프론티어 연장 — 즉시 목표 아님.

---

## 4. 우선순위 [가설 기반 판단]

```
1) M1 false positive (셀 뭉개짐)   — 즉시. 포인터 base+offset 분리 + unknown끼리 정확매칭. 가장 위험.
2) M2 false positive (반환 reg)    — 즉시. CALL 후 반환 reg 재버전.
3) M3 false negative (store-load)  — 높음. 키 정규화 + wide-copy 범위매핑. 단순케이스(U001)까지 회복.
4) M4 heap/컨테이너                 — 로드맵(frontier).
```

> M1·M2·M3는 모두 **"값을 어느 메모리 셀/레지스터에서 가져오느냐"의 정밀도** 한 뿌리다.
> 셀 해석(포인터 base+offset 분리, 키 정규화)을 고치면 FP·FN이 함께 개선될 것으로 본다 [가설].

---

## 5. 수정 후 검증 [측정 도구 제공]

```bash
python tools/collect_failures.py     # dist/failure_report.json — 게이트: ERROR=0, false_pos=0
python tools/diagnose_case.py <json> # 개별 케이스 경로/키 재확인
python tools/verify_flows.py         # 정답지 자체 정합성(불변)
```
회귀 순서: **false_pos=0** 먼저(M1/M2) → 그다음 P0·DebugGame PASS 상승(M3). `/O2`는 lowering 영향이
커 PASS 목표가 아니라 "FP 없음 + 정직한 degrade"로 본다.

---

## 6. 부록 — 관찰된 의존성 [측정]

- 32-bit(x86/armv7) PASS가 64-bit(x64/aarch64)보다 약간 높음.
- aarch64에서만 C002 FP(M2) 발생 — 반환 reg 과연결이 arch codegen에 민감.
- DebugGame이 /O2보다 PASS 낮음 — 비최적화라 `FVector` ctor 등 helper 콜 인라인 안 돼 셀이 더 자주
  포인터/unknown 경유(M1/M3/M4 증가). 양극단 모두 셀 해석이 병목.
