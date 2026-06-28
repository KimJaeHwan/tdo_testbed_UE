#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shlex
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .reporting import write_json


AGENT_RESULT_SCHEMA_VERSION = 1
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
    output_dir = args.output_dir or args.tasks.parent / "agent_outputs"
    output_dir.mkdir(parents=True, exist_ok=True)
    results = []
    executor = shlex.split(args.executor) if args.executor else []
    for index, task in enumerate(tasks):
        agent = task.get("agent") or "unknown"
        prefix = output_dir / f"{index:03d}_{agent}"
        request_path = prefix.with_suffix(".request.json")
        write_json(request_path, task)
        if args.dry_run:
            results.append(
                {
                    "task_index": index,
                    "agent": agent,
                    "request_path": str(request_path),
                    "output_path": None,
                    "validation": {"accepted": False, "warnings": ["dry_run"]},
                }
            )
            continue
        if not executor:
            print("error: --executor is required unless --dry-run is used")
            return 2
        proc = subprocess.run(
            executor,
            input=json.dumps(task, ensure_ascii=False),
            text=True,
            capture_output=True,
            check=False,
        )
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
        results.append(
            {
                "task_index": index,
                "agent": agent,
                "request_path": str(request_path),
                "output_path": str(output_path),
                "stdout_path": str(stdout_path),
                "stderr_path": str(stderr_path),
                "returncode": proc.returncode,
                "validation": validation,
            }
        )
    write_json(output_dir / "agent_results.json", results)
    accepted = sum(1 for row in results if (row.get("validation") or {}).get("accepted"))
    print(f"agent tasks: {len(results)} result(s), accepted={accepted}, output={output_dir}")
    return 0 if all((row.get("validation") or {}).get("accepted") for row in results) else 1


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
    run_p.add_argument("--tasks", type=Path, required=True)
    run_p.add_argument("--output-dir", type=Path, default=None)
    run_p.add_argument("--executor", default="", help="Command that reads one task JSON on stdin and prints output JSON.")
    run_p.add_argument("--dry-run", action="store_true", help="Write request JSON files only.")
    run_p.set_defaults(func=run_tasks)

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
