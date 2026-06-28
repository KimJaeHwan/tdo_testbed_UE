#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import ROOT
from .reporting import write_json


PROPOSAL_SCHEMA_VERSION = 1


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _safe_name(text: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in text)[:120]


def materialize(args: argparse.Namespace) -> int:
    results = _read_json(args.agent_results)
    if not isinstance(results, list):
        print("agent_results must contain a list")
        return 2
    output_root = args.output_dir or ROOT / "proposed_cases" / args.run_id
    output_root.mkdir(parents=True, exist_ok=True)
    written: list[dict] = []
    for row in results:
        validation = row.get("validation") or {}
        if not validation.get("accepted"):
            continue
        output_path = row.get("output_path")
        if not output_path or not Path(output_path).is_file():
            continue
        output = _read_json(Path(output_path))
        agent = row.get("agent")
        if agent == "case_author":
            written.extend(_write_case_author(output_root, row, output))
        elif agent == "engine_fixer":
            written.append(_write_engine_fixer(output_root, row, output))
        elif agent == "coverage_planner" and args.include_coverage:
            written.append(_write_coverage(output_root, row, output))
    manifest = {
        "schema_version": PROPOSAL_SCHEMA_VERSION,
        "run_id": args.run_id,
        "source_agent_results": str(args.agent_results),
        "written": written,
        "generated_at": _now(),
    }
    write_json(output_root / "proposal_manifest.json", manifest)
    print(f"materialized {len(written)} proposal artifact(s) under {output_root}")
    return 0


def _write_case_author(output_root: Path, row: dict, output: dict) -> list[dict]:
    proposed_root = output_root / "case_author"
    proposed_root.mkdir(parents=True, exist_ok=True)
    written = []
    for index, proposal in enumerate(output.get("proposed_cases") or []):
        case_id = proposal.get("id") or f"case_{row.get('task_index', 'unknown')}_{index}"
        path = proposed_root / f"{_safe_name(str(case_id))}.proposal.json"
        artifact = {
            "schema_version": PROPOSAL_SCHEMA_VERSION,
            "kind": "proposed_case",
            "agent_result": row,
            "proposal": proposal,
            "policy": {
                "expected_not_applied": True,
                "manifest_not_modified": True,
                "requires_human_approval": True,
            },
            "generated_at": _now(),
        }
        write_json(path, artifact)
        written.append({"kind": "proposed_case", "path": str(path), "case_id": case_id})
    return written


def _write_engine_fixer(output_root: Path, row: dict, output: dict) -> dict:
    root = output_root / "engine_fixer"
    root.mkdir(parents=True, exist_ok=True)
    key = output.get("branch") or output.get("summary") or f"engine_fix_{row.get('task_index', 'unknown')}"
    path = root / f"{_safe_name(str(key))}.proposal.json"
    artifact = {
        "schema_version": PROPOSAL_SCHEMA_VERSION,
        "kind": "engine_fix_proposal",
        "agent_result": row,
        "proposal": output,
        "policy": {
            "engine_not_modified": True,
            "main_merge_forbidden": True,
            "oracle_changes_forbidden": True,
            "requires_human_approval": True,
        },
        "generated_at": _now(),
    }
    write_json(path, artifact)
    return {"kind": "engine_fix_proposal", "path": str(path)}


def _write_coverage(output_root: Path, row: dict, output: dict) -> dict:
    root = output_root / "coverage_planner"
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"coverage_{row.get('task_index', 'unknown')}.proposal.json"
    artifact = {
        "schema_version": PROPOSAL_SCHEMA_VERSION,
        "kind": "coverage_update_proposal",
        "agent_result": row,
        "proposal": output,
        "policy": {
            "capability_map_not_modified": True,
            "requires_human_or_memory_synth_review": True,
        },
        "generated_at": _now(),
    }
    write_json(path, artifact)
    return {"kind": "coverage_update_proposal", "path": str(path)}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Materialize accepted agent outputs into proposal artifacts.")
    parser.add_argument("--agent-results", type=Path, required=True)
    parser.add_argument("--run-id", default="manual")
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--include-coverage", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    return materialize(build_parser().parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
