#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

from .adapters import PrepareStep, Variant, selected_prepare_steps, selected_variants
from .agent_tasks import build_agent_tasks
from .case_scope import CaseScopePlanner, ScopedCase
from .config import HarnessConfig, ROOT
from .gates import human_gate_items, invariant_status, regression_failures
from .memory.store import Memory
from .reporting import (
    canonical_hash,
    git_commit,
    print_summary,
    sha256_directory,
    sha256_file,
    summarize,
    write_json,
)


TIER0_ARCHES = ["x86", "x64", "armv7", "aarch64"]
DEFAULT_CASE_SCOPE_FILE_THRESHOLD = 32
DEFAULT_CASE_SCOPE_BYTE_THRESHOLD = 128 * 1024 * 1024
PREPARE_CACHE_SCHEMA_VERSION = 1
PREPARE_HASH_EXCLUDED_DIRS = {
    "__pycache__",
    ".git",
    "Binaries",
    "Build",
    "DerivedDataCache",
    "Intermediate",
    "Saved",
    "build",
    "dist",
    "output",
    "samples",
}


def _add_engine_to_syspath(engine_root: Path) -> None:
    sys.path.insert(0, str(engine_root))


def _ensure_engine_python(engine_root: Path) -> None:
    if os.environ.get("TDO_HARNESS_NO_VENV_REEXEC") == "1":
        return
    venv_python = engine_root / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not venv_python.exists():
        return
    current = Path(sys.executable).absolute()
    target = venv_python.absolute()
    if current == target:
        return
    os.environ["TDO_HARNESS_NO_VENV_REEXEC"] = "1"
    os.execv(str(target), [str(target), "-m", "harness.orchestrator", *sys.argv[1:]])


