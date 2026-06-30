#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import HarnessConfig, ROOT
from .gates import objective_vector, regression_failures
from .reporting import write_json


DEV_LOOP_SCHEMA_VERSION = 1
REASONING_EFFORTS = {"low", "medium", "high", "xhigh"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path, default: Any = None) -> Any:
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _safe_name(text: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "_" for ch in text)[:180]


def _run_logged(
    cmd: list[str],
    log_path: Path,
    *,
    cwd: Path,
    input_text: str | None = None,
    dry_run: bool = False,
    timeout: float | None = None,
) -> subprocess.CompletedProcess[str]:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    header = {
        "cmd": cmd,
        "cwd": str(cwd),
        "dry_run": dry_run,
        "started_at": _now(),
    }
    if dry_run:
        log_path.write_text(json.dumps(header, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 0, "", "")
    proc = subprocess.run(
        cmd,
        cwd=cwd,
        input=input_text,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        timeout=timeout,
    )
    log_path.write_text(
        json.dumps(header, ensure_ascii=False, indent=2)
        + "\n\n"
        + (proc.stdout or "")
        + f"\n\n[returncode] {proc.returncode}\n",
        encoding="utf-8",
    )
    return proc


def _git(args: list[str], repo: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(repo), *args], text=True, capture_output=True, check=False)


def _git_text(args: list[str], repo: Path) -> str:
    return (_git(args, repo).stdout or "").strip()


def _git_dirty(repo: Path) -> bool:
    return bool(_git_text(["status", "--short"], repo))


def _engine_python(config: HarnessConfig, engine_root: Path) -> str:
    configured = str(config.value("tools", "python", "") or "").strip()
    if configured and Path(configured).expanduser().exists():
        return str(Path(configured).expanduser())
    venv = engine_root / ".venv" / ("Scripts/python.exe" if sys.platform.startswith("win") else "bin/python")
    if venv.exists():
        return str(venv)
    return sys.executable


def _model_from_config(config: HarnessConfig, cli_model: str) -> str:
    if cli_model:
        return cli_model
    strong = str((config.value("models", "strong", "") or "")).strip()
    return strong.split(":", 1)[1] if strong.startswith("codex:") else strong


def _append_reasoning_effort(cmd: list[str], effort: str) -> None:
    if not effort:
        return
    if effort not in REASONING_EFFORTS:
        raise ValueError(f"unsupported reasoning effort: {effort}")
    cmd.extend(["-c", f'model_reasoning_effort="{effort}"'])


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
    counts["objective_vector"] = list(objective_vector(report))
    return counts


def _fully_green(report: list[dict]) -> bool:
    m = _metrics(report)
    return m["total"] > 0 and m["fail"] == 0 and m["error"] == 0 and m["degraded"] == 0 and m["false_positive"] == 0


def _compare_reports(before: list[dict], after: list[dict]) -> dict:
    before_metrics = _metrics(before)
    after_metrics = _metrics(after)
    regressions = regression_failures(before, after)
    before_vector = tuple(before_metrics["objective_vector"])
    after_vector = tuple(after_metrics["objective_vector"])
    no_worse = (
        not regressions
        and after_metrics["error"] <= before_metrics["error"]
        and after_metrics["false_positive"] <= before_metrics["false_positive"]
        and after_metrics["pass"] >= before_metrics["pass"]
    )
    return {
        "before": before_metrics,
        "after": after_metrics,
        "objective_improved": after_vector > before_vector,
        "no_worse": no_worse,
        "regressions": regressions,
        "fp_added": _false_positive_added(before, after),
        "fully_green": _fully_green(after),
    }


