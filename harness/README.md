# Harness

09/10/12 자동 반복 루프의 결정적 실행 하니스. 단일 진실 사양은
[`docs/harness_design.md`](../docs/harness_design.md)이다.

현재 구현 범위는 deterministic vertical slice + optional LLM provider hook이다. Config -> suite
adapter -> Engine11 실행 -> expected 검증 -> FailureReport v2 -> suite summary -> gate
-> JSON 원장 -> 동일 입력 캐시 재사용까지 실제로 동작한다. Suite10 Tier0는 local
build/extract prepare step으로 NDK/Ghidra 산출물을 만들고 곧바로 Engine11 분석까지
연결할 수 있다. UE 5.8 Mac local build 산출물도 prepare step에서 Ghidra
low-pcode 추출까지 자동 연결할 수 있다. 큰 UE 디렉터리는 case-scoped low-pcode
closure로 분석해 P0(DebugGame)도 전체 22개 case 회귀가 가능하다. Suite12 Obf는
소스 레벨 난독화와 Docker OLLVM profile의 low-pcode를 같은 Engine11 회귀 루프에
연결한다. LLM 호출은
provider command가 설정된 경우에만 실행되며, 결과는 proposal/work item으로만 남긴다.

파일별 책임과 `harness/config.yaml` 작성법은
[`docs/harness_file_guide.md`](../docs/harness_file_guide.md)에 정리되어 있다.

## 에이전트 7종
`triage · diagnostician · adversary · engine_fixer · case_author · memory_synth · coverage_planner`

## 구성
```text
harness/
  orchestrator.py     결정적 CLI runner. 09/10/12 suite adapter를 통해 Engine11 실행.
  adapters.py         Suite09/Suite10UE/Suite12Obf variant discovery + local prepare step.
  config.py           config.yaml(.example) 로드 + 로컬 기본값.
  reporting.py        artifact hash, FailureReport v2 summary writer.
  gates.py            목적함수·불변식·오라클잠금.
  case_scope.py       큰 low-pcode 디렉터리의 case별 dependency closure materializer.
  agent_tasks.py      human gate 기반 판단 노드 task artifact 생성.
  agent_runtime.py    외부 JSON-in/JSON-out agent executor hook + role/evidence 검증.
  design_lint.py      Engine11 diff가 설계 철학을 깨는 하드코딩인지 검사.
  human_approval.py   human approval queue 조회/결정 append-only CLI.
  baseline.py         I3 regression baseline pin 관리 CLI.
  proposals.py        accepted agent output을 proposed artifact로 materialize.
  work_items.py       proposal work item doctor + guarded engine/case promotion.
  frontier_case_loop.py
                      case_author 제안 -> doctor -> 적용계획 -> 선택적 Engine11 수리 루프.
  memory/
    schema.json       외부 원장 스키마.
    store.py          JSON/JSONL 원장 구현.
  agents/             판단 노드 계약서.
```

## 사용 방법
기본값은 `docs/local_regression_environment.md`의 현재 로컬 경로를 따른다.
필요하면 `harness/config.yaml.example`을 `harness/config.yaml`로 복사해
경로를 고정한다.

전제 조건:

```text
1. lowpcode_data_origin, tdo_testbed, tdo_testbed_UE, tdo_testbed_Obf가 같은 01_tdo 루트 아래에 있다.
2. lowpcode_data_origin/.venv에 Engine11 의존성(networkx 등)이 설치되어 있다.
3. release-artifacts 모드는 dist/release_0.3.0 low-pcode/expected가 준비되어 있다.
4. local-samples prepare 모드는 Android NDK, Ghidra, Ghidra Java가 설정되어 있다.
5. UE local build/extract는 `/Users/Shared/Epic Games/UE_5.8` + Xcode 26에서 검증되어 있다.
```

빠른 확인:

```bash
python -m harness.orchestrator --suite 09,10 --list-variants
python -m harness.orchestrator --suite 10 --mode local-samples --list-variants
python -m harness.orchestrator --suite 12 --mode local-samples --list-variants
```

기존 추출물로 회귀 실행:

```bash
python -m harness.orchestrator --suite 09 --case-filter case_DFB001
python -m harness.orchestrator --suite 10 --mode release-artifacts
python -m harness.orchestrator --suite 12 --mode local-samples
python -m harness.orchestrator --suite 09 --case-filter case_DFB001 --no-cache
```

Suite12 Obf 로컬 build/extract/analyze:

```bash
python -m harness.orchestrator --suite 12 --mode local-samples --prepare-artifacts --profile P0 --variant-filter obf-P0
python -m harness.orchestrator --suite 12 --mode local-samples --prepare-artifacts --profile P1 --variant-filter obf-P1
python -m harness.orchestrator --suite 12 --mode local-samples --prepare-artifacts --profile P2 --variant-filter obf-P2
```

Suite12 OLLVM Docker build/extract/analyze:

```bash
cd ../tdo_testbed_Obf
scripts/setup_ollvm_docker.sh
cd ../tdo_testbed_UE
python -m harness.orchestrator --suite 12 --mode local-samples --prepare-artifacts --profile OLLVM_ALL --variant-filter obf-OLLVM_ALL
```

`OLLVM_FLA_SPLIT`, `OLLVM_FLA_SUB_SPLIT`, `OLLVM_ALL`은 현재 `fla + split`
조합을 압박하는 frontier profile이다. 안정 회귀만 보고 싶으면
`--variant-filter`로 통과 profile을 좁혀 실행한다.

