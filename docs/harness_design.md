# Harness 설계 (v2, 최종 합의) — 09/10/11 자동 반복 루프 멀티에이전트

테스트베드(10_)↔BackwardSlice 엔진(11_) 개발 반복 루프를 자동화하는 하니스의 **구현용 단일 설계서**.
Codex가 이 문서 하나로 구현한다(PR 단위 §16). 본 문서가 단일 진실. 구현 전 단계(설계 확정).

> 변경 이력: v1(스켈레톤) → v2(Opus 4.8 R1–R6 + 최종 정밀화 P1–P4 + GPT5.5 보강 반영).
> v1↔스켈레톤 정합 감사는 `docs/harness_design_audit.md`(v1 기준, 구현 PR에서 재정합).

---

## 0. 프로젝트 번호 (코드·문서 공통)
```
09 = tdo_testbed                 일반 C/C++ dataflow 테스트베드
10 = tdo_testbed_UE              Unreal/Engine-oriented Testbed V2 (이 repo)
11 = trace_data_origin_lowpcode  Low P-code SliceGraph / Backward Slice 엔진
```
하니스는 09/10/11을 **포함**하지 않고 **orchestration**한다(별도 제어 계층).

## 1. 설계 원칙 (불변)
```
P1 결정적 우선   : build/extract/analyze/verify/report/gate/cache/ledger를 먼저 안정화.
                   LLM은 판단 노드(triage/diagnose/adversary/fix/author/coverage)에만.
P2 반박 필수     : 모든 원인가설·수정·분류는 증거를 갖춰 adversary 반박을 통과해야 채택.
P3 오라클 무결성 : 테스트 통과 위해 expected/manifest 수정 절대 금지(gaming 차단).
P4 목적함수 사전식: PASS 단일 최대화 금지(§4).
P5 결정성·버전핀 : 툴체인(NDK/UE/Ghidra/MSVC) 버전 핀 + 자동선택 금지 + 결과에 기록.
P6 외부 구조화 메모리: 컨텍스트가 아닌 원장(JSON/sqlite)에 상태 보존(§9).
P7 휴먼 게이트   : 오라클 변경·엔진 merge·frontier/contradictory 판정은 사람(§13).
P8 증거가 척추   : 분류/진단/수정/오라클 — 무엇이든 재현 가능한 증거 없으면 게이트 통과 금지.
```

## 2. 권한 경계 (코드로 강제, P3/P7)
```
engine_fixer  : write=11 repo only,  read=09/10 artifacts·failure report.  main merge 금지(제안만).
case_author   : write=proposed_cases/ only.  expected/manifest 직접수정 금지.
orchestrator  : build/extract/run/verify/report/gate 실행.  expected/manifest 반영은 사람 승인 후.
memory_synth  : ledger/capability map 갱신.  expected 변경 금지.
coverage_planner: capability_map 갱신·gap 산출.  쓰기 없음(읽기·기록만).
```

## 3. 컴포넌트
**결정적 파이프라인** (먼저 안정화, P1):
```
build → extract(lowpcode+metadata) → analyze(11_ 엔진) → verify(expected) → report(v2) → gate → cache → ledger
```
**Adapter 분리** (run_tests 단일책임 금지):
```
SuiteAdapter(base): discover_cases / build(variant) / extract_lowpcode / expected_for
  ├ Suite09Adapter   : 09 일반 C/C++ build/extract/expected
  └ Suite10UEAdapter : 10 UE(USTRUCT/컨테이너) build/extract/expected
EngineAdapter: Engine11Adapter — 11_ 실행(engine commit/config 기록)
Verifier    : engine_result × expected → VerifyResult(verdict/missing/forbidden_found/...)
```
완료 기준: 09만/10만/09+10 동시 실행 가능, 11 engine commit·config가 report에 기록.

**에이전트(LLM 판단 노드, 7종)** — §10.

## 4. 목적함수 & 불변식 (P4/P8)
```
사전식 점수 = ( -crash, -false_positive, -regression, +pass(high-priority), +pass(other), honest_degrade )
불변식(어기면 수정 거부):
  I1 crash=0      I2 false_positive=0      I3 regression=0
  I4 oracle(expected/manifest) 미변경      I5 evidence_required(증거 없는 engine_defect/수정/오라클 변경 금지)
가장 위험한 실패 = source 못 찾음(FN)이 아니라 엉뚱한 source를 맞다고 함(FP). 그래서 I2 ≫ pass 증가.
/O2 변형은 PASS 목표가 아니라 "FP 없음 + 정직한 degrade(unresolved/widened)"로 평가.
```

