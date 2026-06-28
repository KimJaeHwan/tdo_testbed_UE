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
    work_items: list[dict] = []
    if args.scaffold_work_items:
        work_items = _write_work_items(output_root, written)
    manifest = {
        "schema_version": PROPOSAL_SCHEMA_VERSION,
        "run_id": args.run_id,
        "source_agent_results": str(args.agent_results),
        "written": written,
        "work_items": work_items,
        "generated_at": _now(),
    }
    write_json(output_root / "proposal_manifest.json", manifest)
    print(f"materialized {len(written)} proposal artifact(s) under {output_root}")
    if work_items:
        print(f"scaffolded {len(work_items)} proposal work item(s)")
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


def _write_work_items(output_root: Path, written: list[dict]) -> list[dict]:
    root = output_root / "work_items"
    root.mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text(
        "\n".join(
            [
                "# Proposal Work Items",
                "",
                "These files are review artifacts only.",
                "They do not modify expected JSON, manifests, Engine11 main, or testbed sources.",
                "Human approval is required before copying any source, expected data, or engine fix into a real repo.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    items: list[dict] = []
    for entry in written:
        artifact_path = Path(str(entry.get("path") or ""))
        if not artifact_path.is_file():
            continue
        artifact = _read_json(artifact_path)
        kind = artifact.get("kind")
        if kind == "proposed_case":
            items.append(_write_case_work_item(root, artifact))
        elif kind == "engine_fix_proposal":
            items.append(_write_engine_work_item(root, artifact))
        elif kind == "coverage_update_proposal":
            items.append(_write_coverage_work_item(root, artifact))
    return items


def _write_case_work_item(root: Path, artifact: dict) -> dict:
    proposal = artifact.get("proposal") or {}
    case_id = str(proposal.get("id") or "unnamed_case")
    case_root = root / "source_cases"
    case_root.mkdir(parents=True, exist_ok=True)
    source_path = case_root / f"{_safe_name(case_id)}.proposal.cpp"
    expected_path = case_root / f"{_safe_name(case_id)}.expected.proposal.json"
    source_path.write_text(_render_case_source(case_id, proposal), encoding="utf-8")
    write_json(
        expected_path,
        {
            "schema_version": PROPOSAL_SCHEMA_VERSION,
            "kind": "case_expected_proposal",
            "case_id": case_id,
            "expected": proposal.get("expected") or {},
            "expected_flow": proposal.get("expected_flow") or [],
            "forbidden_flow": proposal.get("forbidden_flow") or [],
            "oracle_basis": proposal.get("oracle_basis"),
            "independent_check": proposal.get("independent_check") or proposal.get("independent_validation"),
            "policy": {
                "manifest_not_modified": True,
                "expected_not_applied": True,
                "requires_human_approval": True,
            },
        },
    )
    return {"kind": "case_work_item", "case_id": case_id, "source_path": str(source_path), "expected_path": str(expected_path)}


def _render_case_source(case_id: str, proposal: dict) -> str:
    snippet = str(proposal.get("cpp_or_ue") or "").strip()
    header = [
        f"// Proposal-only source skeleton for {case_id}.",
        "// Do not add this to manifests or expected JSON without human approval.",
        "// Oracle basis and independent checks live beside this file as *.expected.proposal.json.",
        "",
    ]
    if snippet:
        return "\n".join(header + [snippet, ""])
    return "\n".join(
        header
        + [
            f"void {case_id}_proposal_skeleton() {{",
            "    // TODO: replace with by-construction source from the accepted case_author proposal.",
            "    // TODO: attach independent endpoint validation before manifest approval.",
            "}",
            "",
        ]
    )


def _write_engine_work_item(root: Path, artifact: dict) -> dict:
    proposal = artifact.get("proposal") or {}
    key = str(proposal.get("branch") or proposal.get("summary") or "engine_fix")
    item_root = root / "engine_fixes" / _safe_name(key)
    item_root.mkdir(parents=True, exist_ok=True)
    plan_path = item_root / "engine_fix_plan.json"
    write_json(
        plan_path,
        {
            "schema_version": PROPOSAL_SCHEMA_VERSION,
            "kind": "engine_fix_work_item",
            "proposal": proposal,
            "policy": {
                "engine_repo_not_modified": True,
                "main_merge_forbidden": True,
                "oracle_changes_forbidden": True,
                "requires_human_approval": True,
            },
        },
    )
    return {"kind": "engine_fix_work_item", "plan_path": str(plan_path)}


def _write_coverage_work_item(root: Path, artifact: dict) -> dict:
    row = artifact.get("agent_result") or {}
    item_root = root / "coverage_updates"
    item_root.mkdir(parents=True, exist_ok=True)
    path = item_root / f"coverage_{row.get('task_index', 'unknown')}.proposal.json"
    write_json(
        path,
        {
            "schema_version": PROPOSAL_SCHEMA_VERSION,
            "kind": "coverage_work_item",
            "proposal": artifact.get("proposal") or {},
            "policy": {
                "capability_map_not_modified": True,
                "requires_human_or_memory_synth_review": True,
            },
        },
    )
    return {"kind": "coverage_work_item", "path": str(path)}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Materialize accepted agent outputs into proposal artifacts.")
    parser.add_argument("--agent-results", type=Path, required=True)
    parser.add_argument("--run-id", default="manual")
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--include-coverage", action="store_true")
    parser.add_argument("--scaffold-work-items", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    return materialize(build_parser().parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