class Engine11Runner:
    def __init__(
        self,
        config: HarnessConfig,
        output_root: Path,
        memory: Memory | None = None,
        use_cache: bool = True,
        case_scope_policy: str = "auto",
        case_scope_file_threshold: int = DEFAULT_CASE_SCOPE_FILE_THRESHOLD,
        case_scope_byte_threshold: int = DEFAULT_CASE_SCOPE_BYTE_THRESHOLD,
    ):
        self.config = config
        self.engine_root = config.path("repos", "engine_11")
        self.output_root = output_root
        self.memory = memory
        self.use_cache = use_cache
        self.case_scope_policy = case_scope_policy
        self.case_scope_file_threshold = case_scope_file_threshold
        self.case_scope_byte_threshold = case_scope_byte_threshold
        _ensure_engine_python(self.engine_root)
        _add_engine_to_syspath(self.engine_root)

        from analysis.interprocedural_summary import ProgramSliceGraphBuilder
        from core.edge import DATA_CONTROL_SLICE_EDGES
        from query.backward_slice import BackwardSliceQuery
        from report.expected_validator import ExpectedValidator

        self.ProgramSliceGraphBuilder = ProgramSliceGraphBuilder
        self.DATA_CONTROL_SLICE_EDGES = DATA_CONTROL_SLICE_EDGES
        self.BackwardSliceQuery = BackwardSliceQuery
        self.ExpectedValidator = ExpectedValidator

    def run_variant(self, run_id: str, variant: Variant, run_config_hash: str) -> list[dict]:
        if not variant.sample_dir.exists():
            return [self._error_row(run_id, variant, "NO_SAMPLES", f"missing samples: {variant.sample_dir}", run_config_hash)]
        cases = sorted(variant.sample_dir.rglob(variant.case_glob))
        if not cases:
            return [self._error_row(run_id, variant, "NO_CASES", f"no cases matching {variant.case_glob}", run_config_hash)]
        validator = self.ExpectedValidator(variant.expected_path)
        builder = self.ProgramSliceGraphBuilder()
        scope_planner = CaseScopePlanner(
            variant.sample_dir,
            self.output_root,
            variant.label,
            policy=self.case_scope_policy,
            file_threshold=self.case_scope_file_threshold,
            byte_threshold=self.case_scope_byte_threshold,
        )
        rows = []
        for json_path in cases:
            rows.append(self._run_case(run_id, variant, json_path, validator, builder, run_config_hash, scope_planner))
        return rows

    def _run_case(
        self,
        run_id: str,
        variant: Variant,
        json_path: Path,
        validator,
        builder,
        run_config_hash: str,
        scope_planner: CaseScopePlanner,
    ) -> dict:
        scoped_case = scope_planner.materialize(json_path)
        artifacts = self._artifacts(variant, json_path, run_config_hash, scoped_case)
        engine = self._engine(run_config_hash)
        if self.use_cache and self.memory is not None:
            cached = self.memory.cached_result(
                artifacts.get("pcode_hash"),
                engine.get("commit"),
                run_config_hash,
                artifacts.get("expected_hash"),
            )
            if cached is not None:
                cached["run_id"] = run_id
                cached["suite"] = variant.suite
                cached["variant_label"] = variant.label
                cached["variant"] = variant.variant_dict()
                cached["toolchain"] = self._toolchain()
                cached["engine"] = engine
                cached["artifacts"] = {**artifacts, "result_path": None}
                source_cache = cached.get("cache") or {}
                cached["cache"] = {
                    "hit": True,
                    "source_result_path": (source_cache.get("source_result_path") or source_cache.get("result_path")),
                }
                cached["pcode_scope"] = scoped_case.manifest
                return cached
        try:
            fg = builder.build_for_target(scoped_case.target_path)
            data_sources: set[str] = set()
            control_sources: set[str] = set()
            cuts: list[str] = []
            for sink in fg.sink_index.values():
                data_query = self.BackwardSliceQuery(fg)
                data_result = data_query.run(sink)
                data_sources.update(data_result.source_labels)
                control_query = self.BackwardSliceQuery(fg, self.DATA_CONTROL_SLICE_EDGES, mode="data+control")
                control_sources.update(control_query.run(sink).source_labels)
                cuts.extend(self._cut_points(fg, data_query, sink))
            control_sources -= data_sources
            validation = validator.validate(fg.function_name, data_sources, control_sources)
            missing = validation.get("missing_expected_sources", []) + validation.get("missing_expected_control_sources", [])
            forbidden = validation.get("forbidden_sources_found", []) + validation.get("forbidden_control_sources_found", [])
            return {
                "schema_version": 2,
                "run_id": run_id,
                "suite": variant.suite,
                "variant_label": variant.label,
                "case": validation.get("case_id") or fg.function_name,
                "function": fg.function_name,
                "variant": variant.variant_dict(),
                "toolchain": self._toolchain(),
                "engine": engine,
                "artifacts": artifacts,
                "verdict": validation.get("verdict"),
                "actual_sources": validation.get("actual_sources", []),
                "actual_control_sources": validation.get("actual_control_sources", []),
                "missing": missing,
                "forbidden_found": forbidden,
                "warnings": list(fg.warnings),
                "features": [],
                "edge_kinds_seen": self._edge_kinds(fg),
                "cut": sorted(set(cuts)) if validation.get("verdict") != "PASS" else [],
                "budgets": {"budget_exceeded": False, "details": []},
                "pcode_scope": scoped_case.manifest,
                "cache": {"hit": False},
            }
        except Exception as exc:  # noqa: BLE001
            row = self._error_row(run_id, variant, json_path.stem, str(exc), run_config_hash)
            row["artifacts"] = artifacts
            row["pcode_scope"] = scoped_case.manifest
            return row

    def _error_row(
        self,
        run_id: str,
        variant: Variant,
        case: str,
        error: str,
        run_config_hash: str,
    ) -> dict:
        return {
            "schema_version": 2,
            "run_id": run_id,
            "suite": variant.suite,
            "variant_label": variant.label,
            "case": case,
            "function": case,
            "variant": variant.variant_dict(),
            "toolchain": self._toolchain(),
            "engine": self._engine(run_config_hash),
            "artifacts": self._artifacts(variant, None, run_config_hash),
            "verdict": "ERROR",
            "missing": [],
            "forbidden_found": [],
            "warnings": [error],
            "features": [],
            "edge_kinds_seen": [],
            "cut": [],
            "budgets": {"budget_exceeded": False, "details": []},
        }

    def _cut_points(self, fg, query, sink) -> list[str]:
        result = query.run(sink)
        graph = fg.slice_graph
        leaves = []
        for node in result.visited:
            if any(graph.edges[pred, node].get("kind") in query.edge_policy for pred in graph.predecessors(node)):
                continue
            attrs = graph.nodes[node]
            if attrs.get("kind") == "source_boundary":
                continue
            op = attrs.get("opcode") or attrs.get("kind")
            storage = attrs.get("storage") or str(node)
            leaves.append(f"{op}:{storage}")
        return leaves

    def _edge_kinds(self, fg) -> list[str]:
        return sorted({str(attrs.get("kind")) for _, _, attrs in fg.slice_graph.edges(data=True) if attrs.get("kind")})

    def _toolchain(self) -> dict:
        return {
            "android_ndk_version": str(self.config.value("tools", "android_ndk", "")),
            "ghidra_home": str(self.config.value("tools", "ghidra_home", "")),
            "unreal_engine_root": str(self.config.value("tools", "unreal_engine_root", "")),
        }

    def _engine(self, run_config_hash: str) -> dict:
        return {
            "repo": "trace_data_origin_lowpcode",
            "commit": git_commit(self.engine_root),
            "config_hash": run_config_hash,
            "mode": "summary_first" if self.config.value("defaults", "summary_first", True) else "default",
        }

    def _artifacts(
        self,
        variant: Variant,
        json_path: Path | None,
        run_config_hash: str,
        scoped_case: ScopedCase | None = None,
    ) -> dict:
        if scoped_case is not None:
            pcode_hash = scoped_case.scope_hash
            effective_path = scoped_case.target_path
        elif json_path is not None:
            pcode_hash = sha256_file(json_path)
            effective_path = json_path
        else:
            pcode_hash = sha256_directory(variant.sample_dir, variant.case_glob)
            effective_path = variant.sample_dir
        return {
            "binary_path": str(variant.binary_path) if variant.binary_path else None,
            "binary_hash": sha256_file(variant.binary_path),
            "pcode_path": str(json_path or variant.sample_dir),
            "effective_pcode_path": str(effective_path),
            "pcode_hash": pcode_hash,
            "root_pcode_hash": sha256_file(json_path) if json_path else None,
            "metadata_path": str(json_path or variant.sample_dir),
            "result_path": None,
            "diagnose_dump_path": None,
            "expected_path": str(variant.expected_path),
            "expected_hash": sha256_file(variant.expected_path)
            if variant.expected_path.is_file()
            else sha256_directory(variant.expected_path, "*.expected.json"),
            "run_config_hash": run_config_hash,
        }


