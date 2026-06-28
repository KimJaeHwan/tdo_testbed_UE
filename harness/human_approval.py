#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import HarnessConfig, ROOT
from .memory.store import Memory
from .reporting import canonical_hash, write_json


DECISION_SCHEMA_VERSION = 1
CAPABILITY_STATUSES = {"can", "cannot", "frontier", "missing", "weakly_covered", "contradictory"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _append_jsonl(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _queue_payload(row: dict) -> dict:
    return dict(row.get("case") or row)


def _decision_payload(row: dict) -> dict:
    return dict(row.get("decision") or row)


def queue_key(payload: dict) -> str:
    stable = {
        "run_id": payload.get("run_id"),
        "kind": payload.get("kind"),
        "case": payload.get("case"),
        "variant": payload.get("variant"),
        "reason": payload.get("reason"),
        "missing": payload.get("missing", []),
        "forbidden_found": payload.get("forbidden_found", []),
    }
    return canonical_hash(stable)[:16]


def load_items(memory: Memory) -> tuple[dict[str, dict], dict[str, dict]]:
    queued = {}
    for row in _read_jsonl(memory.human_queue_path):
        payload = _queue_payload(row)
        key = queue_key(payload)
        queued[key] = {**payload, "key": key, "queued_at": row.get("time")}

    decisions = {}
    for row in _read_jsonl(memory.human_decisions_path):
        payload = _decision_payload(row)
        key = str(payload.get("key") or "")
        if key:
            decisions[key] = {**payload, "decided_at": row.get("time")}
    return queued, decisions


def _print_items(items: list[dict], json_output: bool) -> None:
    if json_output:
        print(json.dumps(items, ensure_ascii=False, indent=2, sort_keys=True))
        return
    if not items:
        print("no human approval items")
        return
    for item in items:
        status = item.get("decision", "pending")
        print(
            f"{item['key']}  {status:8}  {item.get('severity',''):6}  "
            f"{item.get('kind',''):20}  {item.get('variant','') or '-':24}  {item.get('case','') or '-'}"
        )
        reason = item.get("reason")
        if reason:
            print(f"  reason: {reason}")


def list_items(args: argparse.Namespace, memory: Memory) -> int:
    queued, decisions = load_items(memory)
    items = []
    for key, item in queued.items():
        decision = decisions.get(key)
        if decision:
            item = {**item, **{"decision": decision.get("decision"), "decided_at": decision.get("decided_at")}}
        elif not args.all:
            item = {**item, "decision": "pending"}
        else:
            item = {**item, "decision": "pending"}
        if not args.all and decision:
            continue
        if args.kind and item.get("kind") != args.kind:
            continue
        if args.run_id and item.get("run_id") != args.run_id:
            continue
        items.append(item)
    items.sort(key=lambda row: (str(row.get("run_id")), str(row.get("kind")), str(row.get("case"))))
    _print_items(items, args.json)
    return 0


def show_item(args: argparse.Namespace, memory: Memory) -> int:
    queued, decisions = load_items(memory)
    item = queued.get(args.key)
    if item is None:
        print(f"not found: {args.key}")
        return 1
    decision = decisions.get(args.key)
    payload = {**item, "decision_record": decision}
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def decide_item(args: argparse.Namespace, memory: Memory) -> int:
    queued, decisions = load_items(memory)
    item = queued.get(args.key)
    if item is None:
        print(f"not found: {args.key}")
        return 1
    if args.key in decisions and not args.replace:
        print(f"already decided: {args.key} (use --replace to append a superseding decision)")
        return 1
    if args.capability_status and args.capability_status not in CAPABILITY_STATUSES:
        print(f"unknown capability status: {args.capability_status}")
        return 2

    decision = {
        "schema_version": DECISION_SCHEMA_VERSION,
        "key": args.key,
        "decision": args.decision,
        "actor": args.actor or os.environ.get("USER") or "unknown",
        "reason": args.reason,
        "capability_status": args.capability_status,
        "queue_item": item,
        "replaces_previous": bool(args.replace),
    }
    _append_jsonl(memory.human_decisions_path, {"time": _now(), "decision": decision})
    if args.capability_status and item.get("case"):
        _update_capability_from_decision(memory, item, decision)
    print(json.dumps(decision, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _update_capability_from_decision(memory: Memory, item: dict, decision: dict) -> None:
    cap = memory.capability_map()
    key = str(item.get("case"))
    previous = cap.get(key, {})
    status = str(decision.get("capability_status"))
    cap[key] = {
        **previous,
        "case_class": key,
        "status": status,
        "human_confirmed": decision.get("decision") == "approve",
        "needs_human": decision.get("decision") != "approve",
        "human_decision_ref": decision.get("key"),
        "human_decision_reason": decision.get("reason"),
        "human_decision_actor": decision.get("actor"),
        "updated_at": _now(),
    }
    write_json(memory.capability_map_path, cap)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inspect and record human approval decisions for harness gates.")
    parser.add_argument("--config", type=Path, default=ROOT / "harness" / "config.yaml")
    sub = parser.add_subparsers(dest="command", required=True)

    list_p = sub.add_parser("list", help="List pending human approval items.")
    list_p.add_argument("--all", action="store_true", help="Include already decided items.")
    list_p.add_argument("--json", action="store_true", help="Emit JSON instead of text.")
    list_p.add_argument("--kind", default="", help="Filter by gate item kind.")
    list_p.add_argument("--run-id", default="", help="Filter by run id.")
    list_p.set_defaults(func=list_items)

    show_p = sub.add_parser("show", help="Show one approval item.")
    show_p.add_argument("key")
    show_p.set_defaults(func=show_item)

    decide_p = sub.add_parser("decide", help="Append a human decision.")
    decide_p.add_argument("key")
    decide_p.add_argument("--decision", required=True, choices=["approve", "reject", "defer"])
    decide_p.add_argument("--reason", required=True)
    decide_p.add_argument("--actor", default="")
    decide_p.add_argument("--capability-status", choices=sorted(CAPABILITY_STATUSES), default="")
    decide_p.add_argument("--replace", action="store_true", help="Append a superseding decision for an already decided item.")
    decide_p.set_defaults(func=decide_item)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    config = HarnessConfig.load(args.config if args.config.exists() else None)
    memory = Memory(config.path("output", "memory"))
    return args.func(args, memory)


if __name__ == "__main__":
    raise SystemExit(main())