기본 OLLVM profile은 AArch64 Docker image를 사용한다. OLLVM 난독화를 다른
아키텍처에도 걸려면 suffix profile을 사용한다.

```bash
cd ../tdo_testbed_Obf
OBF_OLLVM_ARCH=x64 scripts/setup_ollvm_docker.sh
cd ../tdo_testbed_UE
python -m harness.orchestrator \
  --suite 12 \
  --mode local-samples \
  --prepare-artifacts \
  --force-prepare \
  --profile OLLVM_ALL_x64 \
  --variant-filter obf-OLLVM_ALL_x64
```

지원 suffix는 `_aarch64`, `_x64`, `_x86`, `_armv7`이다. 이미지가 없으면
`setup_ollvm_docker.sh`를 arch별로 먼저 실행해야 한다. 각 suffix는 별도
`samples/low_pcode/<profile>_<arch>` 디렉터리를 사용하므로 기존 AArch64
샘플과 섞이지 않는다.

Suite12 OLLVM 반복 rebuild/extract/analyze 루프:

```bash
python -m harness.obf_rebuild_loop \
  --config harness/config.yaml.example \
  --run-id obf_ollvm_all_loop \
  --profiles OLLVM_ALL \
  --max-cycles 3 \
  --clean-output
```

처음 실행해서 `tdo-testbed-obf-ollvm:llvm4` 이미지가 아직 없으면
`--setup-docker-image`를 한 번 붙인다. suffix profile을 같이 주면 필요한
arch-specific image도 같이 준비한다. 이 단계는 obfuscator-llvm/LLVM을 Docker
이미지 안에서 빌드하므로 오래 걸릴 수 있다.

```bash
python -m harness.obf_rebuild_loop \
  --config harness/config.yaml.example \
  --run-id obf_ollvm_setup_and_smoke \
  --profiles OLLVM_ALL,OLLVM_ALL_x64 \
  --max-cycles 1 \
  --setup-docker-image \
  --clean-output
```

정말 계속 돌리고 싶을 때는 `--max-cycles 0`을 사용한다. 이 경우 실패하거나
터미널에서 중지할 때까지 반복한다. 각 cycle은 `--force-prepare`와 `--no-cache`
의미로 실행되므로 OLLVM Docker 빌드, Ghidra low-pcode 재추출, Engine11 회귀가
매번 새로 돈다. 진행 상태는
`output/harness/<run-id>/obf_rebuild_loop_state.json`에 남는다.

```bash
python -m harness.obf_rebuild_loop \
  --config harness/config.yaml.example \
  --run-id obf_ollvm_unlimited \
  --profiles OLLVM_FLA_SPLIT,OLLVM_FLA_SUB_SPLIT,OLLVM_ALL,OLLVM_ALL_x64 \
  --max-cycles 0 \
  --duration-hours 4.5 \
  --clean-output
```

이 루프는 **새 케이스를 만들지 않는다**. 기존 Suite12 케이스를 매 cycle마다 다시
빌드/추출/검증하는 압박 루프다.

Suite12에서 신규 OBF 케이스 생성까지 닫힌 루프로 연결하려면
`harness.frontier_case_loop`를 `--suite 12`로 실행한다. 이 경로는
`case_author` proposal을 만들고, `suite12-obf` target으로 `src/cases_basic_obf.c`와
`manifests/cases_obf_manifest.json`에 적용할 수 있으며, 적용 후
`generate_registry_from_manifest.py`와 `generate_expected_from_manifest.py`를 호출한다.

먼저 source/manifest를 바꾸지 않는 배선 smoke:

```bash
python -m harness.frontier_case_loop \
  --config harness/config.yaml.example \
  --suite 12 \
  --mode local-samples \
  --run-id suite12_offline_case_author_dryrun \
  --clean-output \
  --include-proposed-regression \
  --offline-case-author \
  --apply-mode dry-run
```

Codex case_author가 신규 OBF 케이스를 만들고, 승인 적용 후 OLLVM 빌드/추출/회귀와
Engine11 수리까지 이어가는 형태:

```bash
python -m harness.frontier_case_loop \
  --config harness/config.yaml.example \
  --suite 12 \
  --mode local-samples \
  --run-id suite12_obf_case_engine_closed \
  --clean-output \
  --include-proposed-regression \
  --author-calls 8 \
  --author-chunk-calls 4 \
  --author-chunk-tokens 100000 \
  --author-reasoning-effort high \
  --gap-note-file /tmp/tdo_operator_note.md \
  --apply-mode approved \
  --allow-unapproved-case-apply \
  --prepare-after-apply \
  --prepare-profiles OLLVM_FLA_SPLIT,OLLVM_FLA_SUB_SPLIT,OLLVM_ALL \
  --post-apply-regression \
  --run-engine-dev-loop \
  --engine-duration-hours 3.0 \
  --engine-max-cycles 6 \
  --engine-analysis-calls 12 \
  --editor-reasoning-effort high \
  --repair-reasoning-effort xhigh
```

위 닫힌 루프를 여러 cycle 반복하고, 각 cycle에서 생성/적용된 케이스를 ledger로
남기려면 `frontier_auto_loop`로 감싼다. `--` 뒤 옵션은 그대로
`frontier_case_loop`에 전달된다.