def _false_positive_added(before: list[dict], after: list[dict]) -> list[dict]:
    before_by_key = {
        (str(row.get("variant_label")), str(row.get("case"))): row
        for row in before
    }
    added: list[dict] = []
    for row in after:
        key = (str(row.get("variant_label")), str(row.get("case")))
        before_row = before_by_key.get(key) or {}
        before_fp = set(before_row.get("forbidden_found") or [])
        after_fp = set(row.get("forbidden_found") or [])
        new_fp = sorted(after_fp - before_fp)
        if new_fp:
            added.append(
                {
                    "variant": key[0],
                    "case": key[1],
                    "before": sorted(before_fp),
                    "after": sorted(after_fp),
                    "added": new_fp,
                }
            )
    return added


def _repair_context_from_cycle(cycle: dict) -> dict | None:
    comparison = cycle.get("comparison") or {}
    if comparison.get("no_worse") is not False:
        return None
    pre = cycle.get("pre_regression") or {}
    post = cycle.get("post_regression") or {}
    return {
        "source_cycle": cycle.get("cycle"),
        "reason": "previous cycle introduced regression or false positive",
        "baseline_report": pre.get("report_path"),
        "bad_report": post.get("report_path"),
        "regressions": comparison.get("regressions") or [],
        "fp_added": comparison.get("fp_added") or [],
        "before_metrics": comparison.get("before") or {},
        "after_metrics": comparison.get("after") or {},
    }


def _pending_repair_context(cycles: list[dict]) -> dict | None:
    if not cycles:
        return None
    return _repair_context_from_cycle(cycles[-1])


def _run_regression(args: argparse.Namespace, config: HarnessConfig, cycle_dir: Path, phase: str, cycle_index: int) -> dict:
    run_id = f"{args.run_id}_c{cycle_index:02d}_{phase}"
    output_dir = cycle_dir / f"{phase}_regression"
    cmd = [
        sys.executable,
        "-m",
        "harness.orchestrator",
        "--config",
        str(args.config),
        "--suite",
        args.suite,
        "--run-id",
        run_id,
        "--output-dir",
        str(output_dir),
        "--case-scope",
        args.case_scope,
    ]
    if args.mode:
        cmd.extend(["--mode", args.mode])
    if args.variant_filter:
        cmd.extend(["--variant-filter", args.variant_filter])
    if args.case_filter:
        cmd.extend(["--case-filter", args.case_filter])
    if not args.use_cache:
        cmd.append("--no-cache")
    if args.prepare_artifacts:
        cmd.append("--prepare-artifacts")
    if args.prepare_dry_run:
        cmd.append("--prepare-dry-run")
    if args.force_prepare:
        cmd.append("--force-prepare")
    if args.profile:
        cmd.extend(["--profile", args.profile])
    if args.arch:
        cmd.extend(["--arch", args.arch])
    if args.skip_tier0_prepare:
        cmd.append("--skip-tier0-prepare")
    if args.include_ue_build:
        cmd.append("--include-ue-build")
    if args.include_ue_extract:
        cmd.append("--include-ue-extract")

    print(f"[engine-dev-loop] regression {phase}: {run_id}")
    proc = _run_logged(cmd, cycle_dir / f"{phase}_regression.log", cwd=ROOT, dry_run=args.dry_run)
    report = _read_json(output_dir / "failure_report_v2.json", [])
    gate = _read_json(output_dir / "gate.json", {})
    summary = _read_json(output_dir / "summary.json", {})
    return {
        "run_id": run_id,
        "output_dir": str(output_dir),
        "command": cmd,
        "returncode": proc.returncode,
        "report_path": str(output_dir / "failure_report_v2.json"),
        "gate_path": str(output_dir / "gate.json"),
        "summary_path": str(output_dir / "summary.json"),
        "tasks_path": str(output_dir / "agent_tasks.json"),
        "metrics": _metrics(report if isinstance(report, list) else []),
        "gate": gate,
        "summary": summary,
    }


