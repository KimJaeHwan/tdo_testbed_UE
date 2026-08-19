from __future__ import annotations


def is_negative_case(row: dict) -> bool:
    return bool(row.get("negative_case"))


def is_precision_pending(row: dict) -> bool:
    return bool(
        not is_negative_case(row)
        and (
            row.get("precision_status") == "REFINEMENT_PENDING"
            or row.get("precision_candidates")
            or row.get("forbidden_found")
        )
    )


def is_negative_control_violation(row: dict) -> bool:
    return bool(is_negative_case(row) and row.get("verdict") != "PASS")


def is_recall_failure(row: dict) -> bool:
    verdict = str(row.get("verdict") or "ERROR")
    return bool(
        not is_negative_case(row)
        and verdict not in {"PASS", "ERROR", "DEGRADED"}
    )


def report_metrics(report: list[dict]) -> dict[str, int]:
    counts = {
        "pass": 0,
        "fail": 0,
        "error": 0,
        "degraded": 0,
        "precision_pending": 0,
        "negative_control_failures": 0,
        "recall_failures": 0,
    }
    for row in report:
        verdict = str(row.get("verdict") or "ERROR").lower()
        if verdict == "pass":
            counts["pass"] += 1
        elif verdict == "error":
            counts["error"] += 1
        elif verdict == "degraded":
            counts["degraded"] += 1
        else:
            counts["fail"] += 1
        if is_precision_pending(row):
            counts["precision_pending"] += 1
        if is_negative_control_violation(row):
            counts["negative_control_failures"] += 1
        if is_recall_failure(row):
            counts["recall_failures"] += 1
    counts["false_positive"] = counts["precision_pending"]
    counts["total"] = sum(counts[key] for key in ("pass", "fail", "error", "degraded"))
    return counts


def report_primary_green(report: list[dict]) -> bool:
    metrics = report_metrics(report)
    return bool(
        metrics["total"] > 0
        and metrics["fail"] == 0
        and metrics["error"] == 0
        and metrics["degraded"] == 0
        and metrics["negative_control_failures"] == 0
    )