```bash
python -m harness.frontier_auto_loop \
  --config harness/config.yaml.example \
  --run-id suite12_obf_auto_loop \
  --clean-output \
  --max-cycles 0 \
  --duration-hours 4.5 \
  --stop-after-green-cycles 3 \
  --green-streak-mode post-apply \
  --setup-suite12-docker-image \
  -- \
  --suite 12 \
  --mode local-samples \
  --include-proposed-regression \
  --author-calls 8 \
  --author-chunk-calls 4 \
  --author-chunk-tokens 100000 \
  --author-reasoning-effort high \
  --gap-note-file /tmp/tdo_operator_note.md \
  --apply-mode approved \
  --allow-unapproved-case-apply \
  --prepare-after-apply \
  --prepare-profiles OLLVM_FLA_SPLIT,OLLVM_FLA_SUB_SPLIT,OLLVM_ALL \
  --post-apply-regression \
  --run-engine-dev-loop \
  --engine-duration-hours 3.0 \
  --engine-max-cycles 6 \
  --engine-analysis-calls 12 \
  --editor-reasoning-effort high \
  --repair-reasoning-effort xhigh
```

Tier0 C/C++ 로컬 build/extract:

```bash
python -m harness.orchestrator --suite 10 --mode local-samples --prepare-only --profile P0 --arch x64
```

Tier0 C/C++ 로컬 build/extract/analyze 원커맨드:

```bash
python -m harness.orchestrator --suite 10 --mode local-samples --prepare-artifacts --profile P0 --arch x64 --variant-filter tv2-tier0-P0-x64
```

UE 5.8 local build까지 실행:

```bash
python -m harness.orchestrator --suite 10 --mode local-samples --prepare-only --profile P0 --arch x64 --include-ue-build
python -m harness.orchestrator --suite 10 --mode local-samples --prepare-only --profile P1 --arch x64 --include-ue-build
```

UE 5.8 local build/extract/analyze 원커맨드:

```bash
python -m harness.orchestrator --suite 10 --mode local-samples --prepare-artifacts --skip-tier0-prepare --profile P1 --include-ue-build --include-ue-extract --variant-filter ue-local-development
python -m harness.orchestrator --suite 10 --mode local-samples --prepare-artifacts --skip-tier0-prepare --profile P0 --include-ue-build --include-ue-extract --variant-filter ue-local-debuggame
```

P1(Development)와 P0(DebugGame) 모두 현재 build/extract/analyze smoke로 검증되어
있다. P0는 full directory compose 대신 case-scoped closure를 사용한다.

주요 옵션:

```text
--suite 09|10|12|09,10    실행할 테스트베드 선택
--mode release-artifacts  release에 포함된 Win64 UE low-pcode 사용
--mode local-samples      로컬 samples/low_pcode 경로 사용
--prepare-artifacts       분석 전 build/extract 준비 단계 실행
--prepare-only            build/extract 준비만 하고 분석은 생략
--prepare-dry-run         준비 명령을 기록만 하고 실행하지 않음
--force-prepare           changed-only prepare cache를 무시하고 준비 명령 실행
--profile P0|P1|P2|OLLVM_* 빌드/추출 프로파일
--arch x64|x86|armv7|aarch64|all
--skip-tier0-prepare      UE만 준비할 때 Tier0 build/extract 생략
--include-ue-build        UE 5.8 Mac build step 포함
--include-ue-extract      UE 5.8 Mac build output low-pcode extraction 포함
--case-scope auto|always|never
                           큰 low-pcode directory를 case별 closure로 materialize
--variant-filter TEXT     variant label substring으로 실행 대상 제한
--case-filter TEXT        case JSON filename substring으로 실행 대상 제한
--include-proposed-regression
                           case_author proposed-regression 케이스까지 실행
--regression-baseline ID|PATH
                           이전 run id/output dir/failure_report_v2.json 기준 I3 비교
--no-cache                engine/verify 캐시 재사용 끄기
--no-ledger               memory ledger 갱신 끄기
--jobs N                  variant 단위 병렬 프로세스 실행
--slow-case-limit N       performance_report.json에 남길 느린 케이스 수
--slice-profile-opcodes   SliceGraphBuilder opcode별 timing/profile 수집
```

산출물:

```text
output/harness/<run_id>/failure_report_v2.json
output/harness/<run_id>/summary.json
output/harness/<run_id>/performance_report.json
output/harness/<run_id>/gate.json
output/harness/<run_id>/human_gate.json
output/harness/<run_id>/agent_tasks.json
output/harness/<run_id>/prepare_report.json
output/harness/<run_id>/prepare/*.log
output/harness/memory/failure_ledger.jsonl
output/harness/memory/artifact_cache.json
output/harness/memory/baseline_map.json
output/harness/memory/capability_map.json
output/harness/memory/human_approval_queue.jsonl
output/harness/memory/human_decisions.jsonl
output/harness/memory/baseline_pins.json
```

Human approval queue:

```bash
python -m harness.human_approval list --run-id p0_case_scope_agent_tasks
python -m harness.human_approval show 38487fd26e35d1c9
python -m harness.human_approval decide 38487fd26e35d1c9 --decision defer --reason "need engine diagnosis"
python -m harness.human_approval decide 789a6902be877df4 --decision approve --capability-status frontier --reason "confirmed current frontier"
```

Regression baseline pins:

```bash
python -m harness.baseline pin dfb001-good --run-id dfb001_after_harness_finish --description DFB001-all-arch-known-good
python -m harness.baseline list
python -m harness.orchestrator --suite 09 --case-filter case_DFB001 --regression-baseline dfb001-good
```

Agent runtime hook:

```bash
python -m harness.agent_runtime doctor
python -m harness.agent_runtime doctor --strict --json

python -m harness.agent_runtime run \
  --tasks output/harness/p0_case_scope_agent_tasks/agent_tasks.json \
  --output-dir output/harness/agent_runtime \
  --max-calls 2 \
  --max-tokens 200000 \
  --stop-on-provider-error

python -m harness.agent_runtime run \
  --tasks output/harness/p0_case_scope_agent_tasks/agent_tasks.json \
  --output-dir output/harness/agent_runtime \
  --max-calls 10 \
  --max-tokens 100000 \
  --resume-existing \
  --stop-on-provider-error

python -m harness.proposals \
  --agent-results output/harness/agent_runtime/agent_results.json \
  --run-id proposal_run \
  --output-dir output/harness/proposal_run \
  --include-coverage \
  --scaffold-work-items

python -m harness.agent_loop \
  --config harness/config.yaml.example \
  --tasks output/harness/cycle_check_ue_p0_hot/agent_tasks.json \
  --output-dir output/harness/codex_agent_longrun \
  --duration-hours 4.5 \
  --chunk-calls 5 \
  --chunk-tokens 50000 \
  --materialize-proposals \
  --proposal-output-dir output/harness/codex_agent_longrun_proposal \
  --include-coverage \
  --scaffold-work-items \
  --stop-on-no-progress
```

`--max-calls`, `--max-tokens`, provider error로 중간 종료되면 exit code 3이 날 수 있다.
이때도 accepted 결과는 `agent_results.json`에 저장되므로, 같은 output dir에
`--resume-existing`을 붙여 이어서 실행한다.
장시간 실행은 `agent_loop`가 이 과정을 반복한다. `duration-hours`는 Codex 5시간 만료
전에 안전 여유를 두기 위해 4.5처럼 잡는다.

Agent executor output은 role별 JSON 계약과 evidence requirement를 통과해야 accepted로
기록된다. 모델 출력은 PASS/FAIL, expected, manifest, engine merge를 직접 바꾸지 않는다.
Accepted case_author/engine_fixer/coverage_planner output도 proposal artifact로만
materialize된다. `--scaffold-work-items`는 사람이 검토할 source skeleton,
engine fix plan, coverage update plan만 만들고, source-of-truth 오라클과 엔진 main은
자동 수정하지 않는다. 실제 provider command는 로컬 `harness/config.yaml`의
`models.commands`에 넣고 `agent_runtime doctor --strict`로 점검한다.
기본 예시는 Codex CLI provider를 사용한다. Codex CLI provider는
`--reasoning-effort low|medium|high|xhigh`를 받아 `model_reasoning_effort`로 전달한다.
추천 운용은 cheap/coverage는 `medium`, diagnostician은 `high`, triage/adversary처럼
false-positive 판단에 가까운 role은 `xhigh`다. OpenAI API provider도 가능하지만 그 경우
`OPENAI_API_KEY`와 API billing이 필요하다.

Engine11 direct development loop:

```bash
python -m harness.engine_dev_loop \
  --config harness/config.yaml.example \
  --suite 09,10 \
  --mode local-samples \
  --run-id engine_dev_09_10 \
  --clean-output \
  --duration-hours 4.5 \
  --max-cycles 3 \
  --analysis-calls 10 \
  --analysis-chunk-calls 5 \
  --analysis-chunk-tokens 50000
```

`engine_dev_loop`는 분석 전용 `agent_loop`와 다르다. 매 cycle마다 09/10 회귀를
`--no-cache`로 실행하고, 실패 리포트와 선택적 agent proposal을 바탕으로 Codex CLI를
`lowpcode_data_origin` repo에서 `workspace-write` sandbox로 실행한다. 이후
`compileall`과 사후 회귀를 실행하고, 이전 PASS가 깨지거나 ERROR/false positive가
증가하면 diff와 로그를 남긴 뒤 멈춘다. expected/manifest/testbed 파일은 자동 편집
대상이 아니며, 루프 시작 시 Engine11 repo가 dirty면 기본적으로 중단한다.
회귀 병목이 크면 `--regression-jobs N`을 주어 pre/post orchestrator 회귀를
variant 단위 멀티프로세스로 실행한다. 케이스 내부 순서는 그대로 두고 variant별
프로세스만 분리하므로 Engine11 builder 상태를 공유하지 않는다.

작게 점검하려면 편집 없이:

```bash
python -m harness.engine_dev_loop \
  --config harness/config.yaml.example \
  --suite 09 \
  --mode local-samples \
  --case-filter case_DFB001 \
  --run-id engine_dev_loop_smoke_dfb001 \
  --clean-output \
  --max-cycles 1 \
  --no-edit
```

중간 산출물:

```text
output/harness/<run_id>/engine_dev_loop_state.json
output/harness/<run_id>/cycle_XX/pre_regression/
output/harness/<run_id>/cycle_XX/agent_analysis/
output/harness/<run_id>/cycle_XX/codex_engine_fix_prompt.md
output/harness/<run_id>/cycle_XX/engine.diff
output/harness/<run_id>/cycle_XX/post_regression/
```

중간에 사람이 추가 지시를 넣고 재개할 때:

```bash
cat > output/harness/engine_dev_09_10/operator_note.md <<'EOF'
Focus the next cycle on observed memory edges around TV2R001.
Do not change expected files or add ABI/parameter semantics to core graph.
EOF

python -m harness.engine_dev_loop \
  --config harness/config.yaml.example \
  --suite 09,10 \
  --mode local-samples \
  --run-id engine_dev_09_10 \
  --resume-existing \
  --duration-hours 4.5 \
  --max-cycles 4 \
  --analysis-calls 10 \
  --editor-extra-instructions-file output/harness/engine_dev_09_10/operator_note.md
```

짧은 일회성 지시는 파일 없이도 붙일 수 있다:

```bash
python -m harness.engine_dev_loop \
  --config harness/config.yaml.example \
  --run-id engine_dev_09_10 \
  --resume-existing \
  --editor-extra-instructions "Prioritize the latest post_regression false positive before adding recall."
```

Regression/FP repair mode:

```bash
python -m harness.engine_dev_loop \
  --config harness/config.yaml.example \
  --suite 09,10 \
  --mode local-samples \
  --run-id engine_dev_09_10 \
  --resume-existing \
  --duration-hours 4.5 \
  --max-cycles 5 \
  --analysis-calls 10 \
  --repair-on-regression \
  --editor-reasoning-effort high \
  --repair-reasoning-effort xhigh \
  --editor-extra-instructions-file /tmp/tdo_operator_note.md
```

기본 모드는 이전 PASS 회귀나 false positive 증가가 생기면 멈춘다.
`--repair-on-regression`은 그 정보를 다음 cycle의 `Active repair context`로 넘긴다.
다음 post-regression은 직전 cycle pre뿐 아니라 회귀가 생기기 전 baseline report와도
비교한다. 즉 aggregate PASS가 늘어도 기존 PASS를 깨거나 새 FP를 만들면 repair cycle이
계속 그 사실을 보게 된다.
`--editor-reasoning-effort`는 실제 `lowpcode_data_origin` 수정 담당 Codex CLI에만
적용된다. 개발 cycle은 보통 `high`로 시작하고, 비용/한도 소모를 줄여야 할 때만
`medium`으로 낮춘다.
`--repair-reasoning-effort`는 repair context가 있는 cycle에만 적용된다. 기본값은
`xhigh`라서 일반 개발은 `high`로 돌리다가, false positive나 regression이 생긴
수리 cycle만 더 깊게 추론하게 할 수 있다. `--no-stop-on-regression`과 함께 써도
repair가 `--stop-on-no-progress`보다 먼저 예약된다.

Engine11 design lint:

```bash
python -m harness.design_lint \
  --config harness/config.yaml.example \
  --engine-repo /Volumes/DO/00_gitProject/01_tdo/lowpcode_data_origin
```

`engine_dev_loop`는 기본적으로 편집 직후 `design_lint`를 실행한다. lint는 Engine11
code diff의 추가 라인에서 `TV2...`, `DFB...`, `case_...`, `write_expected`,
`dfb_source_A/B/C` 같은 benchmark/helper/source-label 하드코딩을 잡는다.
목표는 no arg/no ret, convention-free, wrapper/BoundaryProvider 분리 원칙을
자동 게이트로 지키는 것이다. 문서나 dev log의 사례명은 검사 대상이 아니며,
Engine11 code path의 새 추가 라인만 본다. 정말로 lint를 끄려면
`engine_dev_loop --no-design-lint`를 명시해야 한다.

Proposal work item promotion:

```bash
python -m harness.work_items doctor \
  --proposal-root output/harness/proposal_scaffold_smoke

python -m harness.work_items engine-worktree \
  --plan output/harness/proposal_run/work_items/engine_fixes/<fix>/engine_fix_plan.json \
  --dry-run

python -m harness.work_items case-bundle \
  --expected output/harness/proposal_run/work_items/source_cases/<case>.expected.proposal.json \
  --target suite10-cpp \
  --bundle-dir output/harness/case_bundles/<case>

python -m harness.work_items case-apply \
  --expected output/harness/proposal_run/work_items/source_cases/<case>.expected.proposal.json \
  --target suite10-cpp \
  --dry-run
```

`engine-worktree --create`와 `case-apply --apply`는 human approval key가 있어야 실제
작동한다. 이 명령들도 Engine11 main merge나 expected 생성을 자동 진행하지 않는다.
case apply는 source/manifest까지만 다루고, expected JSON은 승인 후 기존
`generate_expected_from_manifest.py` 경로로 생성한다.

Frontier case authoring loop:

```bash
python -m harness.frontier_case_loop \
  --config harness/config.yaml.example \
  --suite 09,10 \
  --mode local-samples \
  --run-id frontier_case_loop_09_10 \
  --clean-output \
  --include-proposed-regression \
  --author-calls 6 \
  --author-chunk-calls 3 \
  --author-chunk-tokens 100000 \
  --gap-note-file /tmp/tdo_operator_note.md \
  --apply-mode dry-run
```

이 루프는 baseline 회귀를 먼저 돌리고, 그 report/capability map을 `case_author`에
넘겨 신규 융합/frontier 케이스를 proposal로 만들고, `work_items doctor`와
`case-apply --dry-run` 계획까지 생성한다. 기본값은 source/manifest를 바꾸지 않는
dry-run이다. 사람이 승인한 뒤 실제 반영까지 맡기려면 `--apply-mode approved`와
`--approval-key <key>`를 함께 준다. 승인 없이 로컬 실험만 할 때는
`--allow-unapproved-case-apply`를 명시한다. 승인 적용 모드에서는 기본적으로 manifest
기반 expected generator까지 실행한다. 끄려면 `--no-regenerate-expected`를 준다.