def _run_analysis(args: argparse.Namespace, cycle_dir: Path, regression: dict) -> dict:
    tasks_path = Path(str(regression["tasks_path"]))
    tasks = _read_json(tasks_path, [])
    if not isinstance(tasks, list) or not tasks or args.analysis_calls <= 0:
        return {"skipped": True, "reason": "no tasks or analysis_calls <= 0", "tasks": len(tasks) if isinstance(tasks, list) else 0}

    output_dir = cycle_dir / "agent_analysis"
    proposal_dir = cycle_dir / "agent_proposals"
    cmd = [
        sys.executable,
        "-m",
        "harness.agent_loop",
        "--config",
        str(args.config),
        "--tasks",
        str(tasks_path),
        "--output-dir",
        str(output_dir),
        "--duration-hours",
        str(args.analysis_duration_hours),
        "--chunk-calls",
        str(args.analysis_chunk_calls),
        "--chunk-tokens",
        str(args.analysis_chunk_tokens),
        "--max-total-calls",
        str(args.analysis_calls),
        "--materialize-proposals",
        "--proposal-output-dir",
        str(proposal_dir),
        "--include-coverage",
        "--scaffold-work-items",
        "--stop-on-no-progress",
    ]
    if args.analysis_executor:
        cmd.extend(["--executor", args.analysis_executor])

    print(f"[engine-dev-loop] analysis: calls={args.analysis_calls} tasks={len(tasks)}")
    proc = _run_logged(cmd, cycle_dir / "agent_analysis.log", cwd=ROOT, dry_run=args.dry_run)
    return {
        "skipped": False,
        "command": cmd,
        "returncode": proc.returncode,
        "output_dir": str(output_dir),
        "proposal_dir": str(proposal_dir),
        "agent_results": str(output_dir / "agent_results.json"),
        "proposal_manifest": str(proposal_dir / "proposal_manifest.json"),
    }


def _failure_excerpt(report_path: Path, limit: int) -> list[dict]:
    rows = _read_json(report_path, [])
    if not isinstance(rows, list):
        return []
    failures = [row for row in rows if row.get("verdict") != "PASS" or row.get("forbidden_found")]
    excerpt = []
    for row in failures[:limit]:
        excerpt.append(
            {
                "suite": row.get("suite"),
                "variant": row.get("variant_label"),
                "case": row.get("case"),
                "function": row.get("function"),
                "verdict": row.get("verdict"),
                "missing": row.get("missing", []),
                "forbidden_found": row.get("forbidden_found", []),
                "cut": row.get("cut", [])[:12],
                "artifacts": row.get("artifacts", {}),
                "pcode_scope": row.get("pcode_scope", {}),
            }
        )
    return excerpt


def _extra_editor_instructions(args: argparse.Namespace) -> list[str]:
    lines: list[str] = []
    inline = str(getattr(args, "editor_extra_instructions", "") or "").strip()
    file_path = getattr(args, "editor_extra_instructions_file", None)
    cached_file_text = str(getattr(args, "_editor_extra_instructions_file_text", "") or "").strip()
    if inline:
        lines.extend(["", "Operator extra instructions:", inline])
    if file_path:
        path = Path(file_path).expanduser()
        if path.is_file():
            lines.extend(["", f"Operator extra instructions file: {path}", path.read_text(encoding="utf-8").strip()])
        elif cached_file_text:
            lines.extend(["", f"Operator extra instructions file: {path}", cached_file_text])
        else:
            lines.extend(["", f"Operator extra instructions file missing: {path}"])
    return lines


