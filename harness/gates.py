"""
gates.py — 결정적 게이트 (설계 A §5 목적함수·불변식, §P3 오라클잠금).
LLM 아님. failure_report.json(수치)과 git 상태(오라클 변경)만으로 판정한다.
"""
from __future__ import annotations
import subprocess
from pathlib import Path

INVARIANTS = ["I1 crash=0", "I2 false_positive=0", "I3 regression=0", "I4 oracle_unchanged"]


def _counts(report: list[dict]) -> dict:
    crashes = fp = pass_p0 = pass_other = passes = 0
    per_case = {}  # (variant,case) -> verdict  (회귀 비교용)
    for v in report:
        p0 = ("P0" in v["label"]) or ("DebugGame" in v["label"])
        for cid, c in v.get("cases", {}).items():
            per_case[(v["label"], cid)] = c["verdict"]
            if c["verdict"] == "ERROR": crashes += 1
            if c.get("forbidden_found"): fp += 1
            if c["verdict"] == "PASS":
                passes += 1
                pass_p0 += 1 if p0 else 0
                pass_other += 0 if p0 else 1
    return dict(crashes=crashes, fp=fp, pass_p0=pass_p0, pass_other=pass_other,
                passes=passes, per_case=per_case)


def objective_vector(report: list[dict]) -> tuple:
    """사전식 비교용 벡터(클수록 좋음). A §5 순서."""
    c = _counts(report)
    return (-c["crashes"], -c["fp"], c["pass_p0"], c["pass_other"])


def regression_ok(before: list[dict], after: list[dict]) -> bool:
    """I3: 이전에 PASS였던 (variant,case)가 after에서 PASS 유지."""
    b, a = _counts(before)["per_case"], _counts(after)["per_case"]
    for key, verdict in b.items():
        if verdict == "PASS" and a.get(key) != "PASS":
            return False
    return True


def objective_improves(before: list[dict], after: list[dict]) -> bool:
    """불변식(crash/fp) 위반 0 유지하면서 목적벡터가 사전식으로 개선되었나."""
    ca = _counts(after)
    if ca["crashes"] > 0 or ca["fp"] > 0:   # I1·I2 위반이면 무조건 거부
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
