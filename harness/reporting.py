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
            {"pass": 0, "fail": 0, "error": 0, "degraded": 0, "false_positive": 0, "variants": {}},
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

        variant = row.get("variant_label") or "unknown"
        vb = bucket["variants"].setdefault(
            variant,
            {"pass": 0, "fail": 0, "error": 0, "degraded": 0, "false_positive": 0},
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
    return {"schema_version": 2, "suites": suites}


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def print_summary(summary: dict) -> None:
    for suite, stats in summary.get("suites", {}).items():
        print(f"## {suite}")
        print(
            f"PASS {stats['pass']}  FAIL {stats['fail']}  ERROR {stats['error']}  "
            f"DEGRADED {stats['degraded']}  FP {stats['false_positive']}"
        )
        for variant, vstats in sorted(stats.get("variants", {}).items()):
            print(
                f"  {variant:32} PASS {vstats['pass']:3}  FAIL {vstats['fail']:3}  "
                f"ERROR {vstats['error']:2}  FP {vstats['false_positive']:2}"
            )