def _editor_prompt(
    args: argparse.Namespace,
    engine_root: Path,
    cycle_index: int,
    pre: dict,
    analysis: dict,
    repair_context: dict | None = None,
) -> str:
    report_path = Path(str(pre["report_path"]))
    gate_path = Path(str(pre["gate_path"]))
    summary_path = Path(str(pre["summary_path"]))
    proposal_manifest = str(analysis.get("proposal_manifest") or "")
    proposal_note = proposal_manifest if proposal_manifest and Path(proposal_manifest).is_file() else "not generated or not available"
    excerpt = _failure_excerpt(report_path, args.prompt_max_cases)
    return "\n".join(
        [
            "You are Codex working inside the lowpcode_data_origin repository.",
            "",
            "Objective:",
            "- Improve the Low-PCode data origin engine, then leave the repository ready for the harness to rerun 09/10 regression.",
            "- Do not merely patch for one named test; implement behavior that generalizes to fused and more complex cases.",
            "",
            "Hard constraints:",
            "- Edit only the lowpcode_data_origin engine repository unless explicitly necessary for documentation inside that repo.",
            "- Do not edit tdo_testbed, tdo_testbed_UE expected files, manifests, generated low-pcode samples, or oracle data.",
            "- Preserve the design philosophy: Low P-code is source of truth, no arg/no ret in core semantics, convention-free observed storage transitions, architecture-aware storage.",
            "- Ghidra/decompiler metadata may be used only as optional facts or hints; do not let ABI/signature/parameter names override observed dataflow.",
            "- Avoid broad over-approximation that creates false positives.",
            "- Keep changes focused. Update dev_docs/progress_log.md or the relevant phase doc if the change is meaningful.",
            "",
            "Useful design files to read before editing:",
            "- dev_docs/v8_v1_design.md",
            "- dev_docs/v8_v1_phase_plan.md",
            "- dev_docs/phase_06_external_summary.md",
            "",
            f"Cycle: {cycle_index}",
            f"Engine root: {engine_root}",
            f"Regression report: {report_path}",
            f"Gate: {gate_path}",
            f"Summary: {summary_path}",
            f"Agent proposal manifest: {proposal_note}",
            "",
            "Current metrics:",
            json.dumps(pre.get("metrics") or {}, ensure_ascii=False, indent=2, sort_keys=True),
            "",
            "Failure excerpt:",
            json.dumps(excerpt, ensure_ascii=False, indent=2, sort_keys=True),
            "",
            "Active repair context:",
            json.dumps(repair_context or {}, ensure_ascii=False, indent=2, sort_keys=True),
            "",
            "After editing, run the most relevant lightweight checks you can from this repository.",
            "The outer harness will run the full 09/10 regression with cache disabled after you return.",
            *_extra_editor_instructions(args),
        ]
    )


def _run_editor(
    args: argparse.Namespace,
    config: HarnessConfig,
    cycle_dir: Path,
    cycle_index: int,
    pre: dict,
    analysis: dict,
    repair_context: dict | None = None,
) -> dict:
    engine_root = config.path("repos", "engine_11")
    prompt = _editor_prompt(args, engine_root, cycle_index, pre, analysis, repair_context)
    prompt_path = cycle_dir / "codex_engine_fix_prompt.md"
    prompt_path.write_text(prompt, encoding="utf-8")

    codex_bin = shutil.which(args.codex_bin)
    if not codex_bin:
        return {"returncode": 2, "error": f"codex executable not found: {args.codex_bin}", "prompt_path": str(prompt_path)}

    last_message = cycle_dir / "codex_engine_fix_last_message.txt"
    cmd = [
        codex_bin,
        "exec",
        "--ephemeral",
        "--sandbox",
        args.editor_sandbox,
        "--cd",
        str(engine_root),
        "--output-last-message",
        str(last_message),
    ]
    model = _model_from_config(config, args.editor_model)
    if model:
        cmd.extend(["--model", model])
    try:
        _append_reasoning_effort(cmd, args.editor_reasoning_effort)
    except ValueError as exc:
        return {"returncode": 2, "error": str(exc), "prompt_path": str(prompt_path), "command": cmd}
    if args.editor_profile:
        cmd.extend(["--profile", args.editor_profile])
    if args.editor_oss:
        cmd.append("--oss")
    if args.editor_local_provider:
        cmd.extend(["--local-provider", args.editor_local_provider])
    cmd.append("-")

    print(f"[engine-dev-loop] editor: {model or 'codex-default'} sandbox={args.editor_sandbox}")
    proc = _run_logged(
        cmd,
        cycle_dir / "codex_engine_fix.log",
        cwd=engine_root,
        input_text=prompt,
        dry_run=args.dry_run or args.editor_dry_run,
        timeout=args.editor_timeout,
    )
    return {
        "command": cmd,
        "returncode": proc.returncode,
        "prompt_path": str(prompt_path),
        "log_path": str(cycle_dir / "codex_engine_fix.log"),
        "last_message_path": str(last_message),
    }


