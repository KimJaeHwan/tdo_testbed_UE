#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import shlex
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import HarnessConfig, ROOT
from .reporting import write_json


AGENT_RESULT_SCHEMA_VERSION = 1
DEFAULT_AGENT_TIERS = {
    "triage": "cheap",
    "coverage_planner": "cheap",
    "memory_synth": "cheap",
    "diagnostician": "strong",
    "adversary": "strong",
    "engine_fixer": "strong",
    "case_author": "strong",
}
TRIAGE_CATEGORIES = {
    "engine_defect",
    "harness_defect",
    "extractor_defect",
    "testcase_defect",
    "oracle_defect",
    "environment_defect",
    "known_frontier",
    "unsupported",
    "unknown",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _estimate_tokens(value: Any) -> int:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    return max(1, (len(text) + 3) // 4)


def validate_agent_output(task: dict, output: dict) -> dict:
    agent = str(task.get("agent") or "")
    errors: list[str] = []
    warnings: list[str] = []
    if output.get("agent") not in {agent, None}:
        errors.append(f"agent mismatch: task={agent}, output={output.get('agent')}")
    if output.get("schema_version") is None:
        errors.append("missing schema_version")

    if agent == "triage":
        category = output.get("category")
        if category not in TRIAGE_CATEGORIES:
            errors.append(f"invalid triage category: {category}")
        if not output.get("reason"):
            errors.append("triage output missing reason")
        if category not in {"known_frontier", "unsupported"} and not output.get("evidence_ref"):
            errors.append("triage non-frontier output missing evidence_ref")
    elif agent == "diagnostician":
        if not output.get("root_cause"):
            errors.append("diagnostician output missing root_cause")
        if not output.get("evidence_ref"):
            errors.append("diagnostician output missing evidence_ref")
    elif agent == "adversary":
        if output.get("refuted") is None:
            errors.append("adversary output missing refuted")
        if not output.get("lens"):
            errors.append("adversary output missing lens")
        if not output.get("evidence_ref"):
            errors.append("adversary output missing evidence_ref")
    elif agent == "coverage_planner":
        updates = output.get("capability_updates")
        if not isinstance(updates, list):
            errors.append("coverage_planner output missing capability_updates list")
        else:
            for index, update in enumerate(updates):
                if not update.get("case_class"):
                    errors.append(f"capability_updates[{index}] missing case_class")
                if not update.get("status"):
                    errors.append(f"capability_updates[{index}] missing status")
                if not update.get("evidence_ref"):
                    errors.append(f"capability_updates[{index}] missing evidence_ref")
    elif agent == "case_author":
        for index, proposed in enumerate(output.get("proposed_cases") or []):
            if not proposed.get("oracle_basis"):
                errors.append(f"proposed_cases[{index}] missing oracle_basis")
            independent = proposed.get("independent_check") or proposed.get("independent_validation")
            if not independent:
                errors.append(f"proposed_cases[{index}] missing independent validation")
    elif agent == "engine_fixer":
        if not output.get("summary"):
            errors.append("engine_fixer output missing summary")
        if not output.get("selftest"):
            errors.append("engine_fixer output missing selftest")
        changed = output.get("files_changed") or []
        forbidden = [path for path in changed if "expected/" in str(path) or str(path).endswith(".expected.json")]
        if forbidden:
            errors.append(f"engine_fixer attempted oracle changes: {forbidden}")
    elif agent == "memory_synth":
        if not output.get("updated"):
            errors.append("memory_synth output missing updated list")
    else:
        errors.append(f"unknown agent: {agent}")

    if task.get("requires_evidence") and not _has_any_evidence(output):
        warnings.append("no generic evidence field found; role-specific validation may still reject")

    return {
        "schema_version": AGENT_RESULT_SCHEMA_VERSION,
        "agent": agent,
        "accepted": not errors,
        "errors": errors,
        "warnings": warnings,
        "validated_at": _now(),
    }


def _has_any_evidence(output: Any) -> bool:
    if isinstance(output, dict):
        for key, value in output.items():
            if key in {"evidence_ref", "evidence"} and value:
                return True
            if _has_any_evidence(value):
                return True
    if isinstance(output, list):
        return any(_has_any_evidence(item) for item in output)
    return False


def run_tasks(args: argparse.Namespace) -> int:
    tasks = _read_json(args.tasks)
    if not isinstance(tasks, list):
        print("tasks file must contain a list")
        return 2
    config = HarnessConfig.load(args.config if args.config.exists() else None)
    output_dir = args.output_dir or args.tasks.parent / "agent_outputs"
    output_dir.mkdir(parents=True, exist_ok=True)
    results = []
    max_calls = int(args.max_calls if args.max_calls is not None else config.value("budgets", "per_run_max_calls", 0) or 0)
    max_tokens = int(args.max_tokens if args.max_tokens is not None else config.value("budgets", "per_run_max_tokens", 0) or 0)
    used_calls = 0
    used_tokens = 0
    for index, task in enumerate(tasks):
        agent = task.get("agent") or "unknown"
        prefix = output_dir / f"{index:03d}_{agent}"
        request_path = prefix.with_suffix(".request.json")
        write_json(request_path, task)
        tier, executor_text, model_name = _resolve_executor(args, config, task)
        estimated_input_tokens = _estimate_tokens(task)
        if args.dry_run:
            results.append(
                {
                    "task_index": index,
                    "agent": agent,
                    "tier": tier,
                    "model": model_name,
                    "request_path": str(request_path),
                    "output_path": None,
                    "budget": {
                        "estimated_input_tokens": estimated_input_tokens,
                        "estimated_total_tokens": estimated_input_tokens,
                        "max_calls": max_calls,
                        "max_tokens": max_tokens,
                    },
                    "validation": {"accepted": False, "warnings": ["dry_run"]},
                }
            )
            continue
        if not executor_text:
            print(f"error: no executor configured for agent={agent} tier={tier}")
            return 2
        if max_calls and used_calls + 1 > max_calls:
            print(f"error: agent call budget exceeded before task {index}: max_calls={max_calls}")
            return 3
        if max_tokens and used_tokens + estimated_input_tokens > max_tokens:
            print(f"error: agent token budget exceeded before task {index}: max_tokens={max_tokens}")
            return 3
        executor = shlex.split(executor_text)
        proc = subprocess.run(
            executor,
            input=json.dumps(task, ensure_ascii=False),
            text=True,
            capture_output=True,
            check=False,
        )
        used_calls += 1
        stdout_path = prefix.with_suffix(".stdout.txt")
        stderr_path = prefix.with_suffix(".stderr.txt")
        stdout_path.write_text(proc.stdout or "", encoding="utf-8")
        stderr_path.write_text(proc.stderr or "", encoding="utf-8")
        try:
            output = json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            output = {"agent": agent, "schema_version": None, "parse_error": str(exc), "raw_stdout_path": str(stdout_path)}
        output_path = prefix.with_suffix(".output.json")
        write_json(output_path, output)
        validation = validate_agent_output(task, output)
        estimated_output_tokens = _estimate_tokens(output)
        used_tokens += estimated_input_tokens + estimated_output_tokens
        if max_tokens and used_tokens > max_tokens:
            validation["accepted"] = False
            validation.setdefault("errors", []).append(f"agent token budget exceeded: used={used_tokens}, max={max_tokens}")
        results.append(
            {
                "task_index": index,
                "agent": agent,
                "tier": tier,
                "model": model_name,
                "request_path": str(request_path),
                "output_path": str(output_path),
                "stdout_path": str(stdout_path),
                "stderr_path": str(stderr_path),
                "returncode": proc.returncode,
                "budget": {
                    "estimated_input_tokens": estimated_input_tokens,
                    "estimated_output_tokens": estimated_output_tokens,
                    "estimated_total_tokens": estimated_input_tokens + estimated_output_tokens,
                    "used_calls": used_calls,
                    "used_tokens": used_tokens,
                    "max_calls": max_calls,
                    "max_tokens": max_tokens,
                },
                "validation": validation,
            }
        )
    write_json(output_dir / "agent_results.json", results)
    accepted = sum(1 for row in results if (row.get("validation") or {}).get("accepted"))
    print(f"agent tasks: {len(results)} result(s), accepted={accepted}, output={output_dir}")
    return 0 if all((row.get("validation") or {}).get("accepted") for row in results) else 1


def _resolve_executor(args: argparse.Namespace, config: HarnessConfig, task: dict) -> tuple[str, str, str]:
    agent = str(task.get("agent") or "")
    agent_tiers = config.value("models", "agent_tiers", {}) or {}
    tier = str(agent_tiers.get(agent) or DEFAULT_AGENT_TIERS.get(agent) or "strong")
    model_name = str(config.value("models", tier, "") or "")
    if args.executor:
        return tier, args.executor, model_name
    commands = config.value("models", "commands", {}) or {}
    executor = str(commands.get(tier) or "")
    if not executor and tier == "cheap":
        executor = str(commands.get("strong") or "")
    return tier, executor, model_name


def doctor(args: argparse.Namespace) -> int:
    config = HarnessConfig.load(args.config if args.config.exists() else None)
    commands = config.value("models", "commands", {}) or {}
    agent_tiers = config.value("models", "agent_tiers", {}) or {}
    merged_agent_tiers = dict(DEFAULT_AGENT_TIERS)
    merged_agent_tiers.update({str(key): str(value) for key, value in agent_tiers.items()})
    used_tiers = sorted(set(merged_agent_tiers.values()) | {"cheap", "strong"})
    command_rows = [_inspect_command(tier, str(commands.get(tier) or "")) for tier in used_tiers]
    warnings = []
    errors = []
    for row in command_rows:
        if row["status"] == "missing":
            message = f"missing command for tier={row['tier']}"
            (errors if args.strict else warnings).append(message)
        elif row["status"] == "not_found":
            errors.append(f"command not found for tier={row['tier']}: {row['executable']}")
    report = {
        "schema_version": AGENT_RESULT_SCHEMA_VERSION,
        "config": str(args.config) if args.config.exists() else "<defaults>",
        "agent_tiers": merged_agent_tiers,
        "commands": command_rows,
        "models": {
            "cheap": config.value("models", "cheap", ""),
            "strong": config.value("models", "strong", ""),
            "adversary_panel": config.value("models", "adversary_panel", []),
        },
        "budgets": {
            "per_run_max_calls": config.value("budgets", "per_run_max_calls", 0),
            "per_run_max_tokens": config.value("budgets", "per_run_max_tokens", 0),
        },
        "warnings": warnings,
        "errors": errors,
    }
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"config: {report['config']}")
        print(f"budgets: calls={report['budgets']['per_run_max_calls']} tokens={report['budgets']['per_run_max_tokens']}")
        for row in command_rows:
            print(f"tier {row['tier']}: {row['status']} {row['command'] or '<empty>'}")
        if warnings:
            print("warnings:")
            for warning in warnings:
                print(f"  - {warning}")
        if errors:
            print("errors:")
            for error in errors:
                print(f"  - {error}")
    return 0 if not errors else 1


def _inspect_command(tier: str, command: str) -> dict:
    if not command:
        return {"tier": tier, "command": command, "executable": "", "resolved": "", "status": "missing"}
    argv = shlex.split(command)
    if not argv:
        return {"tier": tier, "command": command, "executable": "", "resolved": "", "status": "missing"}
    executable = argv[0]
    resolved = shutil.which(executable)
    if resolved is None and Path(executable).is_file():
        resolved = str(Path(executable))
    status = "ok" if resolved else "not_found"
    return {"tier": tier, "command": command, "executable": executable, "resolved": resolved or "", "status": status}


def validate_outputs(args: argparse.Namespace) -> int:
    tasks = _read_json(args.tasks)
    if not isinstance(tasks, list):
        print("tasks file must contain a list")
        return 2
    output_dir = args.outputs
    results = []
    for index, task in enumerate(tasks):
        agent = task.get("agent") or "unknown"
        output_path = output_dir / f"{index:03d}_{agent}.output.json"
        if not output_path.is_file():
            results.append(
                {
                    "task_index": index,
                    "agent": agent,
                    "output_path": str(output_path),
                    "validation": {"accepted": False, "errors": ["missing output"]},
                }
            )
            continue
        output = _read_json(output_path)
        results.append(
            {
                "task_index": index,
                "agent": agent,
                "output_path": str(output_path),
                "validation": validate_agent_output(task, output),
            }
        )
    write_json(output_dir / "agent_results.json", results)
    accepted = sum(1 for row in results if (row.get("validation") or {}).get("accepted"))
    print(f"validated {len(results)} output(s), accepted={accepted}")
    return 0 if all((row.get("validation") or {}).get("accepted") for row in results) else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run or validate harness agent task JSON envelopes.")
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="Run tasks with an external JSON-in/JSON-out executor.")
    run_p.add_argument("--config", type=Path, default=ROOT / "harness" / "config.yaml")
    run_p.add_argument("--tasks", type=Path, required=True)
    run_p.add_argument("--output-dir", type=Path, default=None)
    run_p.add_argument("--executor", default="", help="Override command that reads one task JSON on stdin and prints output JSON.")
    run_p.add_argument("--max-calls", type=int, default=None, help="Override per-run agent call budget. 0 means unlimited.")
    run_p.add_argument("--max-tokens", type=int, default=None, help="Override approximate token budget. 0 means unlimited.")
    run_p.add_argument("--dry-run", action="store_true", help="Write request JSON files only.")
    run_p.set_defaults(func=run_tasks)

    doctor_p = sub.add_parser("doctor", help="Validate configured agent tiers, commands, and budgets.")
    doctor_p.add_argument("--config", type=Path, default=ROOT / "harness" / "config.yaml")
    doctor_p.add_argument("--strict", action="store_true", help="Treat missing tier commands as errors.")
    doctor_p.add_argument("--json", action="store_true", help="Print machine-readable diagnostics.")
    doctor_p.set_defaults(func=doctor)

    val_p = sub.add_parser("validate", help="Validate existing agent output JSON files.")
    val_p.add_argument("--tasks", type=Path, required=True)
    val_p.add_argument("--outputs", type=Path, required=True)
    val_p.set_defaults(func=validate_outputs)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
