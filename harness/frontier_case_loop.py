#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shlex
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


def _strip_codex_prefix(model: str) -> str:
    return model.split(":", 1)[1] if model.startswith("codex:") else model


def _case_author_executor(args: argparse.Namespace, config: HarnessConfig) -> str:
    if args.author_executor:
        return args.author_executor
    if not args.codex_bin:
        return ""
    agent_tiers = config.value("models", "agent_tiers", {}) or {}
    tier = str(agent_tiers.get("case_author") or "strong")
    model = _strip_codex_prefix(str(args.author_model or config.value("models", tier, "") or ""))
    cmd = [
        sys.executable,
        "-m",
        "harness.providers.codex_cli_agent_executor",
        "--codex-bin",
        str(args.codex_bin),
        "--reasoning-effort",
        args.author_reasoning_effort,
    ]
    if model:
        cmd.extend(["--model", model])
    return " ".join(shlex.quote(part) for part in cmd)


def _run_case_author(args: argparse.Namespace, config: HarnessConfig, output_root: Path, tasks_path: Path) -> dict:
    agent_dir = output_root / "case_author_agent"
    proposal_dir = output_root / "case_author_proposals"
    executor = _case_author_executor(args, config)
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
    if executor:
        cmd.extend(["--executor", executor])
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


def _case_id_from_expected(expected_path: Path) -> str:
    payload = _read_json(expected_path, {})
    if not isinstance(payload, dict):
        return expected_path.stem.split(".", 1)[0]
    expected = payload.get("expected") if isinstance(payload.get("expected"), dict) else {}
    manifest_case = expected.get("manifest_case") if isinstance(expected.get("manifest_case"), dict) else {}
    return str(payload.get("case_id") or expected.get("id") or manifest_case.get("id") or expected_path.stem.split(".", 1)[0])


def _apply_or_plan_cases(args: argparse.Namespace, output_root: Path, proposal_dir: Path) -> dict:
    if args.apply_mode == "none":
        result = {"mode": args.apply_mode, "case_count": 0, "rows": [], "skipped": True}
        write_json(output_root / "case_apply_plan.json", result)
        return result
    expected_paths = sorted((proposal_dir / "work_items" / "source_cases").glob("*.expected.proposal.json"))
    rows: list[dict] = []
    for expected_path in expected_paths:
        target = _target_from_expected(expected_path)
        case_id = _case_id_from_expected(expected_path)
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
                "case_id": case_id,
                "command": cmd,
                "returncode": proc.returncode,
                "log_path": str(log_path),
                "mode": args.apply_mode,
            }
        )
    result = {"mode": args.apply_mode, "case_count": len(rows), "rows": rows}
    write_json(output_root / "case_apply_plan.json", result)
    return result


def _successful_applied_cases(apply_result: dict) -> list[dict]:
    if apply_result.get("mode") != "approved":
        return []
    cases = []
    seen = set()
    for row in apply_result.get("rows") or []:
        if row.get("returncode") != 0:
            continue
        case_id = str(row.get("case_id") or "")
        target = str(row.get("target") or "")
        if not case_id or (case_id, target) in seen:
            continue
        seen.add((case_id, target))
        cases.append({"case_id": case_id, "target": target, "expected": row.get("expected")})
    return cases


def _parse_csv(text: str, default: list[str]) -> list[str]:
    values = [part.strip() for part in str(text or "").split(",") if part.strip()]
    return values or list(default)


def _safe_label(text: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "_" for ch in text)[:160]


def _regenerate_expected(args: argparse.Namespace, output_root: Path, apply_result: dict) -> dict:
    applied_cases = _successful_applied_cases(apply_result)
    if not args.regenerate_expected:
        result = {"skipped": True, "reason": "regenerate_expected disabled", "rows": []}
        write_json(output_root / "expected_regeneration.json", result)
        return result
    if not applied_cases:
        result = {"skipped": True, "reason": "no approved applied cases", "rows": []}
        write_json(output_root / "expected_regeneration.json", result)
        return result
    scripts = {
        "suite10-cpp": ROOT / "cpp_like" / "tools" / "generate_expected_from_manifest.py",
        "suite10-ue": ROOT / "unreal_playground" / "tools" / "generate_expected_from_manifest.py",
    }
    rows = []
    for target in sorted({case["target"] for case in applied_cases}):
        script = scripts.get(target)
        if script is None:
            rows.append({"target": target, "returncode": 2, "error": f"unknown target: {target}"})
            continue
        cmd = [sys.executable, str(script)]
        log_path = output_root / "expected_regeneration" / f"{target}.log"
        proc = _run_logged(cmd, log_path)
        rows.append({"target": target, "command": cmd, "returncode": proc.returncode, "log_path": str(log_path)})
    result = {"skipped": False, "rows": rows}
    write_json(output_root / "expected_regeneration.json", result)
    return result


