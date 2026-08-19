"""
gates.py — 결정적 게이트 (설계 A §5 목적함수·불변식, §P3 오라클잠금).
LLM 아님. failure_report.json(수치)과 git 상태(오라클 변경)만으로 판정한다.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from .evaluation import (
    is_negative_control_violation,
    is_precision_pending,
    is_recall_failure,
)


INVARIANTS = [
    "I1 crash=0",
    "I2 expected_sources_recalled",
    "I3 regression=0",
    "I4 oracle_unchanged",
    "I5 negative_controls_clean",
]


def _case_rows(report: list[dict]):
    for row in report:
        if "case" in row and "variant_label" in row:
            yield row.get("variant_label"), row.get("case"), row
            continue
        for cid, case in row.get("cases", {}).items():
            merged = dict(case)
            merged.setdefault("case", cid)
            yield row.get("label"), cid, merged


def _counts(report: list[dict]) -> dict:
    crashes = precision_pending = negative_failures = recall_failures = 0
    pass_p0 = pass_other = passes = 0
    per_case = {}  # (variant,case) -> verdict  (회귀 비교용)
    for label, cid, case in _case_rows(report):
        label = str(label or "")
        verdict = str(case.get("verdict") or "ERROR")
        p0 = ("P0" in label) or ("DebugGame" in label) or ("debuggame" in label.lower())
        per_case[(label, str(cid))] = verdict
        if verdict == "ERROR":
            crashes += 1
        if is_precision_pending(case):
            precision_pending += 1
        if is_negative_control_violation(case):
            negative_failures += 1
        if is_recall_failure(case):
            recall_failures += 1
        if verdict == "PASS":
            passes += 1
            pass_p0 += 1 if p0 else 0
            pass_other += 0 if p0 else 1
    return dict(
        crashes=crashes,
        precision_pending=precision_pending,
        negative_failures=negative_failures,
        recall_failures=recall_failures,
        pass_p0=pass_p0,
        pass_other=pass_other,
        passes=passes,
        per_case=per_case,
    )


def objective_vector(report: list[dict]) -> tuple:
    """Recall-first lexicographic objective; precision is separate telemetry."""
    c = _counts(report)
    return (
        -c["crashes"],
        -c["negative_failures"],
        -c["recall_failures"],
        c["pass_p0"],
        c["pass_other"],
    )


def regression_ok(before: list[dict], after: list[dict]) -> bool:
    """I3: 이전에 PASS였던 (variant,case)가 after에서 PASS 유지."""
    b, a = _counts(before)["per_case"], _counts(after)["per_case"]
    for key, verdict in b.items():
        if verdict == "PASS" and a.get(key) != "PASS":
            return False
    return True


def regression_failures(before: list[dict], after: list[dict]) -> list[dict]:
    """Rows that were PASS in before and are no longer PASS in after."""
    b, a = _counts(before)["per_case"], _counts(after)["per_case"]
    failures = []
    for key, verdict in sorted(b.items()):
        if verdict == "PASS" and a.get(key) != "PASS":
            variant, case = key
            failures.append({"variant": variant, "case": case, "before": verdict, "after": a.get(key, "MISSING")})
    return failures


def objective_improves(before: list[dict], after: list[dict]) -> bool:
    """Improve recall without introducing crashes or negative-control leaks."""
    ca = _counts(after)
    if ca["crashes"] > 0 or ca["negative_failures"] > 0:
        return False
    return objective_vector(after) > objective_vector(before)


def oracle_locked(root: Path) -> bool:
    """I4: expected/manifest가 이 수정 사이클에서 변경되지 않았는지(P3).
    오라클 변경은 휴먼 게이트 전용 — 자동 수정이 정답을 약화시키는 gaming 차단."""
    patterns = ["expected/", "manifests/", "cases_v2_manifest.json", ".expected.json"]
    diff = subprocess.run(["git", "-C", str(root), "diff", "--name-only", "HEAD"],
                          capture_output=True, text=True).stdout
    touched = [ln for ln in diff.splitlines() if any(p in ln for p in patterns)]
    return len(touched) == 0


def invariant_status(report: list[dict], root: Path | None = None) -> dict:
    counts = _counts(report)
    status = {
        "I1_crash_zero": counts["crashes"] == 0,
        "I2_recall_complete": counts["recall_failures"] == 0,
        "I5_negative_controls_clean": counts["negative_failures"] == 0,
        "precision_clean": counts["precision_pending"] == 0,
        "crashes": counts["crashes"],
        "recall_failures": counts["recall_failures"],
        "negative_control_failures": counts["negative_failures"],
        "precision_pending": counts["precision_pending"],
        "false_positive": counts["precision_pending"],
        "objective_vector": objective_vector(report),
    }
    if root is not None:
        status["I4_oracle_locked"] = oracle_locked(root)
    return status


def human_gate_items(report: list[dict], gate: dict) -> list[dict]:
    """Return deterministic human-review items.

    This is not an LLM triage decision. It only exposes hard gates and places
    where the design requires a person before changing oracle/frontier state.
    """
    items: list[dict] = []
    if gate.get("I4_oracle_locked") is False:
        items.append(
            {
                "kind": "oracle_change",
                "severity": "hard",
                "reason": "expected_or_manifest_changed",
                "required_action": "human_approval_before_accepting_run",
            }
        )
    if gate.get("I3_regression_zero") is False:
        for regression in gate.get("regressions", []):
            items.append(
                {
                    "kind": "regression",
                    "severity": "hard",
                    "case": regression.get("case"),
                    "variant": regression.get("variant"),
                    "reason": "I3 regression gate failed",
                    "evidence_ref": gate.get("regression_baseline"),
                    "required_action": "diagnose_or_revert_before_accepting_run",
                }
            )
    for row in report:
        case = row.get("case")
        variant = row.get("variant_label")
        result_path = (row.get("artifacts") or {}).get("result_path")
        if row.get("verdict") == "ERROR":
            items.append(
                {
                    "kind": "crash_or_harness_error",
                    "severity": "hard",
                    "case": case,
                    "variant": variant,
                    "reason": "I1 crash/error gate failed",
                    "evidence_ref": result_path,
                    "required_action": "diagnose_before_engine_fix",
                }
            )
        if is_negative_control_violation(row):
            items.append(
                {
                    "kind": "negative_control_violation",
                    "severity": "hard",
                    "case": case,
                    "variant": variant,
                    "reason": "I5 negative-control gate failed",
                    "forbidden_found": row.get("forbidden_found", []),
                    "evidence_ref": result_path,
                    "required_action": "diagnose_or_revert_before_accepting_run",
                }
            )
        if is_recall_failure(row):
            items.append(
                {
                    "kind": "frontier_candidate",
                    "severity": "review",
                    "case": case,
                    "variant": variant,
                    "reason": "missing expected source under recall-first policy",
                    "missing": row.get("missing", []),
                    "evidence_ref": result_path,
                    "required_action": "human_or_agent_evidence_before_frontier_status",
                }
            )
    return items