## 5. 계층 Artifact Cache (R1) — 단일 평면키 금지
과잉 무효화 방지를 위해 **단계별 캐시**:
```
build_artifact   key = source_hash + toolchain + build_variant
pcode_metadata   key = binary_hash + ghidra_version + extractor_hash + metadata_schema_version
engine_result    key = pcode_hash + metadata_hash + engine_commit + run_config_hash
verify_result    key = engine_result_hash + expected_hash + verifier_version
```
무효화 전파:
```
source 변경     → build부터 재실행
extractor 변경  → pcode/metadata부터
engine commit   → engine_result부터
expected 변경   → verify만
```
**P4(결정성)**: 비교·해시 전 결과를 **canonical JSON(키 정렬·node/edge 정렬)** 로 정규화.
`engine_result_hash`/회귀비교가 엔진 출력 결정성에 의존하므로, PR3 슬라이스에서 "같은 입력 2회→동일 해시"를 검증.
`run_config_hash`는 엔진 플래그(`--summary-first`, budgets 등)를 정규화해 포함.

## 6. FailureReport v2 스키마
```json
{
  "schema_version": 2, "run_id": "...", "suite": "09_tdo_testbed",
  "case": "DFB055",
  "variant": { "arch": "x64", "compiler": "msvc", "opt": "O2", "build_config": null, "pdb": false, "unreal_version": null },
  "toolchain": { "android_ndk_version": "25.1.8937393", "clang_version": "...", "target_triple": "aarch64-linux-android" },
  "engine": { "repo": "trace_data_origin_lowpcode", "commit": "...", "config_hash": "...", "mode": "summary_first" },
  "artifacts": { "binary_path","binary_hash","pcode_path","pcode_hash","metadata_path","result_path","diagnose_dump_path" },
  "verdict": "PASS|FAIL|ERROR|DEGRADED",
  "missing": [], "forbidden_found": [], "warnings": [], "features": [], "edge_kinds_seen": [], "cut": [],
  "budgets": { "budget_exceeded": false, "details": [] }
}
```
**suite별 분리 summary 필수**(하나의 pass/fail로 합치지 말 것):
```json
{ "suites": { "09_tdo_testbed": {"pass":370,"fail":118,"error":0,"false_positive":0,"regression":0},
              "10_tdo_testbed_UE": {"pass":12,"fail":3,"degraded":1,"false_positive":0} } }
```

## 7. Triage — 8 범주 + unknown 폴백 (R4/P2)
```
engine_defect · harness_defect · extractor_defect · testcase_defect ·
oracle_defect · environment_defect · known_frontier · unsupported
+ unknown → needs_human (8개 중 억지 선택 금지)
```
규칙(I5): **모든 비-frontier 범주는 evidence 필수.** 재현 증거 없으면 engine_defect로 단정 금지,
diagnostician envelope의 evidence가 비면 reject. (근거: 과거 'crash'는 엔진 아닌 하니스 도구 버그였음.)

## 8. Capability Map / coverage_planner (R 보강)
status: `can · cannot · frontier · missing · weakly_covered · contradictory`
```
coverage_planner: failure_report+expected metadata 읽어 capability별 상태 갱신, gap을 case_author에 전달.
frontier  : 알려진 미구현 — 신규 regression으로 세지 않음(gate). 단 frontier가 FP 내면 즉시 hard fail.
contradictory: expected/케이스 충돌 — 자동수정 금지, 즉시 human escalation.
weakly_covered: 단일 케이스뿐, fusion/variant 부족 → 케이스 보강 대상.
```

## 9. 외부 메모리 5원장 (P6)
```
failure_ledger   : case×commit×variant → verdict/missing/forbidden_found/cut/root_cause_ref
hypothesis_ledger: id → claim/evidence_ref/status(proposed|refuted|confirmed|fixed)   # 신뢰의 원장
decision_log     : engine_change → why/cites/evidence/adversary_votes/objective_delta
artifact_cache   : §5 4단 키 → 산출물 경로 (+toolchain 핀 기록)
capability_map   : case_class → status(§8) + blocking_hypothesis
```
각 에이전트는 필요한 슬라이스만 조회. 원장은 추가/상태전이 위주(감사 추적), 사실 삭제 금지.

## 10. 에이전트 7종 + JSON 계약 (R 보강)
역할: `triage · diagnostician · adversary · engine_fixer · case_author · memory_synth · coverage_planner`.
- role string ↔ `agents/<role>.md` 파일명 **정확 일치**, 없는 role 호출 시 즉시 에러.
- 모든 출력은 **기계검증 JSON envelope**. schema 불일치 시 결과 미적용.
- 예) diagnostician: `{agent, schema_version, case_refs, hypotheses[{id,claim,evidence[],confidence,risk}], recommended_next_action}`.
  evidence 비면 reject(I5).
- adversary: 서로 다른 렌즈(correctness/regression/fp_risk) 독립 다수결, **증거 없는 confirm 무효**.
- engine_fixer: proposal-only(§2). 출력=branch/files_changed/summary/selftest(collect_failures 재실행)/risk_note. merge는 사람.

