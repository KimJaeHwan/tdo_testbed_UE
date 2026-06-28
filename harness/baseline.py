#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from .config import HarnessConfig, ROOT
from .memory.store import Memory
from .reporting import sha256_file, write_json


BASELINE_PIN_SCHEMA_VERSION = 1


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_report(config: HarnessConfig, value: str) -> Path:
    path = Path(value).expanduser()
    if path.is_dir():
        path = path / "failure_report_v2.json"
    if path.is_file():
        return path
    run_path = config.path("output", "root") / value / "failure_report_v2.json"
    if run_path.is_file():
        return run_path
    raise FileNotFoundError(f"baseline report not found: {value}")


def list_pins(args: argparse.Namespace, memory: Memory) -> int:
    pins = _read_json(memory.baseline_pins_path, {"schema_version": BASELINE_PIN_SCHEMA_VERSION, "pins": {}})
    if args.json:
        print(json.dumps(pins, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    entries = pins.get("pins") or {}
    if not entries:
        print("no baseline pins")
        return 0
    for name, pin in sorted(entries.items()):
        print(f"{name:24} {pin.get('run_id') or '-':24} {pin.get('report_hash','')[:12]}  {pin.get('description','')}")
        print(f"  report: {pin.get('report_path')}")
    return 0


def show_pin(args: argparse.Namespace, memory: Memory) -> int:
    pins = _read_json(memory.baseline_pins_path, {"schema_version": BASELINE_PIN_SCHEMA_VERSION, "pins": {}})
    pin = (pins.get("pins") or {}).get(args.name)
    if not pin:
        print(f"pin not found: {args.name}")
        return 1
    print(json.dumps(pin, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def pin_baseline(args: argparse.Namespace, config: HarnessConfig, memory: Memory) -> int:
    try:
        report = _resolve_report(config, args.report or args.run_id)
    except FileNotFoundError as exc:
        print(f"error: {exc}")
        return 2
    output_root = report.parent
    summary_path = output_root / "summary.json"
    gate_path = output_root / "gate.json"
    pins = _read_json(memory.baseline_pins_path, {"schema_version": BASELINE_PIN_SCHEMA_VERSION, "pins": {}})
    pins.setdefault("pins", {})
    pins["pins"][args.name] = {
        "schema_version": BASELINE_PIN_SCHEMA_VERSION,
        "name": args.name,
        "run_id": args.run_id or output_root.name,
        "report_path": str(report),
        "report_hash": sha256_file(report),
        "summary_path": str(summary_path) if summary_path.exists() else None,
        "gate_path": str(gate_path) if gate_path.exists() else None,
        "description": args.description,
        "actor": args.actor or os.environ.get("USER") or "unknown",
        "pinned_at": _now(),
    }
    write_json(memory.baseline_pins_path, pins)
    print(json.dumps(pins["pins"][args.name], ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage named regression baseline pins.")
    parser.add_argument("--config", type=Path, default=ROOT / "harness" / "config.yaml")
    sub = parser.add_subparsers(dest="command", required=True)

    list_p = sub.add_parser("list", help="List baseline pins.")
    list_p.add_argument("--json", action="store_true")
    list_p.set_defaults(func=list_pins)

    show_p = sub.add_parser("show", help="Show one baseline pin.")
    show_p.add_argument("name")
    show_p.set_defaults(func=show_pin)

    pin_p = sub.add_parser("pin", help="Pin a run or report as a named regression baseline.")
    pin_p.add_argument("name")
    pin_p.add_argument("--run-id", default="")
    pin_p.add_argument("--report", default="", help="Output directory or failure_report_v2.json path.")
    pin_p.add_argument("--description", default="")
    pin_p.add_argument("--actor", default="")
    pin_p.set_defaults(func=pin_baseline)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    config = HarnessConfig.load(args.config if args.config.exists() else None)
    memory = Memory(config.path("output", "memory"))
    if args.command == "pin" and not args.run_id and not args.report:
        print("error: pin requires --run-id or --report")
        return 2
    if args.command == "pin":
        return args.func(args, config, memory)
    return args.func(args, memory)


if __name__ == "__main__":
    raise SystemExit(main())