외부 Codex/API를 쓰지 않고 harness 자체가 deterministic proposed case를 1개 만들고
멈추는 smoke는 다음처럼 돌린다. source/manifest는 바뀌지 않고, proposal 생성,
doctor, dry-run apply 계획까지만 검증한다. `--offline-case-count`를 늘리면 여러 개를
만들 수 있지만, 기본 운용은 사람이 검토하기 쉬운 1개씩이다.

```bash
python -m harness.frontier_case_loop \
  --config harness/config.yaml.example \
  --suite 10 \
  --mode local-samples \
  --run-id offline_case_author_dryrun \
  --clean-output \
  --include-proposed-regression \
  --offline-case-author \
  --apply-mode dry-run
```

Codex case_author를 바로 실행할 준비가 된 명령은 아래 형태다. `--codex-bin`은 생략해도
`CODEX_BIN`, Codex.app bundle 경로, PATH 순서로 자동 탐색한다. 이 경로는 외부 Codex에
failure report와 gap note를 보내므로 먼저 `dry-run`으로 proposal만 받고, 적용은 별도
검토 뒤 `approved` 모드에서 진행한다.

```bash
python -m harness.frontier_case_loop \
  --config harness/config.yaml.example \
  --suite 10 \
  --mode local-samples \
  --run-id codex_case_author_dryrun \
  --clean-output \
  --include-proposed-regression \
  --author-calls 4 \
  --author-chunk-calls 4 \
  --author-chunk-tokens 100000 \
  --gap-note-file /tmp/tdo_operator_note.md \
  --apply-mode dry-run
```

케이스를 반영한 뒤 빌드/low-pcode 재추출, targeted 회귀, Engine11 수리까지 닫힌
루프로 이어가려면 다음 옵션을 함께 붙인다. cpp-like case는 기본적으로 `tv2-tier0`
variant만 targeted 검증하고, 케이스가 이미 green이면 내부 engine loop는 자동 skip된다.

```bash
python -m harness.frontier_case_loop \
  --config harness/config.yaml.example \
  --suite 09,10 \
  --mode local-samples \
  --run-id frontier_case_loop_closed \
  --clean-output \
  --include-proposed-regression \
  --author-calls 8 \
  --author-chunk-calls 4 \
  --author-chunk-tokens 100000 \
  --gap-note-file /tmp/tdo_operator_note.md \
  --apply-mode approved \
  --allow-unapproved-case-apply \
  --prepare-after-apply \
  --prepare-profiles P0,P1 \
  --prepare-arch all \
  --post-apply-regression \
  --run-engine-dev-loop \
  --engine-duration-hours 4.5 \
  --engine-max-cycles 8 \
  --engine-analysis-calls 15
```

이미 생성된 proposal을 다시 검증하거나 case_author 호출을 건너뛰려면
`--proposal-root output/harness/<run>/case_author_proposals`를 준다. `--codex-bin`은
선택 사항이다. 생략하면 `CODEX_BIN`, `/Applications/Codex.app/Contents/Resources/codex`,
PATH의 `codex` 순서로 자동 탐색하고, 찾은 경로를 case_author provider와 내부
Engine11 editor 양쪽에 전달한다. Codex CLI가 홈 디렉터리 state DB에 쓸 수 없는
샌드박스에서는 provider가 project-local `output/harness/.codex_cli_home`을
`CODEX_HOME`으로 사용한다. proposal이 0개면 루프는 `case_author_no_proposals`로
종료되어 성공처럼 보이지 않는다.

검증된 smoke:

```text
python -m harness.orchestrator --suite 10 --mode release-artifacts --run-id ue_release_smoke
10_tdo_testbed_UE: PASS 9 / FAIL 35 / ERROR 0 / FP 0
  Development: PASS 7 / FAIL 15
  DebugGame  : PASS 2 / FAIL 20

python -m harness.orchestrator --suite 09 --case-filter case_DFB001 --run-id dfb001_smoke
09_tdo_testbed: PASS 6 / FAIL 0 / ERROR 0 / FP 0

python -m harness.orchestrator --suite 10 --case-filter TV2U008 --run-id ledger_ue_u008_smoke
10_tdo_testbed_UE: PASS 1 / FAIL 1 / ERROR 0 / FP 0

python -m harness.orchestrator --suite 09 --case-filter case_DFB001 --run-id cache_dfb001_hot
09_tdo_testbed: PASS 6 / FAIL 0 / ERROR 0 / FP 0 / CACHE 6

python -m harness.orchestrator --suite 10 --case-filter TV2U008 --run-id cache_ue_u008_hot
10_tdo_testbed_UE: PASS 1 / FAIL 1 / ERROR 0 / FP 0 / CACHE 2

python -m harness.orchestrator --suite 10 --mode local-samples --prepare-artifacts --profile P0 --arch x64 --variant-filter tv2-tier0-P0-x64 --run-id tier0_x64_prepare_and_analyze --no-cache
10_tdo_testbed_UE/tv2-tier0-P0-x64: PASS 6 / FAIL 5 / ERROR 0 / FP 0 / CACHE 0

python -m harness.orchestrator --suite 10 --mode local-samples --variant-filter tv2-tier0-P0-x64 --run-id tier0_x64_analysis_hot
10_tdo_testbed_UE/tv2-tier0-P0-x64: PASS 6 / FAIL 5 / ERROR 0 / FP 0 / CACHE 11

python -m harness.orchestrator --suite 10 --mode local-samples --prepare-only --profile P0 --arch x64 --include-ue-build --run-id ue58_harness_p0_prepare
prepare: tier0-build-P0 OK / tier0-extract-P0-x64 OK / ue-build-P0 OK

python -m harness.orchestrator --suite 10 --mode local-samples --prepare-only --profile P1 --arch x64 --include-ue-build --run-id ue58_harness_p1_prepare
prepare: tier0-build-P1 OK / tier0-extract-P1-x64 OK / ue-build-P1 OK

python -m harness.orchestrator --suite 10 --mode local-samples --prepare-artifacts --skip-tier0-prepare --profile P1 --include-ue-build --include-ue-extract --variant-filter ue-local-development --run-id ue58_dev_extract_analyze_v3 --no-cache
10_tdo_testbed_UE/ue-local-development: PASS 2 / FAIL 20 / ERROR 0 / FP 2 / CACHE 0

python -m harness.orchestrator --suite 10 --mode local-samples --variant-filter ue-local-development --run-id ue58_dev_hot_cache
10_tdo_testbed_UE/ue-local-development: PASS 2 / FAIL 20 / ERROR 0 / FP 2 / CACHE 22

python -m harness.orchestrator --suite 10 --mode local-samples --prepare-artifacts --skip-tier0-prepare --profile P0 --include-ue-build --include-ue-extract --variant-filter ue-local-debuggame --run-id ue58_debug_extract_analyze --no-cache
prepare: ue-build-P0 OK / ue-extract-P0 OK / 22 case JSON produced
analysis: interrupted at Engine11 directory-wide NetworkX compose budget

python -m harness.orchestrator --suite 10 --mode local-samples --variant-filter ue-local-debuggame --run-id p0_case_scope_auto_regression --no-cache
10_tdo_testbed_UE/ue-local-debuggame: PASS 10 / FAIL 12 / ERROR 0 / FP 2 / CACHE 0

python -m harness.orchestrator --suite 10 --mode local-samples --variant-filter ue-local-debuggame --case-scope always --run-id p0_case_scope_agent_tasks
10_tdo_testbed_UE/ue-local-debuggame: PASS 10 / FAIL 12 / ERROR 0 / FP 2 / CACHE 22
human_gate.json: 12 review items, agent_tasks.json: 26 deterministic tasks

python -m harness.orchestrator --suite 10 --mode local-samples --variant-filter ue-local-development --run-id p1_case_scope_auto_regression --no-cache
10_tdo_testbed_UE/ue-local-development: PASS 2 / FAIL 20 / ERROR 0 / FP 2 / CACHE 0

python -m harness.orchestrator --suite 10 --mode local-samples --variant-filter ue-local-development --run-id p1_case_scope_auto_hot
10_tdo_testbed_UE/ue-local-development: PASS 2 / FAIL 20 / ERROR 0 / FP 2 / CACHE 22

python -m harness.orchestrator --suite 09 --case-filter case_DFB001 --run-id dfb001_after_harness_finish
09_tdo_testbed: PASS 6 / FAIL 0 / ERROR 0 / FP 0

python -m harness.orchestrator --suite 09 --case-filter case_DFB001 --run-id dfb001_i3_baseline_smoke --regression-baseline dfb001_after_harness_finish
09_tdo_testbed: PASS 6 / FAIL 0 / ERROR 0 / FP 0 / CACHE 6 / I3_regression_zero True

python -m harness.baseline pin dfb001-good --run-id dfb001_after_harness_finish --description DFB001-all-arch-known-good
baseline pin: dfb001-good

python -m harness.orchestrator --suite 09 --case-filter case_DFB001 --run-id dfb001_i3_pin_smoke --regression-baseline dfb001-good
09_tdo_testbed: PASS 6 / FAIL 0 / ERROR 0 / FP 0 / CACHE 6 / I3_regression_zero True

python -m harness.agent_runtime run --tasks output/harness/p0_case_scope_agent_tasks/agent_tasks.json --output-dir output/harness/agent_runtime_smoke2 --executor "<json-in-json-out smoke executor>"
agent tasks: 26 result(s), accepted=26

python -m harness.agent_runtime run --tasks output/harness/p0_case_scope_agent_tasks/agent_tasks.json --output-dir output/harness/agent_runtime_budget_smoke --max-calls 30 --max-tokens 200000 --executor "<json-in-json-out smoke executor>"
agent tasks: 26 result(s), accepted=26, tiers cheap/strong, used_calls=26

python -m harness.proposals --agent-results output/harness/agent_runtime_budget_smoke/agent_results.json --run-id proposal_smoke --output-dir output/harness/proposal_smoke --include-coverage
materialized 10 proposal artifact(s)

python -m harness.proposals --agent-results output/harness/agent_runtime_budget_smoke/agent_results.json --run-id proposal_scaffold_smoke --output-dir output/harness/proposal_scaffold_smoke --include-coverage --scaffold-work-items
materialized 10 proposal artifact(s), scaffolded 10 proposal work item(s)

python -m harness.work_items doctor --proposal-root output/harness/proposal_scaffold_smoke
checked: 20 / all paths ok

python -m harness.work_items engine-worktree --plan output/harness/proposal_scaffold_case_engine_smoke/work_items/engine_fixes/fix_TV2X999-smoke/engine_fix_plan.json --dry-run --allow-unapproved
engine worktree dry-run: branch/worktree plan only

python -m harness.work_items case-bundle --expected output/harness/proposal_scaffold_case_engine_smoke/work_items/source_cases/TV2X999.expected.proposal.json --target suite10-cpp --bundle-dir output/harness/case_bundle_smoke
case bundle generated, real source/manifest not modified
```

