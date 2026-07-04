#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import HarnessConfig, ROOT
from .gates import invariant_status
from .reporting import write_json


FRONTIER_LOOP_SCHEMA_VERSION = 1


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path, default: Any = None) -> Any:
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _run_logged(cmd: list[str], log_path: Path, cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, check=False)
    log_path.write_text(
        json.dumps({"cmd": cmd, "cwd": str(cwd), "started_at": _now()}, ensure_ascii=False, indent=2)
        + "\n\n"
        + (proc.stdout or "")
        + (("\n[stderr]\n" + proc.stderr) if proc.stderr else "")
        + f"\n\n[returncode] {proc.returncode}\n",
        encoding="utf-8",
    )
    return proc


def _metrics(report: list[dict]) -> dict:
    counts = {"pass": 0, "fail": 0, "error": 0, "degraded": 0, "false_positive": 0}
    for row in report:
        verdict = str(row.get("verdict") or "ERROR").lower()
        if verdict == "pass":
            counts["pass"] += 1
        elif verdict == "error":
            counts["error"] += 1
        elif verdict == "degraded":
            counts["degraded"] += 1
        else:
            counts["fail"] += 1
        if row.get("forbidden_found"):
            counts["false_positive"] += 1
    counts["total"] = sum(counts[key] for key in ("pass", "fail", "error", "degraded"))
    return counts


def _report_excerpt(report: list[dict], limit: int) -> list[dict]:
    interesting = [row for row in report if row.get("verdict") != "PASS" or row.get("forbidden_found")]
    if not interesting:
        interesting = report[:limit]
    excerpt: list[dict] = []
    for row in interesting[:limit]:
        excerpt.append(
            {
                "suite": row.get("suite"),
                "variant": row.get("variant_label"),
                "case": row.get("case"),
                "function": row.get("function"),
                "verdict": row.get("verdict"),
                "missing": row.get("missing", []),
                "forbidden_found": row.get("forbidden_found", []),
                "features": row.get("features", []),
                "cut": row.get("cut", [])[:10],
                "pcode_scope": row.get("pcode_scope", {}),
                "artifacts": row.get("artifacts", {}),
            }
        )
    return excerpt


def _gap_note(args: argparse.Namespace) -> str:
    pieces = []
    if args.gap_note_file and args.gap_note_file.is_file():
        pieces.append(args.gap_note_file.read_text(encoding="utf-8").strip())
    if args.gap_note:
        pieces.append(args.gap_note.strip())
    if not pieces:
        pieces.append(
            "Author stronger fusion/frontier cases that combine existing 09/10 capabilities. "
            "The goal is robust backward slicing over rebuilt binaries, not teaching Engine11 named cases."
        )
    return "\n\n".join(piece for piece in pieces if piece)


def _write_case_author_tasks(args: argparse.Namespace, config: HarnessConfig, report_path: Path, tasks_path: Path) -> dict:
    report = _read_json(report_path, [])
    if not isinstance(report, list):
        report = []
    capability_map = _read_json(config.path("output", "memory") / "capability_map.json", {})
    task = {
        "agent": "case_author",
        "schema_version": 1,
        "role_prompt": str(ROOT / "harness" / "agents" / "case_author.md"),
        "requires_evidence": True,
        "input": {
            "capability_map": capability_map if isinstance(capability_map, dict) else {},
            "report": _report_excerpt(report, args.prompt_max_cases),
            "report_metrics": _metrics(report),
            "gate": invariant_status(report, ROOT) if report else {},
            "gap_note": _gap_note(args),
            "design_rules": {
                "no_arg_no_ret": True,
                "convention_free": True,
                "no_abi_specific_parameter_or_return_semantics": True,
                "source_sink_markers_stay_in_boundary_provider_or_wrappers": True,
                "no_expected_manifest_or_sample_json_edits_to_pass": True,
                "no_case_id_helper_name_or_source_label_hardcoding_in_engine": True,
            },
        },
    }
    write_json(tasks_path, [task])
    return {"tasks_path": str(tasks_path), "task_count": 1}


