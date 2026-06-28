#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
import uuid
from pathlib import Path

from .adapters import Variant, selected_variants
from .config import HarnessConfig, ROOT
from .gates import invariant_status
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
    def __init__(self, config: HarnessConfig, memory: Memory | None = None, use_cache: bool = True):
        self.config = config
        self.engine_root = config.path("repos", "engine_11")
        self.memory = memory
        self.use_cache = use_cache
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
        rows = []
        for json_path in cases:
            rows.append(self._run_case(run_id, variant, json_path, validator, builder, run_config_hash))
        return rows

    def _run_case(
        self,
        run_id: str,
        variant: Variant,
        json_path: Path,
        validator,
        builder,
        run_config_hash: str,
    ) -> dict:
        artifacts = self._artifacts(variant, json_path, run_config_hash)
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
                return cached
        try:
            fg = builder.build_for_target(json_path)
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
                "cache": {"hit": False},
            }
        except Exception as exc:  # noqa: BLE001
            row = self._error_row(run_id, variant, json_path.stem, str(exc), run_config_hash)
            row["artifacts"] = artifacts
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

    def _artifacts(self, variant: Variant, json_path: Path | None, run_config_hash: str) -> dict:
        return {
            "binary_path": str(variant.binary_path) if variant.binary_path else None,
            "binary_hash": sha256_file(variant.binary_path),
            "pcode_path": str(json_path or variant.sample_dir),
            "pcode_hash": sha256_file(json_path) if json_path else sha256_directory(variant.sample_dir, variant.case_glob),
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
    args = parser.parse_args(argv)

    config = HarnessConfig.load(args.config if args.config.exists() else None)
    mode = args.mode or str(config.value("defaults", "mode", "release-artifacts"))
    suites = _parse_suites(args.suite)
    variants = selected_variants(config, suites, mode)
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

    run_id = args.run_id or uuid.uuid4().hex[:12]
    output_root = args.output_dir or (config.path("output", "root") / run_id)
    run_config = {
        "engine_mode": "summary_first" if config.value("defaults", "summary_first", True) else "default",
        "report_schema_version": 2,
        "validator": "expected_validator_v1",
    }
    run_config_hash = canonical_hash(run_config)

    memory = None if args.no_ledger and args.no_cache else Memory(config.path("output", "memory"))
    runner = Engine11Runner(config, memory=memory, use_cache=not args.no_cache)
    reports: list[dict] = []
    for variant in variants:
        print(f"[harness] {variant.label}: {variant.sample_dir}")
        reports.extend(runner.run_variant(run_id, variant, run_config_hash))

    summary = summarize(reports)
    gate = invariant_status(reports, ROOT)
    for row in reports:
        row["artifacts"]["result_path"] = str(output_root / "failure_report_v2.json")

    write_json(output_root / "failure_report_v2.json", reports)
    write_json(output_root / "summary.json", summary)
    write_json(output_root / "gate.json", gate)
    if not args.no_ledger and memory is not None:
        memory.record_run(run_id, reports, summary, gate, output_root)

    print_summary(summary)
    print(f"gate: {gate}")
    print(f"[saved] {output_root}")
    return 1 if not gate.get("I1_crash_zero") or not gate.get("I2_false_positive_zero") else 0


if __name__ == "__main__":
    raise SystemExit(main())
