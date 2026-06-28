# Harness File Guide

이 문서는 `tdo_testbed_UE/harness` 하네스의 파일별 책임과
`harness/config.yaml` 작성 방법을 설명한다. 하네스의 목적은 09/10 테스트베드와
11 Engine11(`lowpcode_data_origin`)을 안전하게 연결해 회귀 분석, gate, cache,
ledger, agent proposal 흐름을 자동화하는 것이다.

## 핵심 원칙

```text
1. expected/manifest는 자동 수정하지 않는다.
2. Engine11 main은 자동 merge하지 않는다.
3. LLM 결과는 source of truth가 아니라 proposal/work item이다.
4. no arg / no ret / convention free 원칙을 깨는 ABI/시그니처 추론을 truth로 쓰지 않는다.
5. false positive는 hard gate다. PASS 증가보다 FP 방지가 우선이다.
```

## 디렉터리 구조

```text
harness/
  orchestrator.py
  adapters.py
  config.py
  config.yaml.example
  reporting.py
  gates.py
  case_scope.py
  ue_artifacts.py
  agent_tasks.py
  agent_runtime.py
  providers/
    openai_agent_executor.py
    codex_cli_agent_executor.py
  proposals.py
  work_items.py
  human_approval.py
  baseline.py
  memory/
    store.py
    schema.json
  agents/
    *.md
```

## 파일별 설명

### `harness/orchestrator.py`

하네스의 메인 실행기다.

역할:
- suite 09/10 variant discovery
- build/extract prepare step 실행
- Engine11 분석 실행
- expected 검증
- `failure_report_v2.json`, `summary.json`, `gate.json` 생성
- artifact cache / ledger 갱신
- human gate / agent task 생성

주로 사용하는 명령:

```bash
python3 -m harness.orchestrator --suite 09 --case-filter case_DFB001
python3 -m harness.orchestrator --suite 10 --mode local-samples --variant-filter ue-local-debuggame
python3 -m harness.orchestrator --suite 10 --mode local-samples --prepare-artifacts --include-ue-build --include-ue-extract
```

### `harness/adapters.py`

테스트베드별 차이를 숨기는 adapter 계층이다.

역할:
- Suite09: `tdo_testbed` low-pcode sample과 expected 연결
- Suite10UE: Tier0 C/C++ sample, UE release artifact, UE local sample 연결
- prepare step 목록 생성
- 각 variant의 arch/compiler/opt/build config 기록

### `harness/ue_artifacts.py`

UE 5.8 local build 산출물을 찾는 작은 discovery 계층이다.

역할:
- P0(DebugGame), P1(Development) 프로파일별 dylib/DLL 후보 경로 선택
- sample output directory 결정
- binary path/hash를 artifact identity로 연결

주의:
- 이 파일은 UE 함수 의미를 추론하지 않는다.
- binary path는 cache identity와 추출 입력일 뿐이다.

### `harness/config.py`

`harness/config.yaml`을 읽고 기본값을 제공한다.

역할:
- repo path, tool path, output path, model command, budget 로드
- `harness/config.yaml`이 없으면 local default 사용
- 간단한 YAML fallback parser 제공

### `harness/config.yaml.example`

로컬 설정 템플릿이다. 실제 실행 설정은 이 파일을 복사해서 만든다.

```bash
cp harness/config.yaml.example harness/config.yaml
```

`harness/config.yaml`은 git에 넣지 않는 것을 권장한다. API key 같은 secret은 파일에 쓰지 말고
환경변수로 둔다.

### `harness/reporting.py`

결과와 hash를 안정적으로 기록한다.

역할:
- canonical JSON hash
- artifact hash
- summary/gate/report JSON 저장
- 변동 비교가 가능하도록 정렬된 JSON 기록

### `harness/gates.py`

실패 판정과 목적함수를 담당한다.

중요 gate:
- `I1_crash_zero`
- `I2_false_positive_zero`
- `I3_regression_zero`
- `I4_oracle_locked`

