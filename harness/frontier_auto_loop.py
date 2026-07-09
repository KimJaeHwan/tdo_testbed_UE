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
from .reporting import write_json


SCHEMA_VERSION = 1
SUITE12_OLLVM_ARCHES = ("aarch64", "x64", "x86", "armv7")


def _suite12_default_image(arch: str) -> str:
    return {
        "aarch64": "tdo-testbed-obf-ollvm:llvm4",
        "x64": "tdo-testbed-obf-ollvm:llvm4-x64",
        "x86": "tdo-testbed-obf-ollvm:llvm4-x86",
        "armv7": "tdo-testbed-obf-ollvm:llvm4-armv7",
    }.get(arch, f"tdo-testbed-obf-ollvm:llvm4-{arch}")


def _suite12_default_platform(arch: str) -> str:
    return {
        "aarch64": "linux/arm64",
        "x64": "linux/amd64",
        "x86": "linux/386",
        "armv7": "linux/arm/v7",
    }.get(arch, "linux/arm64")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path, default: Any = None) -> Any:
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _run_logged(cmd: list[str], log_path: Path, cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    started = _now()
    proc = subprocess.run(cmd, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    log_path.write_text(
        json.dumps({"cmd": cmd, "cwd": str(cwd), "started_at": started, "finished_at": _now()}, indent=2)
        + "\n\n"
        + (proc.stdout or "")
        + f"\n\n[returncode] {proc.returncode}\n",
        encoding="utf-8",
    )
    return proc


def _option_values(raw_args: list[str], option: str) -> list[str]:
    values: list[str] = []
    for index, item in enumerate(raw_args):
        if item == option and index + 1 < len(raw_args):
            values.append(raw_args[index + 1])
        elif item.startswith(option + "="):
            values.append(item.split("=", 1)[1])
    return values


def _suite12_arch_from_profile(profile: str) -> str:
    for arch in sorted(SUITE12_OLLVM_ARCHES, key=len, reverse=True):
        if profile.endswith(f"_{arch}"):
            return arch
    return "aarch64" if profile.startswith("OLLVM_") else ""


def _suite12_setup_arches(args: argparse.Namespace, frontier_args: list[str]) -> list[str]:
    if args.suite12_docker_arch.strip().lower() == "all":
        return list(SUITE12_OLLVM_ARCHES)
    if args.suite12_docker_arch.strip():
        return [item.strip() for item in args.suite12_docker_arch.split(",") if item.strip()]
    profiles = ",".join(_option_values(frontier_args, "--prepare-profiles"))
    arches = {
        arch
        for profile in (item.strip() for item in profiles.split(",") if item.strip())
        for arch in [_suite12_arch_from_profile(profile)]
        if arch
    }
    return sorted(arches) or ["aarch64"]


def _run_suite12_docker_setup_one(
    args: argparse.Namespace,
    config: HarnessConfig,
    output_root: Path,
    arch: str,
) -> dict:
    image = args.suite12_docker_image or _suite12_default_image(arch)
    inspect_cmd = ["docker", "image", "inspect", image]
    inspect = _run_logged(inspect_cmd, output_root / f"suite12_docker_image_{arch}_inspect.log")
    smoke_cmd = ["docker", "run", "--rm", "--platform", _suite12_default_platform(arch), image, "true"]
    smoke = _run_logged(smoke_cmd, output_root / f"suite12_docker_image_{arch}_run_smoke.log")
    if inspect.returncode == 0 or smoke.returncode == 0:
        return {
            "skipped": True,
            "reason": "image already exists",
            "arch": arch,
            "image": image,
            "inspect_log_path": str(output_root / f"suite12_docker_image_{arch}_inspect.log"),
            "run_smoke_log_path": str(output_root / f"suite12_docker_image_{arch}_run_smoke.log"),
            "returncode": 0,
        }
    obf_root = config.path("repos", "testbed_12_obf")
    setup_cmd = ["env", f"OBF_OLLVM_ARCH={arch}", f"OBF_OLLVM_IMAGE={image}", "bash", str(obf_root / "scripts" / "setup_ollvm_docker.sh")]
    proc = _run_logged(setup_cmd, output_root / f"suite12_setup_ollvm_docker_{arch}.log", cwd=obf_root)
    post_inspect = _run_logged(inspect_cmd, output_root / f"suite12_docker_image_{arch}_post_setup_inspect.log")
    return {
        "skipped": False,
        "arch": arch,
        "image": image,
        "inspect_log_path": str(output_root / f"suite12_docker_image_{arch}_inspect.log"),
        "post_inspect_log_path": str(output_root / f"suite12_docker_image_{arch}_post_setup_inspect.log"),
        "post_inspect_returncode": post_inspect.returncode,
        "command": setup_cmd,
        "returncode": proc.returncode if proc.returncode != 0 else post_inspect.returncode,
        "log_path": str(output_root / f"suite12_setup_ollvm_docker_{arch}.log"),
    }


def _run_suite12_docker_setup(args: argparse.Namespace, config: HarnessConfig, output_root: Path, frontier_args: list[str]) -> dict:
    arches = _suite12_setup_arches(args, frontier_args)
    rows = [_run_suite12_docker_setup_one(args, config, output_root, arch) for arch in arches]
    return {
        "arches": arches,
        "rows": rows,
        "returncode": 1 if any(row.get("returncode") != 0 for row in rows) else 0,
    }


def _should_continue(args: argparse.Namespace, cycle_index: int, started: float) -> bool:
    if args.max_cycles > 0 and cycle_index >= args.max_cycles:
        return False
    if args.duration_hours > 0 and time.time() - started >= args.duration_hours * 3600:
        return False
    return True


def _clean_frontier_args(raw_args: list[str]) -> list[str]:
    args = list(raw_args)
    if args and args[0] == "--":
        args = args[1:]
    cleaned: list[str] = []
    skip_next = False
    value_options = {"--run-id", "--output-dir"}
    drop_flags = {"--clean-output"}
    for index, item in enumerate(args):
        if skip_next:
            skip_next = False
            continue
        if item in value_options:
            skip_next = index + 1 < len(args)
            continue
        if any(item.startswith(option + "=") for option in value_options):
            continue
        if item in drop_flags:
            continue
        cleaned.append(item)
    return cleaned


def _has_option(args: list[str], option: str) -> bool:
    return option in args or any(item.startswith(option + "=") for item in args)


def _case_apply_rows(cycle_dir: Path, cycle_state: dict) -> list[dict]:
    plan = _read_json(cycle_dir / "case_apply_plan.json", {})
    rows = plan.get("rows") if isinstance(plan, dict) else None
    if isinstance(rows, list):
        return rows
    for phase in cycle_state.get("phases") or []:
        if isinstance(phase, dict) and phase.get("name") == "case_apply":
            phase_rows = phase.get("rows")
            return phase_rows if isinstance(phase_rows, list) else []
    return []


def _metrics_green(metrics: Any) -> bool:
    if not isinstance(metrics, dict):
        return False
    if int(metrics.get("total") or 0) <= 0:
        return False
    return not any(int(metrics.get(key) or 0) for key in ("fail", "error", "degraded", "false_positive"))


def _phase(cycle_state: dict, name: str) -> dict | None:
    for phase in cycle_state.get("phases") or []:
        if isinstance(phase, dict) and phase.get("name") == name:
            return phase
    return None


def _post_apply_green(cycle_state: dict) -> bool:
    phase = _phase(cycle_state, "post_apply_regression")
    rows = phase.get("rows") if isinstance(phase, dict) else None
    if not isinstance(rows, list) or not rows:
        return False
    for row in rows:
        if not isinstance(row, dict):
            return False
        if row.get("returncode") not in {0, 1}:
            return False
        if not _metrics_green(row.get("metrics")):
            return False
    return True


def _engine_dev_green(cycle_state: dict) -> bool:
    phase = _phase(cycle_state, "engine_dev_loop")
    if not isinstance(phase, dict):
        return False
    if phase.get("skipped"):
        return phase.get("reason") == "post_apply_regression_green"
    state_path = Path(str(phase.get("state_path") or ""))
    engine_state = _read_json(state_path, {})
    if not isinstance(engine_state, dict):
        return False
    if engine_state.get("status") in {"fully_green_before_edit", "fully_green_after_edit"}:
        return True
    for cycle in reversed(engine_state.get("cycles") or []):
        comparison = cycle.get("comparison") if isinstance(cycle, dict) else None
        if isinstance(comparison, dict):
            return bool(comparison.get("fully_green"))
    return False


def _cycle_green_evaluation(cycle_state: dict) -> dict:
    if cycle_state.get("status") != "complete":
        return {
            "green": False,
            "post_apply_green": False,
            "final_green": False,
            "reason": f"frontier_status={cycle_state.get('status') or 'unknown'}",
        }
    baseline = _phase(cycle_state, "baseline_regression")
    if isinstance(baseline, dict) and not _metrics_green(baseline.get("metrics")):
        return {
            "green": False,
            "post_apply_green": False,
            "final_green": False,
            "reason": "baseline_not_green",
        }
    post_apply_green = _post_apply_green(cycle_state)
    engine_green = _engine_dev_green(cycle_state)
    final_green = post_apply_green or engine_green
    if post_apply_green:
        reason = "post_apply_regression_green"
    elif engine_green:
        reason = "engine_dev_loop_final_green"
    else:
        reason = "post_apply_or_engine_not_green"
    return {
        "green": final_green,
        "post_apply_green": post_apply_green,
        "final_green": final_green,
        "reason": reason,
    }


def _green_for_streak(evaluation: dict, mode: str) -> bool:
    if mode == "post-apply":
        return bool(evaluation.get("post_apply_green"))
    return bool(evaluation.get("final_green") or evaluation.get("green"))


def _cycle_summary(cycle_dir: Path, returncode: int) -> dict:
    state_path = cycle_dir / "frontier_case_loop_state.json"
    cycle_state = _read_json(state_path, {})
    if not isinstance(cycle_state, dict):
        cycle_state = {}
    rows = _case_apply_rows(cycle_dir, cycle_state)
    cases = [
        {
            "case_id": row.get("case_id"),
            "target": row.get("target"),
            "mode": row.get("mode"),
            "returncode": row.get("returncode"),
            "expected": row.get("expected"),
        }
        for row in rows
        if isinstance(row, dict)
    ]
    return {
        "returncode": returncode,
        "state_path": str(state_path),
        "frontier_status": cycle_state.get("status"),
        "generated_or_applied_cases": cases,
        "case_count": len(cases),
        "green_evaluation": _cycle_green_evaluation(cycle_state),
    }


def run_loop(args: argparse.Namespace) -> int:
    config = HarnessConfig.load(args.config if args.config.exists() else None)
    output_root = args.output_dir or (config.path("output", "root") / args.run_id)
    if args.clean_output and output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    state_path = output_root / "frontier_auto_loop_state.json"
    started = time.time()

    frontier_args = _clean_frontier_args(args.frontier_args)
    if not _has_option(frontier_args, "--config"):
        frontier_args = ["--config", str(args.config), *frontier_args]

    state: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "run_id": args.run_id,
        "status": "running",
        "started_at": _now(),
        "updated_at": _now(),
        "output_root": str(output_root),
        "max_cycles": args.max_cycles,
        "duration_hours": args.duration_hours,
        "frontier_args": frontier_args,
        "stop_after_green_cycles": args.stop_after_green_cycles,
        "green_streak_mode": args.green_streak_mode,
        "consecutive_green_cycles": 0,
        "cycles": [],
    }
    write_json(state_path, state)

    if args.setup_suite12_docker_image:
        setup = _run_suite12_docker_setup(args, config, output_root, frontier_args)
        state["suite12_docker_setup"] = setup
        state["updated_at"] = _now()
        write_json(state_path, state)
        if setup.get("returncode") != 0:
            state["status"] = "suite12_docker_setup_failed"
            state["finished_at"] = _now()
            write_json(state_path, state)
            print(f"[frontier-auto-loop] stopped: {state['status']}")
            print(f"[frontier-auto-loop] state: {state_path}")
            return 1

    cycle_index = 0
    while _should_continue(args, cycle_index, started):
        cycle_index += 1
        cycle_run_id = f"{args.run_id}_c{cycle_index:04d}"
        cycle_dir = output_root / f"cycle_{cycle_index:04d}"
        cmd = [
            sys.executable,
            "-m",
            "harness.frontier_case_loop",
            "--run-id",
            cycle_run_id,
            "--output-dir",
            str(cycle_dir),
            *frontier_args,
        ]
        print(f"[frontier-auto-loop] cycle={cycle_index}")
        cycle_started_at = _now()
        proc = _run_logged(cmd, output_root / f"cycle_{cycle_index:04d}.log")
        summary = _cycle_summary(cycle_dir, proc.returncode)
        cycle = {
            "cycle": cycle_index,
            "run_id": cycle_run_id,
            "output_dir": str(cycle_dir),
            "log_path": str(output_root / f"cycle_{cycle_index:04d}.log"),
            "started_at": cycle_started_at,
            "finished_at": _now(),
            **summary,
        }
        state["cycles"].append(cycle)
        if _green_for_streak(cycle.get("green_evaluation") or {}, args.green_streak_mode):
            state["consecutive_green_cycles"] = int(state.get("consecutive_green_cycles") or 0) + 1
        else:
            state["consecutive_green_cycles"] = 0
        cycle["consecutive_green_cycles"] = state["consecutive_green_cycles"]
        state["updated_at"] = _now()
        write_json(state_path, state)
        if proc.returncode != 0 or summary.get("frontier_status") != "complete":
            state["status"] = "frontier_failed"
            break
        if args.stop_after_green_cycles > 0 and state["consecutive_green_cycles"] >= args.stop_after_green_cycles:
            state["status"] = "green_streak_complete"
            break
        if args.sleep_seconds > 0 and _should_continue(args, cycle_index, started):
            time.sleep(args.sleep_seconds)

    if state["status"] == "running":
        state["status"] = "complete"
    state["finished_at"] = _now()
    write_json(state_path, state)
    print(f"[frontier-auto-loop] stopped: {state['status']}")
    print(f"[frontier-auto-loop] state: {state_path}")
    return 1 if state["status"] == "frontier_failed" else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Repeat frontier_case_loop cycles and record generated/applied cases per cycle.",
        epilog="Pass frontier_case_loop options after '--'.",
    )
    parser.add_argument("--config", type=Path, default=ROOT / "harness" / "config.yaml.example")
    parser.add_argument("--run-id", default="frontier_auto_loop")
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--clean-output", action="store_true")
    parser.add_argument("--max-cycles", type=int, default=1, help="0 means unlimited until duration/failure/manual stop.")
    parser.add_argument("--duration-hours", type=float, default=0.0, help="0 means no wall-clock limit.")
    parser.add_argument("--sleep-seconds", type=float, default=0.0)
    parser.add_argument(
        "--stop-after-green-cycles",
        type=int,
        default=0,
        help="Stop after this many consecutive complete green cycles. 0 disables the streak gate.",
    )
    parser.add_argument(
        "--green-streak-mode",
        choices=["final", "post-apply"],
        default="final",
        help="final counts cycles repaired by nested engine_dev_loop; post-apply counts only cases that pass immediately before engine repair.",
    )
    parser.add_argument("--setup-suite12-docker-image", action="store_true", help="Ensure the Suite12 OLLVM Docker image exists before starting cycles.")
    parser.add_argument("--suite12-docker-image", default="", help="Override Suite12 OLLVM Docker image. Empty uses an arch-specific default.")
    parser.add_argument("--suite12-docker-arch", default="", help="Comma list or all. Empty infers from --prepare-profiles.")
    parser.add_argument("frontier_args", nargs=argparse.REMAINDER)
    return parser


def main(argv: list[str] | None = None) -> int:
    return run_loop(build_parser().parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
