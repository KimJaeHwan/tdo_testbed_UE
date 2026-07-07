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
OLLVM_PROFILES = (
    "OLLVM_FLA",
    "OLLVM_SUB",
    "OLLVM_BCF",
    "OLLVM_SPLIT",
    "OLLVM_FLA_SUB_BCF",
    "OLLVM_SUB_SPLIT",
    "OLLVM_BCF_SPLIT",
    "OLLVM_FLA_SPLIT",
    "OLLVM_FLA_SUB_SPLIT",
    "OLLVM_ALL",
)
OLLVM_ARCHES = ("aarch64", "x64", "x86", "armv7")
OLLVM_ARCH_PROFILES = tuple(f"{profile}_{arch}" for profile in OLLVM_PROFILES for arch in OLLVM_ARCHES)
HOST_PROFILES = ("P0", "P1", "P2")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path, default: Any = None) -> Any:
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _parse_profiles(raw: str) -> list[str]:
    aliases = {
        "all-ollvm": list(OLLVM_PROFILES),
        "ollvm": list(OLLVM_PROFILES),
        "all-ollvm-arch": list(OLLVM_ARCH_PROFILES),
        "ollvm-arch": list(OLLVM_ARCH_PROFILES),
        "all-host": list(HOST_PROFILES),
        "host": list(HOST_PROFILES),
        "all": list(HOST_PROFILES + OLLVM_PROFILES),
    }
    key = raw.strip().lower()
    if key in aliases:
        return aliases[key]
    profiles = [item.strip() for item in raw.split(",") if item.strip()]
    allowed = set(HOST_PROFILES + OLLVM_PROFILES + OLLVM_ARCH_PROFILES)
    unknown = [profile for profile in profiles if profile not in allowed]
    if unknown:
        raise ValueError(f"unknown Suite12 profile(s): {', '.join(unknown)}")
    if not profiles:
        raise ValueError("at least one profile is required")
    return profiles


def _ollvm_arch_from_profile(profile: str) -> str:
    for arch in sorted(OLLVM_ARCHES, key=len, reverse=True):
        if profile.endswith(f"_{arch}"):
            return arch
    return "aarch64" if profile.startswith("OLLVM_") else ""


def _default_ollvm_image(arch: str) -> str:
    return {
        "aarch64": "tdo-testbed-obf-ollvm:llvm4",
        "x64": "tdo-testbed-obf-ollvm:llvm4-x64",
        "x86": "tdo-testbed-obf-ollvm:llvm4-x86",
        "armv7": "tdo-testbed-obf-ollvm:llvm4-armv7",
    }.get(arch, f"tdo-testbed-obf-ollvm:llvm4-{arch}")


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


def _summary_counts(summary: dict) -> dict[str, int]:
    counts = {"pass": 0, "fail": 0, "error": 0, "degraded": 0, "false_positive": 0, "cache_hits": 0}
    for suite in (summary.get("suites") or {}).values():
        for key in counts:
            counts[key] += int(suite.get(key, 0) or 0)
    return counts


def _build_orchestrator_cmd(
    args: argparse.Namespace,
    profile: str,
    cycle_run_id: str,
    output_dir: Path,
) -> list[str]:
    cmd = [
        sys.executable,
        "-m",
        "harness.orchestrator",
        "--config",
        str(args.config),
        "--suite",
        "12",
        "--mode",
        "local-samples",
        "--prepare-artifacts",
        "--force-prepare",
        "--profile",
        profile,
        "--variant-filter",
        f"obf-{profile}",
        "--run-id",
        cycle_run_id,
        "--output-dir",
        str(output_dir),
    ]
    if not args.use_cache:
        cmd.append("--no-cache")
    if args.no_ledger:
        cmd.append("--no-ledger")
    if args.prepare_dry_run:
        cmd.append("--prepare-dry-run")
        cmd.append("--prepare-only")
    if args.case_filter:
        cmd.extend(["--case-filter", args.case_filter])
    if args.case_scope:
        cmd.extend(["--case-scope", args.case_scope])
    return cmd


def _run_setup_docker_image(args: argparse.Namespace, config: HarnessConfig, output_root: Path, profiles: list[str]) -> dict:
    obf_root = config.path("repos", "testbed_12_obf")
    arches = sorted({arch for arch in (_ollvm_arch_from_profile(profile) for profile in profiles) if arch})
    rows = []
    for arch in arches or ["aarch64"]:
        image = _default_ollvm_image(arch)
        cmd = ["env", f"OBF_OLLVM_ARCH={arch}", f"OBF_OLLVM_IMAGE={image}", "bash", str(obf_root / "scripts" / "setup_ollvm_docker.sh")]
        log_path = output_root / f"setup_ollvm_docker_{arch}.log"
        proc = _run_logged(cmd, log_path, cwd=obf_root)
        rows.append({"arch": arch, "image": image, "command": cmd, "returncode": proc.returncode, "log_path": str(log_path)})
        if proc.returncode != 0:
            break
    return {
        "arches": arches or ["aarch64"],
        "rows": rows,
        "returncode": 1 if any(row.get("returncode") != 0 for row in rows) else 0,
    }