## 결정적 vs STUB
| 완성(결정적) | STUB(배선 필요) |
|---|---|
| config + Suite09/Suite10UE adapters + Engine11 runner + FailureReport v2 + summary/gate | local provider command values/secrets configuration |
| artifact hash, engine commit, expected hash, run config hash 기록 | multi-arch/local UE variants beyond Mac arm64 |
| cache hit 기반 engine/verify result skip | approved case expected generation/apply policy |
| changed-only prepare cache | multi-arch/local UE variants beyond Mac arm64 |
| Suite10 Tier0 local build/extract prepare step | multi-arch/local UE variants beyond Mac arm64 |
| UE 5.8 local DebugGame/Development build prepare step | 결정적 core 기준 추가 STUB 없음 |
| UE 5.8 Mac build-output low-pcode extraction + local analysis | 결정적 core 기준 추가 STUB 없음 |
| UE build-output binary discovery + artifact cache identity | 결정적 core 기준 추가 STUB 없음 |
| human approval queue consume CLI | 결정적 core 기준 추가 STUB 없음 |
| agent runtime hook + output schema/evidence validation + tier/budget accounting + provider doctor | 결정적 core 기준 추가 STUB 없음 |
| named regression baseline pins | 결정적 core 기준 추가 STUB 없음 |
| proposal artifact materialization + review work item scaffolding | 결정적 core 기준 추가 STUB 없음 |
| work item doctor + guarded engine worktree/case bundle/apply dry-run | 결정적 core 기준 추가 STUB 없음 |
| P0 DebugGame case-scoped graph/budget path | 결정적 core 기준 추가 STUB 없음 |
| baseline/capability/artifact JSON 원장 갱신 | 결정적 core 기준 추가 STUB 없음 |
| human_gate.json + human_approval_queue.jsonl | 결정적 core 기준 추가 STUB 없음 |
| agent_tasks.json task artifact generation | 결정적 core 기준 추가 STUB 없음 |
| crash=0, false_positive=0, regression=0, oracle_locked gate | 결정적 core 기준 추가 STUB 없음 |

## 기존 자산에 grounding
```text
Test Runner   : build.sh, cpp_like/scripts/extract_lowpcode.sh, tools/collect_failures.py, tools/run_v2_engine.py
Diagnostician : tools/diagnose_case.py
오라클 검사   : tools/verify_flows.py + gates.oracle_locked(git diff)
```

## 핵심 불변식
```text
I1 crash(ERROR)=0  I2 false_positive=0  I3 회귀=0  I4 오라클(expected/manifest) 미변경
목적: 사전식 (-crashes, -fp, +pass_P0/DebugGame, +pass_other). PASS 단일 최대화 금지.
```

## 분석 경계
하네스는 low-pcode JSON을 준비하고 Engine11 결과를 검증할 뿐, source/sink 의미를 새로
추론하지 않는다. no arg / no ret / convention free 원칙을 유지하기 위해 function
signature, parameter, return convention, ABI 이름을 분석 truth로 승격하지 않는다. Ghidra
metadata는 입력 식별·아키텍처 grounding·주소공간/레지스터 정규화에만 사용하고, expected를
엔진 출력에서 생성하지 않는다.

## 다음 배선 순서
1. 로컬 `harness/config.yaml`에 실제 모델 provider command를 `models.commands.{cheap,strong}`로 채우고 `agent_runtime doctor --strict`를 gate에 넣는다. 기본 추천은 Codex CLI provider다.
2. accepted engine_fixer work item을 `work_items engine-worktree --create --approval-key <key>`로 별도 11_ worktree branch에 연다. main merge는 계속 human gate다.
3. accepted case_author work item은 `case-bundle`로 검토 bundle을 만들고, 승인 뒤 `case-apply --apply --approval-key <key>`로 source/manifest까지만 반영한다. expected JSON 생성은 기존 generator 경로로 따로 확인한다. `severity: proposed-regression` 케이스는 기본 회귀에서 격리되며, `--include-proposed-regression`을 준 실행에서만 frontier 개발 대상으로 돌린다.
4. Mac arm64 외 local UE variant는 별도 toolchain이 준비될 때 추가한다.
5. 반복 실행 정책을 정해 어떤 baseline pin을 release/local gate로 승격할지 문서화한다.

## 실제 harness loop 실행 직전 필요한 것
```text
1. Codex login 또는 OpenAI API key
2. harness/config.yaml의 models.commands.cheap/strong 값
3. agent provider가 stdin JSON -> stdout JSON 계약을 지키는지 확인
4. engine-worktree/case-apply를 실제 적용할 때 사용할 human approval key
5. UE 재빌드/재추출까지 돌릴 경우 Xcode 26 + UE_5.8 + Ghidra/Java/NDK 경로 유지
```
