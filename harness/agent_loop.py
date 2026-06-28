#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import ROOT
from .reporting import write_json


LOOP_SCHEMA_VERSION = 1


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path, default: Any = None) -> Any:
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _accepted_count(agent_results: Path) -> int:
    rows = _read_json(agent_results, [])
    if not isinstance(rows, list):
        return 0
    return sum(1 for row in rows if (row.get("validation") or {}).get("accepted"))


def _result_count(agent_results: Path) -> int:
    rows = _read_json(agent_results, [])
    return len(rows) if isinstance(rows, list) else 0


def _task_count(tasks: Path) -> int:
    rows = _read_json(tasks, [])
    if not isinstance(rows, list):
        raise ValueError(f"tasks file must contain a list: {tasks}")
    return len(rows)


def run_loop(args: argparse.Namespace) -> int:
    total_tasks = _task_count(args.tasks)
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    state_path = output_dir / "agent_loop_state.json"
    started = time.monotonic()
    deadline = started + max(0.0, args.duration_hours * 3600.0)
    iteration = 0
    total_new_calls = 0
    last_accepted = _accepted_count(output_dir / "agent_results.json")
    stop_reason = ""
    rounds = []

    while True:
        now = time.monotonic()
        if last_accepted >= total_tasks:
            stop_reason = "all_tasks_accepted"
            break
        if now >= deadline:
            stop_reason = "time_budget_exhausted"
            break
        if args.max_total_calls and total_new_calls >= args.max_total_calls:
            stop_reason = "max_total_calls_exhausted"
            break
        calls_left = args.chunk_calls
        if args.max_total_calls:
            calls_left = min(calls_left, args.max_total_calls - total_new_calls)
        if calls_left <= 0:
            stop_reason = "no_calls_left"
            break

        iteration += 1
        before_accepted = last_accepted
        before_count = _result_count(output_dir / "agent_results.json")
        cmd = [
            sys.executable,
            "-m",
            "harness.agent_runtime",
            "run",
            "--config",
            str(args.config),
            "--tasks",
            str(args.tasks),
            "--output-dir",
            str(output_dir),
            "--max-calls",
            str(calls_left),
            "--max-tokens",
            str(args.chunk_tokens),
            "--resume-existing",
            "--stop-on-provider-error",
        ]
        if args.executor:
            cmd.extend(["--executor", args.executor])
        print(f"[agent-loop] round={iteration} accepted={before_accepted}/{total_tasks} calls={calls_left}")
        proc = subprocess.run(cmd, text=True, capture_output=True, check=False)
        print(proc.stdout, end="")
        if proc.stderr:
            print(proc.stderr, end="", file=sys.stderr)
        after_accepted = _accepted_count(output_dir / "agent_results.json")
        after_count = _result_count(output_dir / "agent_results.json")
        new_accepted = max(0, after_accepted - before_accepted)
        new_rows = max(0, after_count - before_count)
        total_new_calls += new_rows
        round_row = {
            "iteration": iteration,
            "started_at": _now(),
            "command": cmd,
            "returncode": proc.returncode,
            "accepted_before": before_accepted,
            "accepted_after": after_accepted,
            "new_accepted": new_accepted,
            "rows_before": before_count,
            "rows_after": after_count,
            "new_rows": new_rows,
        }
        rounds.append(round_row)
        last_accepted = after_accepted
        _write_state(state_path, args, total_tasks, last_accepted, total_new_calls, rounds, "running")

        if after_accepted >= total_tasks:
            stop_reason = "all_tasks_accepted"
            break
        if proc.returncode not in {0, 3}:
            stop_reason = f"agent_runtime_returncode_{proc.returncode}"
            break
        if args.stop_on_no_progress and new_accepted == 0:
            stop_reason = "no_progress"
            break
        if args.materialize_each_round:
            _materialize(args)
        if args.sleep_seconds:
            time.sleep(args.sleep_seconds)

    _write_state(state_path, args, total_tasks, last_accepted, total_new_calls, rounds, stop_reason)
    if args.materialize_proposals:
        _materialize(args)
    print(f"[agent-loop] stopped: {stop_reason}, accepted={last_accepted}/{total_tasks}, new_rows={total_new_calls}")
    return 0 if stop_reason == "all_tasks_accepted" else 3


def _write_state(
    path: Path,
    args: argparse.Namespace,
    total_tasks: int,
    accepted: int,
    total_new_calls: int,
    rounds: list[dict],
    status: str,
) -> None:
    write_json(
        path,
        {
            "schema_version": LOOP_SCHEMA_VERSION,
            "status": status,
            "updated_at": _now(),
            "tasks": str(args.tasks),
            "output_dir": str(args.output_dir),
            "total_tasks": total_tasks,
            "accepted": accepted,
            "total_new_calls": total_new_calls,
            "duration_hours": args.duration_hours,
            "chunk_calls": args.chunk_calls,
            "chunk_tokens": args.chunk_tokens,
            "rounds": rounds,
        },
    )


def _materialize(args: argparse.Namespace) -> None:
    agent_results = args.output_dir / "agent_results.json"
    if not agent_results.is_file():
        return
    proposal_dir = args.proposal_output_dir or args.output_dir.parent / f"{args.output_dir.name}_proposal"
    cmd = [
        sys.executable,
        "-m",
        "harness.proposals",
        "--agent-results",
        str(agent_results),
        "--run-id",
        args.proposal_run_id or args.output_dir.name,
        "--output-dir",
        str(proposal_dir),
    ]
    if args.include_coverage:
        cmd.append("--include-coverage")
    if args.scaffold_work_items:
        cmd.append("--scaffold-work-items")
    proc = subprocess.run(cmd, text=True, capture_output=True, check=False)
    print(proc.stdout, end="")
    if proc.stderr:
        print(proc.stderr, end="", file=sys.stderr)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run harness agent tasks repeatedly until time/call budget is exhausted.")
    parser.add_argument("--config", type=Path, default=ROOT / "harness" / "config.yaml")
    parser.add_argument("--tasks", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--duration-hours", type=float, default=4.5, help="Wall-clock loop budget. Use <5h to leave margin.")
    parser.add_argument("--chunk-calls", type=int, default=5, help="Provider calls per agent_runtime round.")
    parser.add_argument("--chunk-tokens", type=int, default=50000, help="Token budget per agent_runtime round.")
    parser.add_argument("--max-total-calls", type=int, default=0, help="Optional total new call cap. 0 means unlimited.")
    parser.add_argument("--sleep-seconds", type=float, default=0.0)
    parser.add_argument("--executor", default="", help="Optional override executor for smoke/dry-run.")
    parser.add_argument("--stop-on-no-progress", action="store_true", help="Stop when a round accepts no new tasks.")
    parser.add_argument("--materialize-proposals", action="store_true")
    parser.add_argument("--materialize-each-round", action="store_true")
    parser.add_argument("--proposal-run-id", default="")
    parser.add_argument("--proposal-output-dir", type=Path, default=None)
    parser.add_argument("--include-coverage", action="store_true")
    parser.add_argument("--scaffold-work-items", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    return run_loop(build_parser().parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