def _run_prepare_after_apply(args: argparse.Namespace, output_root: Path, apply_result: dict) -> dict:
    applied_cases = _successful_applied_cases(apply_result)
    if not args.prepare_after_apply:
        result = {"skipped": True, "reason": "prepare_after_apply disabled", "rows": []}
        write_json(output_root / "prepare_after_apply.json", result)
        return result
    if not applied_cases:
        result = {"skipped": True, "reason": "no approved applied cases", "rows": []}
        write_json(output_root / "prepare_after_apply.json", result)
        return result
    profiles = _parse_csv(args.prepare_profiles, ["P0", "P1"])
    rows = []
    for profile in profiles:
        cmd = [
            sys.executable,
            "-m",
            "harness.orchestrator",
            "--config",
            str(args.config),
            "--suite",
            "10",
            "--mode",
            args.mode,
            "--prepare-only",
            "--run-id",
            f"{args.run_id}_prepare_{profile}",
            "--output-dir",
            str(output_root / "prepare_after_apply" / profile),
            "--profile",
            profile,
            "--arch",
            args.prepare_arch,
        ]
        if args.force_prepare:
            cmd.append("--force-prepare")
        if args.skip_tier0_prepare:
            cmd.append("--skip-tier0-prepare")
        if args.include_ue_build:
            cmd.append("--include-ue-build")
        if args.include_ue_extract:
            cmd.append("--include-ue-extract")
        log_path = output_root / "prepare_after_apply" / f"{profile}.log"
        proc = _run_logged(cmd, log_path)
        rows.append({"profile": profile, "command": cmd, "returncode": proc.returncode, "log_path": str(log_path)})
    result = {"skipped": False, "rows": rows}
    write_json(output_root / "prepare_after_apply.json", result)
    return result


def _default_variant_filter_for_target(target: str) -> str:
    if target == "suite10-cpp":
        return "tv2-tier0"
    if target == "suite10-ue":
        return "ue-local"
    return ""


def _run_post_apply_regressions(args: argparse.Namespace, output_root: Path, apply_result: dict) -> dict:
    applied_cases = _successful_applied_cases(apply_result)
    if not args.post_apply_regression:
        result = {"skipped": True, "reason": "post_apply_regression disabled", "rows": []}
        write_json(output_root / "post_apply_regression.json", result)
        return result
    if not applied_cases:
        result = {"skipped": True, "reason": "no approved applied cases", "rows": []}
        write_json(output_root / "post_apply_regression.json", result)
        return result
    rows = []
    for case in applied_cases:
        case_id = case["case_id"]
        target = case["target"]
        variant_filter = args.post_apply_variant_filter or _default_variant_filter_for_target(target)
        out_dir = output_root / "post_apply_regression" / _safe_label(case_id)
        cmd = [
            sys.executable,
            "-m",
            "harness.orchestrator",
            "--config",
            str(args.config),
            "--suite",
            "10",
            "--mode",
            args.mode,
            "--run-id",
            f"{args.run_id}_post_apply_{_safe_label(case_id)}",
            "--output-dir",
            str(out_dir),
            "--case-filter",
            case_id,
            "--case-scope",
            args.case_scope,
            "--include-proposed-regression",
            "--no-cache",
        ]
        if variant_filter:
            cmd.extend(["--variant-filter", variant_filter])
        proc = _run_logged(cmd, output_root / "post_apply_regression" / f"{_safe_label(case_id)}.log")
        report = _read_json(out_dir / "failure_report_v2.json", [])
        rows.append(
            {
                "case_id": case_id,
                "target": target,
                "variant_filter": variant_filter,
                "command": cmd,
                "returncode": proc.returncode,
                "output_dir": str(out_dir),
                "report_path": str(out_dir / "failure_report_v2.json"),
                "metrics": _metrics(report if isinstance(report, list) else []),
            }
        )
    result = {"skipped": False, "rows": rows}
    write_json(output_root / "post_apply_regression.json", result)
    return result


def _post_apply_green(post_apply: dict) -> bool:
    rows = post_apply.get("rows") or []
    if not rows:
        return False
    for row in rows:
        metrics = row.get("metrics") or {}
        if row.get("returncode") not in {0, 1}:
            return False
        if any(metrics.get(key, 0) for key in ("fail", "error", "degraded", "false_positive")):
            return False
    return True


def _engine_focus(applied_cases: list[dict], args: argparse.Namespace) -> tuple[str | None, str | None, str | None]:
    if not args.engine_focus_applied_cases or len(applied_cases) != 1:
        return None, None, None
    case = applied_cases[0]
    return "10", case["case_id"], args.post_apply_variant_filter or _default_variant_filter_for_target(case["target"])