def _run_regression(args: argparse.Namespace, output_root: Path, phase: str) -> dict:
    output_dir = output_root / phase
    cmd = [
        sys.executable,
        "-m",
        "harness.orchestrator",
        "--config",
        str(args.config),
        "--suite",
        args.suite,
        "--mode",
        args.mode,
        "--run-id",
        f"{args.run_id}_{phase}",
        "--output-dir",
        str(output_dir),
        "--case-scope",
        args.case_scope,
        "--no-cache",
    ]
    if args.case_filter:
        cmd.extend(["--case-filter", args.case_filter])
    if args.variant_filter:
        cmd.extend(["--variant-filter", args.variant_filter])
    if args.include_proposed_regression:
        cmd.append("--include-proposed-regression")
    proc = _run_logged(cmd, output_root / f"{phase}.log")
    report_path = output_dir / "failure_report_v2.json"
    report = _read_json(report_path, [])
    return {
        "phase": phase,
        "command": cmd,
        "returncode": proc.returncode,
        "output_dir": str(output_dir),
        "report_path": str(report_path),
        "metrics": _metrics(report if isinstance(report, list) else []),
    }


def _run_case_author(args: argparse.Namespace, output_root: Path, tasks_path: Path) -> dict:
    agent_dir = output_root / "case_author_agent"
    proposal_dir = output_root / "case_author_proposals"
    cmd = [
        sys.executable,
        "-m",
        "harness.agent_loop",
        "--config",
        str(args.config),
        "--tasks",
        str(tasks_path),
        "--output-dir",
        str(agent_dir),
        "--duration-hours",
        str(args.author_duration_hours),
        "--chunk-calls",
        str(args.author_chunk_calls),
        "--chunk-tokens",
        str(args.author_chunk_tokens),
        "--max-total-calls",
        str(args.author_calls),
        "--materialize-proposals",
        "--proposal-output-dir",
        str(proposal_dir),
        "--scaffold-work-items",
        "--stop-on-no-progress",
    ]
    if args.author_executor:
        cmd.extend(["--executor", args.author_executor])
    proc = _run_logged(cmd, output_root / "case_author_agent.log")
    return {
        "command": cmd,
        "returncode": proc.returncode,
        "agent_dir": str(agent_dir),
        "proposal_dir": str(proposal_dir),
        "proposal_manifest": str(proposal_dir / "proposal_manifest.json"),
    }


def _run_doctor(args: argparse.Namespace, output_root: Path, proposal_dir: Path) -> dict:
    cmd = [
        sys.executable,
        "-m",
        "harness.work_items",
        "--config",
        str(args.config),
        "doctor",
        "--proposal-root",
        str(proposal_dir),
        "--json",
    ]
    proc = _run_logged(cmd, output_root / "proposal_doctor.log")
    try:
        summary = json.loads(proc.stdout)
    except json.JSONDecodeError:
        summary = {}
    write_json(output_root / "proposal_doctor.json", summary)
    return {
        "command": cmd,
        "returncode": proc.returncode,
        "summary_path": str(output_root / "proposal_doctor.json"),
        "checked": summary.get("checked"),
        "errors": summary.get("errors") or [],
        "missing": summary.get("missing") or [],
    }


def _target_from_expected(expected_path: Path) -> str:
    payload = _read_json(expected_path, {})
    expected = payload.get("expected") if isinstance(payload, dict) else {}
    if not isinstance(expected, dict):
        expected = {}
    manifest_case = expected.get("manifest_case") if isinstance(expected.get("manifest_case"), dict) else {}
    binary = str(expected.get("binary") or manifest_case.get("binary") or "")
    source_file = str(expected.get("source_file") or manifest_case.get("source_file") or "")
    if "unreal" in binary.lower() or "TraceCases2.cpp" in source_file:
        return "suite10-ue"
    return "suite10-cpp"