def _parse_suites(text: str) -> set[str]:
    aliases = {"9": "09", "09": "09", "tdo": "09", "10": "10", "ue": "10"}
    selected = set()
    for part in text.split(","):
        key = part.strip()
        if not key:
            continue
        selected.add(aliases.get(key, key))
    return selected


def _parse_arches(text: str) -> list[str]:
    if text.strip().lower() == "all":
        return list(TIER0_ARCHES)
    arches = [part.strip() for part in text.split(",") if part.strip()]
    unknown = sorted(set(arches) - set(TIER0_ARCHES))
    if unknown:
        raise ValueError(f"unknown arch for local prepare: {', '.join(unknown)}")
    return arches or ["x64"]


def _safe_label(text: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in text)


def _run_prepare_steps(
    steps: list[PrepareStep],
    output_root: Path,
    dry_run: bool = False,
    memory: Memory | None = None,
    changed_only: bool = True,
) -> list[dict]:
    records: list[dict] = []
    prepare_dir = output_root / "prepare"
    prepare_dir.mkdir(parents=True, exist_ok=True)
    for index, step in enumerate(steps, start=1):
        log_path = prepare_dir / f"{index:02d}_{_safe_label(step.label)}.log"
        prepare_fingerprint = _prepare_fingerprint(step)
        cache_key = canonical_hash(prepare_fingerprint)
        record = {
            "label": step.label,
            "command": list(step.command),
            "cwd": str(step.cwd),
            "inputs": [str(path) for path in step.inputs],
            "outputs": [str(path) for path in step.outputs],
            "optional": step.optional,
            "dry_run": dry_run,
            "changed_only": changed_only,
            "cache_key": cache_key,
            "cache_hit": False,
            "skipped": False,
            "returncode": 0,
            "log_path": str(log_path),
        }
        print(f"[prepare] {step.label}: {' '.join(step.command)}")
        cached = memory.cached_prepare_step(cache_key) if changed_only and memory is not None else None
        if cached is not None and _outputs_ready(step.outputs):
            record.update(
                {
                    "cache_hit": True,
                    "skipped": True,
                    "source_log_path": cached.get("log_path"),
                    "output_exists": {str(path): _output_ready(path) for path in step.outputs},
                }
            )
            log_path.write_text(
                "changed-only cache hit: command skipped\n"
                f"cache_key: {cache_key}\n"
                f"source_log_path: {cached.get('log_path')}\n",
                encoding="utf-8",
            )
            print(f"[prepare] SKIP {step.label}: changed-only cache hit")
            records.append(record)
            continue
        if dry_run:
            log_path.write_text("dry-run: command not executed\n", encoding="utf-8")
            records.append(record)
            continue

        env = {**os.environ, **step.env}
        result = subprocess.run(
            step.command,
            cwd=step.cwd,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        log_path.write_text(result.stdout or "", encoding="utf-8")
        record["returncode"] = result.returncode
        record["output_exists"] = {str(path): _output_ready(path) for path in step.outputs}
        records.append(record)
        if result.returncode == 0 and memory is not None:
            memory.record_prepare_step(cache_key, record)
        if result.returncode != 0:
            print(f"[prepare] FAILED {step.label}; see {log_path}")
            if not step.optional:
                break
    return records


def _prepare_failed(records: list[dict]) -> bool:
    return any(row.get("returncode") != 0 and not row.get("optional") for row in records)


def _prepare_fingerprint(step: PrepareStep) -> dict:
    return {
        "schema_version": PREPARE_CACHE_SCHEMA_VERSION,
        "label": step.label,
        "command": list(step.command),
        "cwd": str(step.cwd),
        "env": {key: step.env[key] for key in sorted(step.env)},
        "inputs": [_input_fingerprint(path) for path in step.inputs],
        "outputs": [str(path) for path in step.outputs],
    }


def _input_fingerprint(path: Path) -> dict:
    path = Path(path)
    if path.is_file():
        return {"path": str(path), "type": "file", "sha256": sha256_file(path)}
    if path.is_dir():
        digest = []
        for item in sorted(path.rglob("*")):
            if not item.is_file() or _excluded_input_path(item):
                continue
            digest.append(
                {
                    "path": str(item.relative_to(path)),
                    "sha256": sha256_file(item),
                }
            )
        return {"path": str(path), "type": "dir", "files": digest}
    return {"path": str(path), "type": "missing", "sha256": None}


def _excluded_input_path(path: Path) -> bool:
    return any(part in PREPARE_HASH_EXCLUDED_DIRS for part in path.parts)


def _outputs_ready(outputs: tuple[Path, ...]) -> bool:
    return bool(outputs) and all(_output_ready(path) for path in outputs)


def _output_ready(path: Path) -> bool:
    if path.is_file():
        return True
    if path.is_dir():
        return any(item.is_file() for item in path.rglob("*"))
    return False


def _load_regression_baseline(config: HarnessConfig, memory: Memory | None, baseline: str) -> tuple[list[dict], str]:
    candidate = Path(baseline).expanduser()
    if candidate.is_dir():
        candidate = candidate / "failure_report_v2.json"
    if candidate.is_file():
        return json.loads(candidate.read_text(encoding="utf-8")), str(candidate)

    output_candidate = config.path("output", "root") / baseline / "failure_report_v2.json"
    if output_candidate.is_file():
        return json.loads(output_candidate.read_text(encoding="utf-8")), str(output_candidate)

    if memory is not None and memory.baseline_map_path.exists():
        baseline_map = json.loads(memory.baseline_map_path.read_text(encoding="utf-8"))
        run = (baseline_map.get("runs") or {}).get(baseline)
        if run:
            report_path = Path(str(run.get("output_root") or "")) / "failure_report_v2.json"
            if report_path.is_file():
                return json.loads(report_path.read_text(encoding="utf-8")), str(report_path)
    if memory is not None and memory.baseline_pins_path.exists():
        pins = json.loads(memory.baseline_pins_path.read_text(encoding="utf-8"))
        pin = (pins.get("pins") or {}).get(baseline)
        if pin:
            report_path = Path(str(pin.get("report_path") or ""))
            if report_path.is_file():
                return json.loads(report_path.read_text(encoding="utf-8")), str(report_path)
    raise FileNotFoundError(f"regression baseline not found: {baseline}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run deterministic 09/10/11 TDO harness checks.")
    parser.add_argument("--config", type=Path, default=ROOT / "harness" / "config.yaml")
    parser.add_argument("--suite", default="10", help="Comma-separated suites: 09,10")
    parser.add_argument("--mode", default=None, choices=["release-artifacts", "local-samples"])
    parser.add_argument("--list-variants", action="store_true")
    parser.add_argument("--case-filter", default="", help="Substring filter for case JSON filenames.")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--no-ledger", action="store_true", help="Do not update harness memory ledgers.")
    parser.add_argument("--no-cache", action="store_true", help="Do not reuse cached verify results.")
    parser.add_argument(
        "--regression-baseline",
        default="",
        help="Compare I3 against a prior run id, output directory, or failure_report_v2.json path.",
    )
    parser.add_argument("--variant-filter", default="", help="Substring filter for variant labels.")
    parser.add_argument("--prepare-artifacts", action="store_true", help="Run local build/extract preparation before analysis.")
    parser.add_argument("--prepare-only", action="store_true", help="Run preparation and stop before Engine11 analysis.")
    parser.add_argument("--prepare-dry-run", action="store_true", help="Print and record preparation commands without executing them.")
    parser.add_argument("--force-prepare", action="store_true", help="Disable changed-only prepare cache and always run prepare commands.")
    parser.add_argument("--profile", default="P0", choices=["P0", "P1"], help="Local Tier0 build/extract profile.")
    parser.add_argument("--arch", default="x64", help="Local Tier0 arch list: x86,x64,armv7,aarch64 or all.")
    parser.add_argument("--skip-tier0-prepare", action="store_true", help="Skip local Tier0 build/extract prepare steps.")
    parser.add_argument("--include-ue-build", action="store_true", help="Also try the local UE build step.")
    parser.add_argument("--include-ue-extract", action="store_true", help="Also extract local UE build low-pcode with Ghidra.")
    parser.add_argument(
        "--case-scope",
        choices=["auto", "always", "never"],
        default=None,
        help="Materialize a per-case low-pcode closure before Engine11 analysis.",
    )
    parser.add_argument(
        "--case-scope-file-threshold",
        type=int,
        default=None,
        help="Auto case-scope when a sample directory has more low-pcode files than this.",
    )
    parser.add_argument(
        "--case-scope-byte-threshold",
        type=int,
        default=None,
        help="Auto case-scope when a sample directory is larger than this many bytes.",
    )
    args = parser.parse_args(argv)

    config = HarnessConfig.load(args.config if args.config.exists() else None)
    mode = args.mode or str(config.value("defaults", "mode", "release-artifacts"))
    suites = _parse_suites(args.suite)
    run_id = args.run_id or uuid.uuid4().hex[:12]
    output_root = args.output_dir or (config.path("output", "root") / run_id)
    memory = None if args.no_ledger and args.no_cache else Memory(config.path("output", "memory"))

    if args.prepare_artifacts or args.prepare_only:
        try:
            arches = _parse_arches(args.arch)
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        steps = selected_prepare_steps(
            config,
            suites,
            mode,
            args.profile,
            arches,
            include_tier0=not args.skip_tier0_prepare,
            include_ue_build=args.include_ue_build,
            include_ue_extract=args.include_ue_extract,
        )
        changed_only = not args.force_prepare and bool(config.value("defaults", "changed_only_prepare", True))
        prepare_records = _run_prepare_steps(
            steps,
            output_root,
            dry_run=args.prepare_dry_run,
            memory=memory,
            changed_only=changed_only,
        )
        write_json(output_root / "prepare_report.json", prepare_records)
        if _prepare_failed(prepare_records):
            return 1
        if args.prepare_only:
            print(f"[prepare] saved {output_root / 'prepare_report.json'}")
            return 0

    variants = selected_variants(config, suites, mode)
    if args.variant_filter:
        variants = [variant for variant in variants if args.variant_filter in variant.label]
    if args.case_filter:
        variants = [
            Variant(
                **{
                    **variant.__dict__,
                    "case_glob": f"*{args.case_filter}*",
                }
            )
            for variant in variants
        ]

    if args.list_variants:
        for variant in variants:
            print(f"{variant.suite:18} {variant.label:32} {variant.sample_dir}")
        return 0
    if not variants:
        print("error: no variants selected", file=sys.stderr)
        return 2

    run_config = {
        "engine_mode": "summary_first" if config.value("defaults", "summary_first", True) else "default",
        "report_schema_version": 2,
        "validator": "expected_validator_v1",
        "case_scope": args.case_scope or str(config.value("defaults", "case_scope", "auto")),
        "case_scope_file_threshold": args.case_scope_file_threshold
        if args.case_scope_file_threshold is not None
        else int(config.value("defaults", "case_scope_file_threshold", DEFAULT_CASE_SCOPE_FILE_THRESHOLD)),
        "case_scope_byte_threshold": args.case_scope_byte_threshold
        if args.case_scope_byte_threshold is not None
        else int(config.value("defaults", "case_scope_byte_threshold", DEFAULT_CASE_SCOPE_BYTE_THRESHOLD)),
    }
    run_config_hash = canonical_hash(run_config)

    runner = Engine11Runner(
        config,
        output_root,
        memory=memory,
        use_cache=not args.no_cache,
        case_scope_policy=str(run_config["case_scope"]),
        case_scope_file_threshold=int(run_config["case_scope_file_threshold"]),
        case_scope_byte_threshold=int(run_config["case_scope_byte_threshold"]),
    )
    reports: list[dict] = []
    for variant in variants:
        print(f"[harness] {variant.label}: {variant.sample_dir}")
        reports.extend(runner.run_variant(run_id, variant, run_config_hash))

    summary = summarize(reports)
    gate = invariant_status(reports, ROOT)
    if args.regression_baseline:
        try:
            baseline_report, baseline_ref = _load_regression_baseline(config, memory, args.regression_baseline)
        except FileNotFoundError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        regressions = regression_failures(baseline_report, reports)
        gate["I3_regression_zero"] = not regressions
        gate["regression_baseline"] = baseline_ref
        gate["regressions"] = regressions
    for row in reports:
        row["artifacts"]["result_path"] = str(output_root / "failure_report_v2.json")
    human_gate = human_gate_items(reports, gate)
    agent_tasks = build_agent_tasks(reports, human_gate, ROOT / "harness" / "agents")

    write_json(output_root / "failure_report_v2.json", reports)
    write_json(output_root / "summary.json", summary)
    write_json(output_root / "gate.json", gate)
    write_json(output_root / "human_gate.json", human_gate)
    write_json(output_root / "agent_tasks.json", agent_tasks)
    if not args.no_ledger and memory is not None:
        memory.record_run(run_id, reports, summary, gate, output_root, human_gate=human_gate)

    print_summary(summary)
    print(f"gate: {gate}")
    print(f"[saved] {output_root}")
    return 1 if any(
        [
            not gate.get("I1_crash_zero"),
            not gate.get("I2_false_positive_zero"),
            gate.get("I3_regression_zero") is False,
        ]
    ) else 0


if __name__ == "__main__":
    raise SystemExit(main())