## 11. case_author 오라클 검증 (R6/P3)
```
출력은 proposed_cases/ + approval queue로만. expected/manifest 직접수정 금지.
필수 필드: expected_by_construction, oracle_rationale, forbidden_rationale, independent_validation{status,method,artifact}
endpoint 검증(어느 source가 sink 도달) = magic-value 실행으로 **stage-1부터 attached 필수**(P3: 가장 위험·저비용).
깊은 경로(flow)·DFSan 등은 staged. independent_validation.status != attached(endpoint) → expected merge 금지.
정답은 소스 의도에서 by-construction 작성, 엔진 출력에서 긁기 금지(순환). offset: cpp=offsetof, UE=pdb/heap 센티넬.
```

## 12. Gates (전체, 결정적)
```
no_crash(I1) · no_false_positive(I2) · no_regression(I3) · oracle_locked(I4) · evidence_required(I5)
artifact_integrity · expected_hash_match · engine_config_recorded
known_frontier_not_counted_as_new_regression   (단 frontier가 FP→hard fail)
```

## 13. 휴먼 게이트 / 자율 범위 / 종료 (P7)
```
사람 승인 필요: expected/manifest 변경 · 11_ 엔진 merge · "frontier/unsupported" 판정 · contradictory 해소
완전 자율    : 테스트 실행 · 증거기반 진단 · 패치 제안(merge 전) · 케이스 초안(proposed_cases)
종료: false_positive=0 AND high-priority PASS 목표 도달 AND frontier 문서화
에스컬레이션: 같은 케이스 N회 수정 실패 / 회귀 게이트 반복 실패 / 오라클·contradictory → 사람
```

## 14. Multi-Repo Config (R5)
`harness/config.yaml`(+`.example`). 경로·툴체인 명시, cwd 비의존, 잘못된 path는 초기 에러.
```yaml
repos: { testbed_09, testbed_10_ue, engine_11 }
tools:
  ghidra: { home, version }
  android_ndk: { path, version, clang }     # 자동선택 금지 — 핀 필수(P5)
  unreal_engine_root, python, cmake
output: { root, artifact_cache, ledgers }
defaults: { changed_only: true, summary_first: true, no_full_graph_export: true, export_query_subgraph_only: true }
```
선택된 toolchain은 모든 run artifact/FailureReport에 기록(§6 toolchain 필드).

## 15. 기존 자산 매핑 (새로 만들지 말 것)
```
Test Runner   ← build.sh · cpp_like/scripts/extract_lowpcode.sh · tools/collect_failures.py · tools/run_v2_engine.py
Diagnostician ← tools/diagnose_case.py (경로·메모리키 증거)
오라클 검사   ← tools/verify_flows.py + gates.oracle_locked(git diff)
```

## 16. PR 계획 (수직 슬라이스 우선, R3/P1)
```
PR1 문서 정리      : 본 v2 설계 확정(번호체계·role·R1~R6·P1~P4), FailureReport v2/캐시/config 스키마 인라인
PR2 config         : harness/config.py + config.yaml.example + path validation + toolchain 핀(NDK 포함)  (완료: python -m harness.config --check)
PR3 09 수직 슬라이스: build→extract→engine→verify→report 최소. **known-PASS 케이스(예 DFB001)** 로 — 실패 시 하니스 결함으로 격리(P1). 엔진 출력 결정성(2회→동일 해시) 검증(P4)
PR4 FailureReport v2: suite/variant/artifact/engine commit/hash 정식 + suite별 summary
PR5 계층 캐시      : build/pcode/engine/verify 4단 + canonical 정규화 (완료: 재실행 skip, engine commit/extractor/expected 변경별 정확 무효화)
PR6 Adapter        : Suite09/Suite10UE/Engine11 + dry-run (--suite 09/10/09,10 --dry-run)
PR7 gates 강화     : harness_defect triage(8범주+unknown) + evidence_required + known_frontier_not_counted
PR8 capability/coverage_planner: missing/weakly/frontier/contradictory 관리
PR9 agent JSON 계약: schema validation + role 정규화 + proposed_cases approval queue (완료: invalid output 무시, case_author가 expected 직접수정 불가)
```

## 17. 최종 목표
```bash
python -m harness.orchestrator --config harness/config.yaml --suite 09,10 --engine 11 --changed-only --budget standard
# → 변경감지 → 필요 case만 build → 캐시 hit/miss → 추출 → 11 실행 → verify → report v2
#   → gates → triage → diagnostics → adversary → (패치 제안|frontier 기록) → case gap이면 proposed_cases → capability/ledger 갱신
```

## 18. 반드시 피할 것 (anti-patterns)
```
- expected 자동수정으로 PASS 늘리기            - 09/10/11 경계 무시하고 한 repo처럼 수정
- LLM agent부터 연결                           - run_tests 하나에 모든 책임
- report에 artifact hash/engine commit 누락    - known frontier와 regression 섞기
- false positive를 allowed warning으로 처리    - NDK 등 toolchain 자동선택(핀 안 함)
- PDB/type metadata를 core truth로 쓰는 테스트 설계   - 증거 없이 engine_defect 단정
```