def _run_compileall(args: argparse.Namespace, config: HarnessConfig, cycle_dir: Path) -> dict:
    if args.skip_compileall:
        return {"skipped": True}
    engine_root = config.path("repos", "engine_11")
    py = _engine_python(config, engine_root)
    targets = ["analysis", "core", "frontend", "query", "report", "tools"]
    cmd = [py, "-m", "compileall", "-q", *targets]
    print("[engine-dev-loop] compileall")
    proc = _run_logged(cmd, cycle_dir / "compileall.log", cwd=engine_root, dry_run=args.dry_run)
    return {"skipped": False, "command": cmd, "returncode": proc.returncode, "log_path": str(cycle_dir / "compileall.log")}


def _write_engine_diff(config: HarnessConfig, cycle_dir: Path) -> dict:
    engine_root = config.path("repos", "engine_11")
    diff_path = cycle_dir / "engine.diff"
    status_path = cycle_dir / "engine_status.txt"
    diff = _git_text(["diff", "--"], engine_root)
    status = _git_text(["status", "--short"], engine_root)
    diff_path.write_text(diff + ("\n" if diff else ""), encoding="utf-8")
    status_path.write_text(status + ("\n" if status else ""), encoding="utf-8")
    changed = [line for line in status.splitlines() if line.strip()]
    return {
        "diff_path": str(diff_path),
        "status_path": str(status_path),
        "changed": changed,
        "changed_count": len(changed),
    }


def _write_state(path: Path, args: argparse.Namespace, status: str, cycles: list[dict], extra: dict | None = None) -> None:
    write_json(
        path,
        {
            "schema_version": DEV_LOOP_SCHEMA_VERSION,
            "status": status,
            "updated_at": _now(),
            "run_id": args.run_id,
            "suite": args.suite,
            "mode": args.mode,
            "case_scope": args.case_scope,
            "editor_extra_instructions_file": str(args.editor_extra_instructions_file) if args.editor_extra_instructions_file else "",
            "has_editor_extra_instructions": bool(args.editor_extra_instructions),
            "repair_on_regression": bool(args.repair_on_regression),
            "cycles": cycles,
            **(extra or {}),
        },
    )