def _run_engine_dev_loop(
    args: argparse.Namespace,
    output_root: Path,
    *,
    suite_override: str | None = None,
    case_filter_override: str | None = None,
    variant_filter_override: str | None = None,
) -> dict:
    cmd = [
        sys.executable,
        "-m",
        "harness.engine_dev_loop",
        "--config",
        str(args.config),
        "--suite",
        suite_override or args.suite,
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
    case_filter = case_filter_override if case_filter_override is not None else args.case_filter
    variant_filter = variant_filter_override if variant_filter_override is not None else args.variant_filter
    if case_filter:
        cmd.extend(["--case-filter", case_filter])
    if variant_filter:
        cmd.extend(["--variant-filter", variant_filter])
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

    if args.proposal_root:
        proposal_dir = args.proposal_root
        state["phases"].append(
            {
                "name": "case_author",
                "skipped": True,
                "reason": "proposal_root supplied",
                "proposal_dir": str(proposal_dir),
                "proposal_manifest": str(proposal_dir / "proposal_manifest.json"),
            }
        )
        if not (proposal_dir / "proposal_manifest.json").is_file():
            state["status"] = "proposal_root_missing_manifest"
            write_json(state_path, state)
            return 3
    else:
        tasks = _write_case_author_tasks(args, config, Path(str(baseline["report_path"])), output_root / "case_author_tasks.json")
        state["phases"].append({"name": "case_author_tasks", **tasks})

        author = _run_case_author(args, config, output_root, Path(str(tasks["tasks_path"])))
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

    expected = _regenerate_expected(args, output_root, apply_result)
    state["phases"].append({"name": "expected_regeneration", **expected})
    if any(row.get("returncode") != 0 for row in expected.get("rows") or []):
        state["status"] = "expected_regeneration_failed"
        write_json(state_path, state)
        return 3

    prepare = _run_prepare_after_apply(args, output_root, apply_result)
    state["phases"].append({"name": "prepare_after_apply", **prepare})
    if any(row.get("returncode") != 0 for row in prepare.get("rows") or []):
        state["status"] = "prepare_after_apply_failed"
        write_json(state_path, state)
        return 3

    post_apply = _run_post_apply_regressions(args, output_root, apply_result)
    state["phases"].append({"name": "post_apply_regression", **post_apply})
    if any(row.get("returncode") not in {0, 1} for row in post_apply.get("rows") or []):
        state["status"] = "post_apply_regression_failed"
        write_json(state_path, state)
        return 3

    if args.run_engine_dev_loop:
        applied_cases = _successful_applied_cases(apply_result)
        suite_override, case_filter_override, variant_filter_override = _engine_focus(applied_cases, args)
        if args.engine_skip_if_post_apply_green and post_apply.get("skipped") is False and _post_apply_green(post_apply):
            engine = {
                "skipped": True,
                "reason": "post_apply_regression_green",
                "focused_case": case_filter_override,
            }
        else:
            engine = _run_engine_dev_loop(
                args,
                output_root,
                suite_override=suite_override,
                case_filter_override=case_filter_override,
                variant_filter_override=variant_filter_override,
            )
        state["phases"].append({"name": "engine_dev_loop", **engine})
        if not engine.get("skipped") and engine["returncode"] not in {0, 3}:
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
    parser.add_argument("--proposal-root", type=Path, default=None, help="Use an existing proposal root and skip case_author.")

    parser.add_argument("--author-calls", type=int, default=4)
    parser.add_argument("--author-duration-hours", type=float, default=1.0)
    parser.add_argument("--author-chunk-calls", type=int, default=4)
    parser.add_argument("--author-chunk-tokens", type=int, default=100000)
    parser.add_argument("--author-executor", default="")
    parser.add_argument("--author-model", default="", help="Optional case_author model override when --codex-bin builds the executor.")
    parser.add_argument("--author-reasoning-effort", default="high", choices=["low", "medium", "high", "xhigh"])

    parser.add_argument("--apply-mode", default="dry-run", choices=["none", "dry-run", "approved"])
    parser.add_argument("--approval-key", default="")
    parser.add_argument("--allow-unapproved-case-apply", action="store_true")
    parser.add_argument("--regenerate-expected", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--prepare-after-apply", action="store_true")
    parser.add_argument("--prepare-profiles", default="P0,P1")
    parser.add_argument("--prepare-arch", default="all")
    parser.add_argument("--force-prepare", action="store_true")
    parser.add_argument("--skip-tier0-prepare", action="store_true")
    parser.add_argument("--include-ue-build", action="store_true")
    parser.add_argument("--include-ue-extract", action="store_true")
    parser.add_argument("--post-apply-regression", action="store_true")
    parser.add_argument("--post-apply-variant-filter", default="")

    parser.add_argument("--run-engine-dev-loop", action="store_true")
    parser.add_argument("--engine-focus-applied-cases", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--engine-skip-if-post-apply-green", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--engine-duration-hours", type=float, default=3.0)
    parser.add_argument("--engine-max-cycles", type=int, default=6)
    parser.add_argument("--engine-analysis-calls", type=int, default=12)
    parser.add_argument("--engine-analysis-chunk-calls", type=int, default=6)
    parser.add_argument("--engine-analysis-chunk-tokens", type=int, default=100000)
    parser.add_argument("--editor-reasoning-effort", default="high", choices=["low", "medium", "high", "xhigh"])
    parser.add_argument("--editor-timeout", type=float, default=7200.0)
    parser.add_argument("--codex-bin", default="", help="Codex executable path used by case_author provider and nested engine_dev_loop.")
    parser.add_argument("--operator-note-file", type=Path, default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    return run_frontier_loop(build_parser().parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
