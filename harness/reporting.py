from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any


def sha256_file(path: Path | None) -> str | None:
    if path is None or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_directory(path: Path, pattern: str) -> str | None:
    if not path.is_dir():
        return None
    digest = hashlib.sha256()
    files = sorted(path.rglob(pattern))
    if not files:
        return None
    for item in files:
        digest.update(str(item.relative_to(path)).encode("utf-8"))
        digest.update(b"\0")
        file_hash = sha256_file(item)
        if file_hash:
            digest.update(file_hash.encode("ascii"))
            digest.update(b"\0")
    return digest.hexdigest()


def canonical_hash(data: Any) -> str:
    encoded = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def git_commit(repo: Path) -> str | None:
    result = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def summarize(reports: list[dict]) -> dict:
    suites: dict[str, dict] = {}
    for row in reports:
        suite = row.get("suite") or "unknown"
        bucket = suites.setdefault(
            suite,
            {
                "pass": 0,
                "fail": 0,
                "error": 0,
                "degraded": 0,
                "false_positive": 0,
                "cache_hits": 0,
                "timing": _empty_timing_bucket(),
                "variants": {},
            },
        )
        verdict = str(row.get("verdict") or "ERROR").lower()
        if verdict == "pass":
            bucket["pass"] += 1
        elif verdict == "error":
            bucket["error"] += 1
        elif verdict == "degraded":
            bucket["degraded"] += 1
        else:
            bucket["fail"] += 1
        if row.get("forbidden_found"):
            bucket["false_positive"] += 1
        if (row.get("cache") or {}).get("hit"):
            bucket["cache_hits"] += 1
        _add_timing(bucket["timing"], row)

        variant = row.get("variant_label") or "unknown"
        vb = bucket["variants"].setdefault(
            variant,
            {
                "pass": 0,
                "fail": 0,
                "error": 0,
                "degraded": 0,
                "false_positive": 0,
                "cache_hits": 0,
                "timing": _empty_timing_bucket(),
            },
        )
        if verdict == "pass":
            vb["pass"] += 1
        elif verdict == "error":
            vb["error"] += 1
        elif verdict == "degraded":
            vb["degraded"] += 1
        else:
            vb["fail"] += 1
        if row.get("forbidden_found"):
            vb["false_positive"] += 1
        if (row.get("cache") or {}).get("hit"):
            vb["cache_hits"] += 1
        _add_timing(vb["timing"], row)
    return {"schema_version": 2, "suites": suites}


def performance_report(reports: list[dict], slow_case_limit: int = 20) -> dict:
    rows = []
    for row in reports:
        timing = row.get("timing") or {}
        total_seconds = float(timing.get("total_seconds") or 0.0)
        rows.append(
            {
                "suite": row.get("suite"),
                "variant": row.get("variant_label"),
                "case": row.get("case"),
                "function": row.get("function"),
                "verdict": row.get("verdict"),
                "cache_hit": bool((row.get("cache") or {}).get("hit")),
                "total_seconds": round(total_seconds, 6),
                "scope_seconds": _round_optional(timing.get("scope_seconds")),
                "artifact_seconds": _round_optional(timing.get("artifact_seconds")),
                "build_seconds": _round_optional(timing.get("build_seconds")),
                "query_seconds": _round_optional(timing.get("query_seconds")),
                "validation_seconds": _round_optional(timing.get("validation_seconds")),
                "sink_count": timing.get("sink_count"),
                "build_profile_top": _top_build_profile(timing.get("build_profile")),
                "effective_pcode_path": (row.get("artifacts") or {}).get("effective_pcode_path"),
            }
        )
    rows.sort(key=lambda item: item["total_seconds"], reverse=True)
    return {
        "schema_version": 1,
        "case_count": len(rows),
        "slow_case_limit": slow_case_limit,
        "slow_cases": rows[: max(0, slow_case_limit)],
        "total_seconds": round(sum(row["total_seconds"] for row in rows), 6),
    }


def _empty_timing_bucket() -> dict:
    return {
        "case_count": 0,
        "total_seconds": 0.0,
        "max_case_seconds": 0.0,
        "slowest_case": None,
    }


def _add_timing(bucket: dict, row: dict) -> None:
    timing = row.get("timing") or {}
    total_seconds = float(timing.get("total_seconds") or 0.0)
    bucket["case_count"] += 1
    bucket["total_seconds"] = round(float(bucket.get("total_seconds") or 0.0) + total_seconds, 6)
    if total_seconds > float(bucket.get("max_case_seconds") or 0.0):
        bucket["max_case_seconds"] = round(total_seconds, 6)
        bucket["slowest_case"] = {
            "case": row.get("case"),
            "function": row.get("function"),
            "variant": row.get("variant_label"),
        }


def _round_optional(value: Any) -> float | None:
    if value is None:
        return None
    return round(float(value), 6)


def _top_build_profile(profile: Any, limit: int = 8) -> list[dict]:
    if not isinstance(profile, dict):
        return []
    rows = []
    for key, value in profile.items():
        if not str(key).endswith("_seconds") and not str(key).endswith(":seconds"):
            continue
        try:
            seconds = float(value)
        except (TypeError, ValueError):
            continue
        rows.append({"stage": str(key), "seconds": round(seconds, 6)})
    rows.sort(key=lambda item: item["seconds"], reverse=True)
    return rows[:limit]


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def print_summary(summary: dict) -> None:
    for suite, stats in summary.get("suites", {}).items():
        print(f"## {suite}")
        print(
            f"PASS {stats['pass']}  FAIL {stats['fail']}  ERROR {stats['error']}  "
            f"DEGRADED {stats['degraded']}  FP {stats['false_positive']}  CACHE {stats['cache_hits']}"
        )
        for variant, vstats in sorted(stats.get("variants", {}).items()):
            print(
                f"  {variant:32} PASS {vstats['pass']:3}  FAIL {vstats['fail']:3}  "
                f"ERROR {vstats['error']:2}  FP {vstats['false_positive']:2}  CACHE {vstats['cache_hits']:3}"
            )