이 gate 때문에 UE P0/P1은 현재 `ERROR 0`이어도 FP 2가 있으면 exit code 1을 낸다.
이건 하네스 실패가 아니라 의도된 hard gate다.

### `harness/case_scope.py`

큰 low-pcode directory를 케이스별 dependency closure로 줄인다.

왜 필요한가:
- UE DebugGame low-pcode 전체 directory를 한 번에 graph compose하면 너무 무겁다.
- root case와 필요한 helper JSON만 scope로 materialize해서 분석한다.

### `harness/agent_tasks.py`

human gate와 failure report를 agent task JSON으로 바꾼다.

역할:
- triage / diagnostician / adversary / coverage_planner task 생성
- role prompt 파일 존재 확인
- evidence-required envelope 생성

### `harness/agent_runtime.py`

외부 LLM executor를 실행하고 결과를 검증한다.

역할:
- task JSON을 stdin으로 provider command에 전달
- provider stdout JSON을 role별 schema로 검증
- cheap/strong tier routing
- per-run call/token budget accounting
- `doctor`로 provider command 설정 확인

주요 명령:

```bash
python3 -m harness.agent_runtime doctor
python3 -m harness.agent_runtime doctor --strict
python3 -m harness.agent_runtime run --tasks output/harness/<run_id>/agent_tasks.json --output-dir output/harness/agent_run
```

### `harness/providers/openai_agent_executor.py`

OpenAI Responses API용 JSON-in/JSON-out provider wrapper다.

역할:
- stdin의 agent task JSON 읽기
- `OPENAI_API_KEY` 환경변수로 OpenAI API 호출
- role prompt와 task를 model input으로 전달
- model output을 JSON으로 파싱해서 stdout에 출력

주의:
- stdout에는 JSON만 출력한다.
- API key는 절대 config 파일에 쓰지 않는다.
- ChatGPT 웹 구독과 API platform billing은 별도다. OpenAI Help 문서도 두 billing이 분리되어 있다고 설명한다.

공식 참고:
- API key / quickstart: https://developers.openai.com/api/docs/quickstart
- Responses API: https://developers.openai.com/api/reference/resources/responses/methods/create
- Models: https://developers.openai.com/api/docs/models
- ChatGPT vs API billing: https://help.openai.com/en/articles/9039756-billing-settings-in-chatgpt-vs-platform

### `harness/providers/codex_cli_agent_executor.py`

Codex CLI용 JSON-in/JSON-out provider wrapper다.

역할:
- stdin의 agent task JSON 읽기
- `codex exec`를 read-only sandbox / approval-never / ephemeral 모드로 호출
- Codex final response를 JSON으로 파싱해서 stdout에 출력

왜 필요한가:
- OpenAI API billing을 열기 전, Codex/ChatGPT 계정 로그인 기반으로 agent loop를 시험할 수 있다.
- 하네스는 여전히 파일을 직접 수정하지 않고 proposal/work item만 만든다.
- Codex 한도 초과로 중간에 멈춰도 `agent_runtime --resume-existing`으로 accepted task를 건너뛰고 이어갈 수 있다.

주의:
- Codex CLI 사용량/한도는 계정/플랜 정책을 따른다.
- 무제한 무료 대체가 아니라 API key 없는 provider 대안으로 보는 것이 안전하다.
- 실제 실행 전에는 `--max-calls 1` 또는 `--max-calls 2`로 작은 smoke부터 한다.

### `harness/proposals.py`

accepted agent output을 proposal artifact로 materialize한다.

역할:
- `case_author` output -> proposed case JSON
- `engine_fixer` output -> engine fix proposal JSON
- `coverage_planner` output -> coverage update proposal JSON
- `--scaffold-work-items` 사용 시 review work item 생성

이 단계도 expected/manifest/engine main을 바꾸지 않는다.

### `harness/work_items.py`

proposal work item을 실제 작업 후보로 승격하는 CLI다.

