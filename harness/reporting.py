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
                "function_build_top": _function_build_top(timing.get("build_profile")),
                "effective_pcode_path": (row.get("artifacts") or {}).get("effective_pcode_path"),
            }
        )
    rows.sort(key=lambda item: item["total_seconds"], reverse=True)
    return {
        "schema_version": 1,
        "case_count": len(rows),
        "slow_case_limit": slow_case_limit,
        "slow_cases": rows[: max(0, slow_case_limit)],
        "scale_profile": scale_profile(reports),
        "total_seconds": round(sum(row["total_seconds"] for row in rows), 6),
    }


def scale_profile(reports: list[dict], limit: int = 12) -> dict:
    """Aggregate cheap large-binary sizing signals from existing report rows."""
    variants: dict[str, dict] = {}
    stage_totals: dict[str, float] = {}
    hot_functions: dict[tuple[str, str], dict] = {}
    hot_call_boundaries: dict[tuple[str, str, str], dict] = {}
    profiled_builds = 0
    profiled_scope_files = 0
    profiled_top_instruction_count = 0
    profiled_top_pcode_count = 0
    profiled_top_node_count = 0
    profiled_top_edge_count = 0
    seen_build_keys: set[str] = set()

    for row in reports:
        variant = str(row.get("variant_label") or "unknown")
        suite = str(row.get("suite") or "unknown")
        case = str(row.get("case") or "unknown")
        timing = row.get("timing") if isinstance(row.get("timing"), dict) else {}
        build_profile = timing.get("build_profile") if isinstance(timing.get("build_profile"), dict) else {}
        variant_bucket = variants.setdefault(
            variant,
            {
                "suite": suite,
                "case_count": 0,
                "cache_hits": 0,
                "profiled_build_count": 0,
                "total_seconds": 0.0,
                "build_seconds": 0.0,
                "query_seconds": 0.0,
                "validation_seconds": 0.0,
            },
        )
        variant_bucket["case_count"] += 1
        if (row.get("cache") or {}).get("hit"):
            variant_bucket["cache_hits"] += 1
        variant_bucket["total_seconds"] += float(timing.get("total_seconds") or 0.0)
        variant_bucket["build_seconds"] += float(timing.get("build_seconds") or 0.0)
        variant_bucket["query_seconds"] += float(timing.get("query_seconds") or 0.0)
        variant_bucket["validation_seconds"] += float(timing.get("validation_seconds") or 0.0)

        if not build_profile:
            continue
        build_key = _profiled_build_key(row, build_profile)
        if build_key in seen_build_keys:
            continue
        seen_build_keys.add(build_key)
        profiled_builds += 1
        variant_bucket["profiled_build_count"] += 1
        profiled_scope_files += _as_int(build_profile.get("file_count"))
        for key, value in build_profile.items():
            if not str(key).endswith("_seconds") and not str(key).endswith(":seconds"):
                continue
            try:
                seconds = float(value)
            except (TypeError, ValueError):
                continue
            stage_totals[str(key)] = stage_totals.get(str(key), 0.0) + seconds

        for function_row in _function_build_top(build_profile):
            if not isinstance(function_row, dict):
                continue
            function = str(function_row.get("function") or "unknown")
            function_key = (variant, function)
            bucket = hot_functions.setdefault(
                function_key,
                {
                    "variant": variant,
                    "function": function,
                    "cases": set(),
                    "appearances": 0,
                    "seconds": 0.0,
                    "instruction_count": 0,
                    "pcode_count": 0,
                    "node_count": 0,
                    "edge_count": 0,
                },
            )
            bucket["cases"].add(case)
            bucket["appearances"] += 1
            bucket["seconds"] += float(function_row.get("seconds") or 0.0)
            bucket["instruction_count"] += _as_int(function_row.get("instruction_count"))
            bucket["pcode_count"] += _as_int(function_row.get("pcode_count"))
            bucket["node_count"] += _as_int(function_row.get("node_count"))
            bucket["edge_count"] += _as_int(function_row.get("edge_count"))
            profiled_top_instruction_count += _as_int(function_row.get("instruction_count"))
            profiled_top_pcode_count += _as_int(function_row.get("pcode_count"))
            profiled_top_node_count += _as_int(function_row.get("node_count"))
            profiled_top_edge_count += _as_int(function_row.get("edge_count"))
            for call_row in function_row.get("call_boundary_profile_top") or []:
                if not isinstance(call_row, dict):
                    continue
                callsite = str(call_row.get("callsite") or "unknown")
                target = str(call_row.get("target") or "")
                call_key = (variant, function, callsite)
                call_bucket = hot_call_boundaries.setdefault(
                    call_key,
                    {
                        "variant": variant,
                        "function": function,
                        "callsite": callsite,
                        "target": target,
                        "seconds": 0.0,
                        "count": 0,
                        "nodes_added": 0,
                        "edges_added": 0,
                        "pre_storage_count": 0,
                        "post_storage_count": 0,
                    },
                )
                call_bucket["seconds"] += float(call_row.get("seconds") or 0.0)
                call_bucket["count"] += _as_int(call_row.get("count"))
                call_bucket["nodes_added"] += _as_int(call_row.get("nodes_added"))
                call_bucket["edges_added"] += _as_int(call_row.get("edges_added"))
                call_bucket["pre_storage_count"] = max(
                    int(call_bucket["pre_storage_count"]),
                    _as_int(call_row.get("pre_storage_count")),
                )
                call_bucket["post_storage_count"] = max(
                    int(call_bucket["post_storage_count"]),
                    _as_int(call_row.get("post_storage_count")),
                )

    for bucket in variants.values():
        for key in ("total_seconds", "build_seconds", "query_seconds", "validation_seconds"):
            bucket[key] = round(float(bucket[key]), 6)

    return {
        "schema_version": 1,
        "case_count": len(reports),
        "variant_count": len(variants),
        "cache_hit_count": sum(1 for row in reports if (row.get("cache") or {}).get("hit")),
        "profiled_build_count": profiled_builds,
        "profiled_scope_file_count": profiled_scope_files,
        "profiled_top_instruction_count": profiled_top_instruction_count,
        "profiled_top_pcode_count": profiled_top_pcode_count,
        "profiled_top_node_count": profiled_top_node_count,
        "profiled_top_edge_count": profiled_top_edge_count,
        "stage_totals_top": _top_stage_totals(stage_totals, limit),
        "hot_functions_top": _top_hot_functions(hot_functions, limit),
        "hot_call_boundaries_top": _top_hot_call_boundaries(hot_call_boundaries, limit),
        "variants": dict(sorted(variants.items())),
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


def _function_build_top(profile: Any) -> list[dict]:
    if not isinstance(profile, dict):
        return []
    rows = profile.get("function_build_top")
    return rows if isinstance(rows, list) else []


def _profiled_build_key(row: dict, build_profile: dict) -> str:
    scope = row.get("pcode_scope") if isinstance(row.get("pcode_scope"), dict) else {}
    artifacts = row.get("artifacts") if isinstance(row.get("artifacts"), dict) else {}
    scope_key = scope.get("scope_hash") or artifacts.get("root_pcode_hash") or artifacts.get("pcode_hash")
    if scope_key:
        return f"{row.get('variant_label')}:{scope_key}:{build_profile.get('file_count')}"
    return ":".join(
        str(part)
        for part in (
            row.get("variant_label"),
            artifacts.get("effective_pcode_path") or artifacts.get("pcode_path"),
            build_profile.get("file_count"),
        )
    )


def _as_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _top_stage_totals(stage_totals: dict[str, float], limit: int) -> list[dict]:
    rows = [{"stage": stage, "seconds": round(seconds, 6)} for stage, seconds in stage_totals.items()]
    rows.sort(key=lambda item: item["seconds"], reverse=True)
    return rows[:limit]


def _top_hot_functions(hot_functions: dict[tuple[str, str], dict], limit: int) -> list[dict]:
    rows = []
    for bucket in hot_functions.values():
        rows.append(
            {
                "variant": bucket["variant"],
                "function": bucket["function"],
                "case_count": len(bucket["cases"]),
                "appearances": bucket["appearances"],
                "seconds": round(float(bucket["seconds"]), 6),
                "instruction_count": bucket["instruction_count"],
                "pcode_count": bucket["pcode_count"],
                "node_count": bucket["node_count"],
                "edge_count": bucket["edge_count"],
            }
        )
    rows.sort(key=lambda item: item["seconds"], reverse=True)
    return rows[:limit]


def _top_hot_call_boundaries(hot_call_boundaries: dict[tuple[str, str, str], dict], limit: int) -> list[dict]:
    rows = []
    for bucket in hot_call_boundaries.values():
        rows.append(
            {
                "variant": bucket["variant"],
                "function": bucket["function"],
                "callsite": bucket["callsite"],
                "target": bucket["target"],
                "seconds": round(float(bucket["seconds"]), 6),
                "count": bucket["count"],
                "nodes_added": bucket["nodes_added"],
                "edges_added": bucket["edges_added"],
                "pre_storage_count": bucket["pre_storage_count"],
                "post_storage_count": bucket["post_storage_count"],
            }
        )
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