def run_dev_loop(args: argparse.Namespace) -> int:
    config = HarnessConfig.load(args.config if args.config.exists() else None)
    engine_root = config.path("repos", "engine_11")
    output_root = args.output_dir or (config.path("output", "root") / args.run_id)
    state_path = output_root / "engine_dev_loop_state.json"
    if args.editor_extra_instructions_file:
        note_path = args.editor_extra_instructions_file.expanduser()
        args._editor_extra_instructions_file_text = note_path.read_text(encoding="utf-8") if note_path.is_file() else ""

    if output_root.exists() and args.clean_output:
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    if _git_dirty(engine_root) and not (args.allow_dirty_engine or args.resume_existing):
        print(
            f"error: engine repo has existing changes; commit/stash them or pass --allow-dirty-engine: {engine_root}",
            file=sys.stderr,
        )
        print(_git_text(["status", "--short"], engine_root), file=sys.stderr)
        return 2

    started = time.monotonic()
    deadline = started + max(0.0, args.duration_hours * 3600.0)
    cycles: list[dict] = []
    existing = _read_json(state_path, {})
    if args.resume_existing and isinstance(existing, dict):
        cycles = list(existing.get("cycles") or [])
    repair_context = _pending_repair_context(cycles) if args.repair_on_regression else None

    status = "max_cycles_exhausted"
    for cycle_index in range(len(cycles) + 1, args.max_cycles + 1):
        if time.monotonic() >= deadline:
            status = "time_budget_exhausted"
            break
        cycle_dir = output_root / f"cycle_{cycle_index:02d}"
        cycle_dir.mkdir(parents=True, exist_ok=True)
        cycle: dict[str, Any] = {"cycle": cycle_index, "started_at": _now(), "cycle_dir": str(cycle_dir)}

        pre = _run_regression(args, config, cycle_dir, "pre", cycle_index)
        cycle["pre_regression"] = pre
        if args.dry_run:
            status = "dry_run_complete"
            cycles.append(cycle)
            _write_state(state_path, args, status, cycles)
            break
        if not Path(str(pre["report_path"])).is_file():
            status = "pre_regression_failed"
            cycles.append(cycle)
            _write_state(state_path, args, status, cycles)
            break
        report = _read_json(Path(str(pre["report_path"])), [])
        if isinstance(report, list) and _fully_green(report):
            status = "fully_green_before_edit"
            cycles.append(cycle)
            _write_state(state_path, args, status, cycles)
            break

        analysis = _run_analysis(args, cycle_dir, pre)
        cycle["analysis"] = analysis
        if analysis.get("returncode") not in (None, 0, 3):
            status = "analysis_failed"
            cycles.append(cycle)
            _write_state(state_path, args, status, cycles)
            break

        if args.no_edit:
            status = "analysis_only_complete"
            cycles.append(cycle)
            _write_state(state_path, args, status, cycles)
            break

        editor = _run_editor(args, config, cycle_dir, cycle_index, pre, analysis, repair_context)
        cycle["editor"] = editor
        if editor.get("returncode") != 0:
            status = "editor_failed"
            cycle["engine_diff"] = _write_engine_diff(config, cycle_dir)
            cycles.append(cycle)
            _write_state(state_path, args, status, cycles)
            break

        cycle["engine_diff"] = _write_engine_diff(config, cycle_dir)
        if cycle["engine_diff"]["changed_count"] == 0:
            status = "no_engine_changes"
            cycles.append(cycle)
            _write_state(state_path, args, status, cycles)
            break

        compile_result = _run_compileall(args, config, cycle_dir)
        cycle["compileall"] = compile_result
        if compile_result.get("returncode") not in (None, 0):
            status = "compileall_failed"
            cycles.append(cycle)
            _write_state(state_path, args, status, cycles)
            break

        post = _run_regression(args, config, cycle_dir, "post", cycle_index)
        cycle["post_regression"] = post
        before_report = _read_json(Path(str(pre["report_path"])), [])
        after_report = _read_json(Path(str(post["report_path"])), [])
        if isinstance(before_report, list) and isinstance(after_report, list):
            cycle["comparison"] = _compare_reports(before_report, after_report)
            if repair_context and repair_context.get("baseline_report"):
                repair_baseline = _read_json(Path(str(repair_context["baseline_report"])), [])
                if isinstance(repair_baseline, list):
                    cycle["repair_comparison"] = _compare_reports(repair_baseline, after_report)
        else:
            cycle["comparison"] = {"no_worse": False, "reason": "missing report"}

        cycles.append(cycle)
        _write_state(state_path, args, "running", cycles)

        comparison = cycle["comparison"]
        repair_comparison = cycle.get("repair_comparison")
        effective_no_worse = bool(comparison.get("no_worse"))
        if repair_comparison is not None:
            effective_no_worse = effective_no_worse and bool(repair_comparison.get("no_worse"))
        if effective_no_worse:
            repair_context = None
        if comparison.get("fully_green"):
            status = "fully_green_after_edit"
            break
        if args.stop_on_regression and not effective_no_worse:
            repair_context = _repair_context_from_cycle(cycle) or repair_context
            if args.repair_on_regression and cycle_index < args.max_cycles and time.monotonic() < deadline:
                status = "repair_cycle_pending"
                continue
            status = "regression_or_fp_worsened"
            break
        if args.stop_on_no_progress and not comparison.get("objective_improved"):
            status = "no_progress_after_edit"
            break
        status = "max_cycles_exhausted"

    _write_state(
        state_path,
        args,
        status,
        cycles,
        {"engine_root": str(engine_root), "output_root": str(output_root), "finished_at": _now()},
    )
    print(f"[engine-dev-loop] stopped: {status}")
    print(f"[engine-dev-loop] state: {state_path}")
    return 0 if status in {"fully_green_before_edit", "fully_green_after_edit", "dry_run_complete", "analysis_only_complete"} else 3


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run an edit-and-regress loop for lowpcode_data_origin using 09/10 harness evidence.")
    parser.add_argument("--config", type=Path, default=ROOT / "harness" / "config.yaml")
    parser.add_argument("--suite", default="09,10", help="Comma-separated suites, normally 09,10.")
    parser.add_argument("--mode", default="local-samples", choices=["release-artifacts", "local-samples"])
    parser.add_argument("--run-id", default="engine_dev_09_10")
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--clean-output", action="store_true", help="Delete this run output directory before starting.")
    parser.add_argument("--resume-existing", action="store_true")
    parser.add_argument("--duration-hours", type=float, default=4.5)
    parser.add_argument("--max-cycles", type=int, default=3)
    parser.add_argument("--case-scope", default="auto", choices=["auto", "always", "never"])
    parser.add_argument("--case-filter", default="")
    parser.add_argument("--variant-filter", default="")
    parser.add_argument("--use-cache", action="store_true", help="Allow regression cache reuse. Default is no-cache for dirty engine safety.")

    parser.add_argument("--prepare-artifacts", action="store_true")
    parser.add_argument("--prepare-dry-run", action="store_true")
    parser.add_argument("--force-prepare", action="store_true")
    parser.add_argument("--profile", default="P0", choices=["P0", "P1"])
    parser.add_argument("--arch", default="x64")
    parser.add_argument("--skip-tier0-prepare", action="store_true")
    parser.add_argument("--include-ue-build", action="store_true")
    parser.add_argument("--include-ue-extract", action="store_true")

    parser.add_argument("--analysis-calls", type=int, default=0, help="Optional agent-analysis calls before each edit cycle.")
    parser.add_argument("--analysis-duration-hours", type=float, default=0.5)
    parser.add_argument("--analysis-chunk-calls", type=int, default=5)
    parser.add_argument("--analysis-chunk-tokens", type=int, default=50000)
    parser.add_argument("--analysis-executor", default="")

    parser.add_argument("--codex-bin", default="codex")
    parser.add_argument("--editor-model", default="")
    parser.add_argument("--editor-reasoning-effort", default="", choices=["", *sorted(REASONING_EFFORTS)])
    parser.add_argument("--editor-profile", default="")
    parser.add_argument("--editor-sandbox", default="workspace-write", choices=["read-only", "workspace-write", "danger-full-access"])
    parser.add_argument("--editor-timeout", type=float, default=1800.0)
    parser.add_argument("--editor-oss", action="store_true")
    parser.add_argument("--editor-local-provider", default="")
    parser.add_argument("--editor-dry-run", action="store_true")
    parser.add_argument(
        "--editor-extra-instructions",
        default="",
        help="Additional one-off operator instructions appended to the Codex editor prompt.",
    )
    parser.add_argument(
        "--editor-extra-instructions-file",
        type=Path,
        default=None,
        help="Path to a markdown/text note appended to every Codex editor prompt.",
    )
    parser.add_argument("--prompt-max-cases", type=int, default=16)

    parser.add_argument("--allow-dirty-engine", action="store_true")
    parser.add_argument("--no-edit", action="store_true")
    parser.add_argument("--skip-compileall", action="store_true")
    parser.add_argument("--stop-on-regression", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument(
        "--repair-on-regression",
        action="store_true",
        help="Continue into the next cycle with regression/FP details in the editor prompt instead of stopping immediately.",
    )
    parser.add_argument("--stop-on-no-progress", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--dry-run", action="store_true", help="Write planned commands/prompts without executing them.")
    return parser


def main(argv: list[str] | None = None) -> int:
    return run_dev_loop(build_parser().parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