역할:
- `doctor`: proposal/work item 경로 검증
- `engine-worktree`: approved engine fix를 Engine11 별도 worktree 후보로 생성
- `case-bundle`: proposed case 검토 bundle 생성
- `case-apply`: human approval key가 있을 때만 source/manifest 반영

주의:
- `engine-worktree --create`는 approval key 없으면 차단된다.
- `case-apply --apply`는 approval key 없으면 차단된다.
- expected JSON 생성은 기존 generator 경로에서 별도 확인한다.

### `harness/human_approval.py`

human approval queue를 조회하고 결정을 append-only로 기록한다.

역할:
- pending gate item 조회
- approve/reject/defer 기록
- capability status를 사람이 확정했을 때 capability map에 반영

### `harness/baseline.py`

regression baseline pin 관리 CLI다.

역할:
- known-good run을 이름으로 pin
- `--regression-baseline dfb001-good`처럼 재사용

### `harness/memory/store.py`

외부 구조화 memory/ledger 저장소다.

역할:
- artifact cache
- failure ledger
- baseline map
- capability map
- human approval queue
- human decisions

### `harness/memory/schema.json`

memory/ledger의 의도와 필드 설명이다. 런타임 검증 schema라기보다 운용 계약 문서에 가깝다.

### `harness/agents/*.md`

각 agent role의 입출력 계약서다.

파일:
- `triage.md`
- `diagnostician.md`
- `adversary.md`
- `engine_fixer.md`
- `case_author.md`
- `memory_synth.md`
- `coverage_planner.md`

LLM provider는 이 파일을 developer prompt 일부로 받아 role별 JSON을 출력해야 한다.

## `config.yaml` 작성법

기본 절차:

```bash
cd /Volumes/DO/00_gitProject/01_tdo/tdo_testbed_UE
cp harness/config.yaml.example harness/config.yaml
```

### repos

세 repo 경로를 지정한다.

```yaml
repos:
  testbed_09: "/Volumes/DO/00_gitProject/01_tdo/tdo_testbed"
  testbed_10_ue: "/Volumes/DO/00_gitProject/01_tdo/tdo_testbed_UE"
  engine_11: "/Volumes/DO/00_gitProject/01_tdo/lowpcode_data_origin"
```

### tools

로컬 toolchain 경로다.

```yaml
tools:
  python: "/Volumes/DO/00_gitProject/01_tdo/lowpcode_data_origin/.venv/bin/python"
  ghidra_home: "/opt/homebrew/Cellar/ghidra/12.0.4/libexec"
  ghidra_java_home: "/Applications/Android Studio.app/Contents/jbr/Contents/Home"
  android_ndk: "/Users/test2000/Library/Android/sdk/ndk/30.0.14904198"
  unreal_engine_root: "/Users/Shared/Epic Games/UE_5.8"
  release_artifacts: "/Volumes/DO/00_gitProject/01_tdo/tdo_testbed_UE/dist/release_0.3.0"
```

### output

하네스 산출물과 memory 위치다.

```yaml
output:
  root: "/Volumes/DO/00_gitProject/01_tdo/tdo_testbed_UE/output/harness"
  memory: "/Volumes/DO/00_gitProject/01_tdo/tdo_testbed_UE/output/harness/memory"
```

### models

LLM agent loop용 설정이다. deterministic 회귀 분석만 할 때는 없어도 된다.

```yaml
models:
  cheap: "codex:gpt-5.4-mini"
  strong: "codex:gpt-5.5"
  adversary_panel: []
  commands:
    cheap: "python3 -m harness.providers.codex_cli_agent_executor --model gpt-5.4-mini"
    strong: "python3 -m harness.providers.codex_cli_agent_executor --model gpt-5.5"
  agent_tiers:
    triage: "cheap"
    coverage_planner: "cheap"
    memory_synth: "cheap"
    diagnostician: "strong"
    adversary: "strong"
    engine_fixer: "strong"
    case_author: "strong"
```

모델명은 예시다. Codex CLI가 해당 모델을 사용할 수 있어야 한다.