def _apply_or_plan_cases(args: argparse.Namespace, output_root: Path, proposal_dir: Path) -> dict:
    if args.apply_mode == "none":
        result = {"mode": args.apply_mode, "case_count": 0, "rows": [], "skipped": True}
        write_json(output_root / "case_apply_plan.json", result)
        return result
    expected_paths = sorted((proposal_dir / "work_items" / "source_cases").glob("*.expected.proposal.json"))
    rows: list[dict] = []
    for expected_path in expected_paths:
        target = _target_from_expected(expected_path)
        cmd = [
            sys.executable,
            "-m",
            "harness.work_items",
            "--config",
            str(args.config),
            "case-apply",
            "--expected",
            str(expected_path),
            "--target",
            target,
        ]
        if args.apply_mode == "approved":
            cmd.append("--apply")
            if args.approval_key:
                cmd.extend(["--approval-key", args.approval_key])
            if args.allow_unapproved_case_apply:
                cmd.append("--allow-unapproved")
        else:
            cmd.append("--dry-run")
        log_path = output_root / "case_apply" / f"{expected_path.stem}.log"
        proc = _run_logged(cmd, log_path)
        rows.append(
            {
                "expected": str(expected_path),
                "target": target,
                "command": cmd,
                "returncode": proc.returncode,
                "log_path": str(log_path),
                "mode": args.apply_mode,
            }
        )
    result = {"mode": args.apply_mode, "case_count": len(rows), "rows": rows}
    write_json(output_root / "case_apply_plan.json", result)
    return result


def _run_engine_dev_loop(args: argparse.Namespace, output_root: Path) -> dict:
    cmd = [
        sys.executable,
        "-m",
        "harness.engine_dev_loop",
        "--config",
        str(args.config),
        "--suite",
        args.suite,
        "--mode",
        args.mode,
        "--run-id",
        f"{args.run_id}_engine",
        "--output-dir",
        str(output_root / "engine_dev_loop"),
        "--duration-hours",
        str(args.engine_duration_hours),
        "--max-cycles",
        str(args.engine_max_cycles),
        "--analysis-calls",
        str(args.engine_analysis_calls),
        "--analysis-chunk-calls",
        str(args.engine_analysis_chunk_calls),
        "--analysis-chunk-tokens",
        str(args.engine_analysis_chunk_tokens),
        "--prompt-max-cases",
        str(args.prompt_max_cases),
        "--editor-reasoning-effort",
        args.editor_reasoning_effort,
        "--editor-timeout",
        str(args.editor_timeout),
        "--repair-on-regression",
        "--no-stop-on-regression",
        "--stop-on-no-progress",
        "--include-proposed-regression",
    ]
    if args.codex_bin:
        cmd.extend(["--codex-bin", args.codex_bin])
    if args.case_filter:
        cmd.extend(["--case-filter", args.case_filter])
    if args.variant_filter:
        cmd.extend(["--variant-filter", args.variant_filter])
    if args.operator_note_file:
        cmd.extend(["--editor-extra-instructions-file", str(args.operator_note_file)])
    proc = _run_logged(cmd, output_root / "engine_dev_loop.log")
    return {
        "command": cmd,
        "returncode": proc.returncode,
        "output_dir": str(output_root / "engine_dev_loop"),
        "state_path": str(output_root / "engine_dev_loop" / "engine_dev_loop_state.json"),
    }