def _run_profile_cycle(args: argparse.Namespace, profile: str, cycle_index: int, cycle_dir: Path) -> dict:
    cycle_run_id = f"{args.run_id}_c{cycle_index:04d}_{profile}"
    output_dir = cycle_dir / profile
    log_path = cycle_dir / f"{profile}.log"
    cmd = _build_orchestrator_cmd(args, profile, cycle_run_id, output_dir)
    print(f"[obf-rebuild-loop] cycle={cycle_index} profile={profile}")
    proc = _run_logged(cmd, log_path)
    summary = _read_json(output_dir / "summary.json", {})
    gate = _read_json(output_dir / "gate.json", {})
    prepare_report = _read_json(output_dir / "prepare_report.json", [])
    row = {
        "profile": profile,
        "run_id": cycle_run_id,
        "returncode": proc.returncode,
        "log_path": str(log_path),
        "output_dir": str(output_dir),
        "summary_path": str(output_dir / "summary.json"),
        "failure_report_path": str(output_dir / "failure_report_v2.json"),
        "gate_path": str(output_dir / "gate.json"),
        "prepare_report_path": str(output_dir / "prepare_report.json"),
        "counts": _summary_counts(summary) if isinstance(summary, dict) else {},
        "gate": gate if isinstance(gate, dict) else {},
        "prepare_failed": any(item.get("returncode") != 0 and not item.get("optional") for item in prepare_report or []),
    }
    if row["returncode"] != 0:
        print(f"[obf-rebuild-loop] profile failed: {profile}, log={log_path}")
    return row


def _should_continue(args: argparse.Namespace, cycle_index: int, started: float) -> bool:
    if args.max_cycles > 0 and cycle_index >= args.max_cycles:
        return False
    if args.duration_hours > 0 and time.time() - started >= args.duration_hours * 3600:
        return False
    return True


def run_loop(args: argparse.Namespace) -> int:
    config = HarnessConfig.load(args.config if args.config.exists() else None)
    try:
        profiles = _parse_profiles(args.profiles)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    output_root = args.output_dir or (config.path("output", "root") / args.run_id)
    if args.clean_output and output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    state_path = output_root / "obf_rebuild_loop_state.json"
    started = time.time()
    state: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "run_id": args.run_id,
        "status": "running",
        "started_at": _now(),
        "updated_at": _now(),
        "profiles": profiles,
        "max_cycles": args.max_cycles,
        "duration_hours": args.duration_hours,
        "force_prepare": True,
        "use_cache": args.use_cache,
        "prepare_dry_run": args.prepare_dry_run,
        "cycles": [],
    }
    write_json(state_path, state)

    if args.setup_docker_image:
        setup = _run_setup_docker_image(args, config, output_root, profiles)
        state["setup_docker_image"] = setup
        state["updated_at"] = _now()
        write_json(state_path, state)
        if setup["returncode"] != 0:
            state["status"] = "setup_docker_image_failed"
            state["finished_at"] = _now()
            write_json(state_path, state)
            print(f"[obf-rebuild-loop] stopped: {state['status']}")
            print(f"[obf-rebuild-loop] state: {state_path}")
            return 1

    cycle_index = 0
    while _should_continue(args, cycle_index, started):
        cycle_index += 1
        cycle_dir = output_root / f"cycle_{cycle_index:04d}"
        cycle_dir.mkdir(parents=True, exist_ok=True)
        cycle = {"cycle": cycle_index, "started_at": _now(), "profiles": []}
        failed = False
        for profile in profiles:
            row = _run_profile_cycle(args, profile, cycle_index, cycle_dir)
            cycle["profiles"].append(row)
            if row["returncode"] != 0:
                failed = True
                if not args.continue_on_failure:
                    break
        cycle["finished_at"] = _now()
        cycle["status"] = "failed" if failed else "pass"
        state["cycles"].append(cycle)
        state["updated_at"] = _now()
        write_json(state_path, state)
        if failed and not args.continue_on_failure:
            state["status"] = "profile_failed"
            break
        if args.sleep_seconds > 0 and _should_continue(args, cycle_index, started):
            time.sleep(args.sleep_seconds)

    if state["status"] == "running":
        state["status"] = "complete"
    state["finished_at"] = _now()
    write_json(state_path, state)
    print(f"[obf-rebuild-loop] stopped: {state['status']}")
    print(f"[obf-rebuild-loop] state: {state_path}")
    return 1 if state["status"] in {"profile_failed", "setup_docker_image_failed"} else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Repeatedly rebuild, re-extract, and regress Suite12 OLLVM profiles.")
    parser.add_argument("--config", type=Path, default=ROOT / "harness" / "config.yaml.example")
    parser.add_argument("--run-id", default="obf_rebuild_loop")
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--profiles", default="OLLVM_ALL", help="Comma list, all-ollvm, all-host, or all.")
    parser.add_argument("--max-cycles", type=int, default=1, help="0 means unlimited until duration/failure/manual stop.")
    parser.add_argument("--duration-hours", type=float, default=0.0, help="0 means no wall-clock limit.")
    parser.add_argument("--sleep-seconds", type=float, default=0.0)
    parser.add_argument("--case-filter", default="")
    parser.add_argument("--case-scope", choices=["auto", "always", "never"], default="")
    parser.add_argument("--prepare-dry-run", action="store_true")
    parser.add_argument("--setup-docker-image", action="store_true")
    parser.add_argument("--use-cache", action="store_true", help="Allow Engine11 result cache. Default is no-cache.")
    parser.add_argument("--no-ledger", action="store_true")
    parser.add_argument("--continue-on-failure", action="store_true")
    parser.add_argument("--clean-output", action="store_true", help="Remove this loop's output directory before starting.")
    return parser


def main(argv: list[str] | None = None) -> int:
    return run_loop(build_parser().parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