OpenAI API를 직접 쓰고 싶으면 commands를 아래처럼 바꾼다.

```yaml
models:
  cheap: "gpt-5.4-mini"
  strong: "gpt-5.5"
  commands:
    cheap: "python3 -m harness.providers.openai_agent_executor --model gpt-5.4-mini"
    strong: "python3 -m harness.providers.openai_agent_executor --model gpt-5.5"
```

이 경우 ChatGPT Plus/Pro 결제와 API platform billing은 별도이므로, API key와 API billing이 준비되어야 한다.

API key는 환경변수로 설정한다.

```bash
export OPENAI_API_KEY="..."
```

OpenAI quickstart는 API key를 만든 뒤 `OPENAI_API_KEY` 환경변수로 export하는 방식을 안내한다.

### budgets

LLM agent loop 비용/호출 제한이다.

```yaml
budgets:
  per_run_max_calls: 30
  per_run_max_tokens: 200000
```

처음에는 낮게 잡는 것이 좋다.

### defaults

하네스 기본 동작이다.

```yaml
defaults:
  mode: "release-artifacts"
  summary_first: true
  changed_only_prepare: true
  case_scope: "auto"
  case_scope_file_threshold: 32
  case_scope_byte_threshold: 134217728
```

## Codex CLI provider 연결 확인

1. Codex 로그인 확인

```bash
codex login status
```

2. config 점검

```bash
python3 -m harness.agent_runtime doctor --strict
```

3. 작은 task로 smoke

```bash
python3 -m harness.agent_runtime run \
  --tasks output/harness/p0_case_scope_agent_tasks/agent_tasks.json \
  --output-dir output/harness/codex_agent_smoke \
  --max-calls 1 \
  --max-tokens 20000 \
  --stop-on-provider-error
```

4. 한도 초과나 provider error 이후 이어서 실행

```bash
python3 -m harness.agent_runtime run \
  --tasks output/harness/p0_case_scope_agent_tasks/agent_tasks.json \
  --output-dir output/harness/codex_agent_smoke \
  --max-calls 5 \
  --max-tokens 50000 \
  --resume-existing \
  --stop-on-provider-error
```

`--resume-existing`은 이미 accepted 된 output을 건너뛰고 실패/미완료 task만 다시 시도한다.
`--max-calls`나 provider error로 중간 종료되면 exit code 3이 날 수 있지만,
`agent_results.json`에는 그 시점까지 accepted 된 결과가 저장된다. 나중에 한도가 돌아오면
같은 `--output-dir`에 `--resume-existing`을 붙여 이어서 실행한다.

## GPT/OpenAI API provider 연결 확인

1. API key 설정

```bash
export OPENAI_API_KEY="..."
```

2. config 점검

```bash
python3 -m harness.agent_runtime doctor --strict
```

3. 작은 task로 smoke

```bash
python3 -m harness.agent_runtime run \
  --tasks output/harness/p0_case_scope_agent_tasks/agent_tasks.json \
  --output-dir output/harness/openai_agent_smoke \
  --max-calls 2 \
  --max-tokens 20000
```

처음부터 전체 26개 task를 돌리지 말고 `--max-calls`를 낮게 잡아 비용과 출력 형식을 확인한다.

## 바로 가능한 실행과 추가 준비가 필요한 실행

바로 가능:

```bash
python3 -m harness.orchestrator --suite 09 --case-filter case_DFB001 --regression-baseline dfb001-good
python3 -m harness.orchestrator --suite 10 --mode local-samples --variant-filter ue-local-debuggame
python3 -m harness.orchestrator --suite 10 --mode local-samples --variant-filter ue-local-development
```

추가 준비 필요:

```text
LLM agent loop    : Codex login 또는 OPENAI_API_KEY + models.commands 설정
engine worktree   : human approval key
case apply        : human approval key
UE 재빌드/재추출 : Xcode 26 + UE_5.8 + Ghidra/Java/NDK 경로 유지
```