def run_frontier_loop(args: argparse.Namespace) -> int:
    config = HarnessConfig.load(args.config if args.config.exists() else None)
    output_root = args.output_dir or (config.path("output", "root") / args.run_id)
    if output_root.exists() and args.clean_output:
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    state: dict[str, Any] = {
        "schema_version": FRONTIER_LOOP_SCHEMA_VERSION,
        "run_id": args.run_id,
        "status": "running",
        "started_at": _now(),
        "output_root": str(output_root),
        "phases": [],
    }
    state_path = output_root / "frontier_case_loop_state.json"
    write_json(state_path, state)

    baseline = _run_regression(args, output_root, "baseline_regression")
    state["phases"].append({"name": "baseline_regression", **baseline})
    if baseline["returncode"] not in {0, 1} or not Path(str(baseline["report_path"])).is_file():
        state["status"] = "baseline_failed"
        write_json(state_path, state)
        return 3

    tasks = _write_case_author_tasks(args, config, Path(str(baseline["report_path"])), output_root / "case_author_tasks.json")
    state["phases"].append({"name": "case_author_tasks", **tasks})

    author = _run_case_author(args, output_root, Path(str(tasks["tasks_path"])))
    state["phases"].append({"name": "case_author", **author})
    proposal_dir = Path(str(author["proposal_dir"]))
    if author["returncode"] not in {0, 3} or not Path(str(author["proposal_manifest"])).is_file():
        state["status"] = "case_author_failed"
        write_json(state_path, state)
        return 3

    doctor = _run_doctor(args, output_root, proposal_dir)
    state["phases"].append({"name": "proposal_doctor", **doctor})
    if doctor["returncode"] != 0:
        state["status"] = "proposal_doctor_failed"
        write_json(state_path, state)
        return 3

    apply_result = _apply_or_plan_cases(args, output_root, proposal_dir)
    state["phases"].append({"name": "case_apply", **apply_result})
    if any(row.get("returncode") != 0 for row in apply_result["rows"]):
        state["status"] = "case_apply_failed"
        write_json(state_path, state)
        return 3

    if args.run_engine_dev_loop:
        engine = _run_engine_dev_loop(args, output_root)
        state["phases"].append({"name": "engine_dev_loop", **engine})
        if engine["returncode"] not in {0, 3}:
            state["status"] = "engine_dev_loop_failed"
            write_json(state_path, state)
            return 3

    state["status"] = "complete"
    state["finished_at"] = _now()
    write_json(state_path, state)
    print(f"[frontier-case-loop] complete: {state_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Author frontier cases, materialize work items, and optionally run Engine11 repair.")
    parser.add_argument("--config", type=Path, default=ROOT / "harness" / "config.yaml")
    parser.add_argument("--run-id", default="frontier_case_loop")
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--clean-output", action="store_true")
    parser.add_argument("--suite", default="09,10")
    parser.add_argument("--mode", default="local-samples", choices=["release-artifacts", "local-samples"])
    parser.add_argument("--case-scope", default="auto", choices=["auto", "always", "never"])
    parser.add_argument("--case-filter", default="")
    parser.add_argument("--variant-filter", default="")
    parser.add_argument("--include-proposed-regression", action="store_true")
    parser.add_argument("--prompt-max-cases", type=int, default=24)
    parser.add_argument("--gap-note", default="")
    parser.add_argument("--gap-note-file", type=Path, default=None)

    parser.add_argument("--author-calls", type=int, default=4)
    parser.add_argument("--author-duration-hours", type=float, default=1.0)
    parser.add_argument("--author-chunk-calls", type=int, default=4)
    parser.add_argument("--author-chunk-tokens", type=int, default=100000)
    parser.add_argument("--author-executor", default="")

    parser.add_argument("--apply-mode", default="dry-run", choices=["none", "dry-run", "approved"])
    parser.add_argument("--approval-key", default="")
    parser.add_argument("--allow-unapproved-case-apply", action="store_true")

    parser.add_argument("--run-engine-dev-loop", action="store_true")
    parser.add_argument("--engine-duration-hours", type=float, default=3.0)
    parser.add_argument("--engine-max-cycles", type=int, default=6)
    parser.add_argument("--engine-analysis-calls", type=int, default=12)
    parser.add_argument("--engine-analysis-chunk-calls", type=int, default=6)
    parser.add_argument("--engine-analysis-chunk-tokens", type=int, default=100000)
    parser.add_argument("--editor-reasoning-effort", default="high", choices=["low", "medium", "high", "xhigh"])
    parser.add_argument("--editor-timeout", type=float, default=7200.0)
    parser.add_argument("--codex-bin", default="")
    parser.add_argument("--operator-note-file", type=Path, default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    return run_frontier_loop(build_parser().parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
