from __future__ import annotations

from pathlib import Path
from typing import Any


AGENT_TASK_SCHEMA_VERSION = 1


def build_agent_tasks(report: list[dict], human_gate: list[dict], agents_dir: Path) -> list[dict]:
    rows_by_key = {
        (str(row.get("variant_label")), str(row.get("case"))): row
        for row in report
    }
    tasks: list[dict[str, Any]] = []
    for item in human_gate:
        variant = str(item.get("variant"))
        case = str(item.get("case"))
        row = rows_by_key.get((variant, case), {})
        kind = item.get("kind")
        if kind in {"false_positive", "crash_or_harness_error"}:
            tasks.append(_task("triage", agents_dir, {"failure": _failure_view(row), "human_gate": item}))
            tasks.append(_task("diagnostician", agents_dir, {"failure": _failure_view(row), "human_gate": item}))
            tasks.append(
                _task(
                    "adversary",
                    agents_dir,
                    {
                        "kind": "failure_review",
                        "subject": _failure_view(row),
                        "lens": "fp_risk" if kind == "false_positive" else "correctness",
                        "human_gate": item,
                    },
                )
            )
        elif kind == "frontier_candidate":
            tasks.append(_task("triage", agents_dir, {"failure": _failure_view(row), "human_gate": item}))
            tasks.append(
                _task(
                    "coverage_planner",
                    agents_dir,
                    {
                        "failure": _failure_view(row),
                        "gap_note": "missing expected source without false positive; human evidence required before frontier status",
                    },
                )
            )
    return tasks


def _task(agent: str, agents_dir: Path, payload: dict) -> dict:
    role_prompt = agents_dir / f"{agent}.md"
    if not role_prompt.is_file():
        raise ValueError(f"missing agent contract: {role_prompt}")
    return {
        "agent": agent,
        "schema_version": AGENT_TASK_SCHEMA_VERSION,
        "role_prompt": str(role_prompt),
        "requires_evidence": True,
        "input": payload,
    }


def _failure_view(row: dict) -> dict:
    return {
        "suite": row.get("suite"),
        "variant": row.get("variant_label"),
        "case": row.get("case"),
        "function": row.get("function"),
        "verdict": row.get("verdict"),
        "missing": row.get("missing", []),
        "forbidden_found": row.get("forbidden_found", []),
        "cut": row.get("cut", []),
        "artifacts": row.get("artifacts", {}),
        "pcode_scope": row.get("pcode_scope", {}),
    }
