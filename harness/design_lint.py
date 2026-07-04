#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from .config import HarnessConfig, ROOT
from .reporting import write_json


DESIGN_LINT_SCHEMA_VERSION = 1

ENGINE_CODE_ROOTS = ("analysis", "core", "frontend", "query", "report", "tools")
ENGINE_CODE_SUFFIXES = (".py",)


@dataclass(frozen=True)
class Rule:
    rule_id: str
    pattern: re.Pattern[str]
    reason: str


@dataclass(frozen=True)
class Issue:
    path: str
    line: int | None
    rule_id: str
    reason: str
    text: str

    def as_dict(self) -> dict:
        return {
            "path": self.path,
            "line": self.line,
            "rule_id": self.rule_id,
            "reason": self.reason,
            "text": self.text,
        }


RULES = (
    Rule("case_id_literal", re.compile(r"\b(?:TV2|DFB)\d*[A-Za-z0-9_]*\b"), "Engine core must not branch on benchmark/case ids."),
    Rule("case_function_literal", re.compile(r"\bcase_(?:TV2|DFB)[A-Za-z0-9_]*\b"), "Engine core must not branch on benchmark function names."),
    Rule("expected_writer_literal", re.compile(r"\bwrite_(?:expected|neighbor)\b"), "Engine core must not recognize test-only helper names."),
    Rule("fixed_dfb_source_literal", re.compile(r"\bdfb_source_[A-Z]\b"), "Engine core must not special-case expected source labels."),
    Rule("fixed_dfb_sink_literal", re.compile(r"\bdfb_sink_[A-Z]\b"), "Engine core must not special-case expected sink labels."),
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _git(repo: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(repo), *args], text=True, capture_output=True, check=False)


def _is_engine_code_path(path: str) -> bool:
    cleaned = path.replace("\\", "/")
    if not cleaned.endswith(ENGINE_CODE_SUFFIXES):
        return False
    return cleaned.startswith(tuple(root + "/" for root in ENGINE_CODE_ROOTS))


def _rule_applies(rule: Rule, path: str, line: str) -> bool:
    if not rule.pattern.search(line):
        return False
    # Generic boundary providers may mention marker families such as dfb_source_*,
    # but not fixed labels like dfb_source_A. The fixed-label rules above still fire.
    if path == "analysis/boundary_provider.py" and rule.rule_id == "case_id_literal":
        return bool(re.search(r"\b(?:TV2|DFB)\d", line))
    return True


def _lint_added_line(path: str, new_line: int | None, text: str) -> list[Issue]:
    if not _is_engine_code_path(path):
        return []
    stripped = text.strip()
    if not stripped or stripped.startswith("#"):
        return []
    issues: list[Issue] = []
    for rule in RULES:
        if _rule_applies(rule, path, stripped):
            issues.append(Issue(path=path, line=new_line, rule_id=rule.rule_id, reason=rule.reason, text=stripped))
    return issues


def _parse_unified_diff(diff_text: str) -> tuple[list[Issue], int, set[str]]:
    issues: list[Issue] = []
    checked_added_lines = 0
    checked_files: set[str] = set()
    current_path = ""
    new_line: int | None = None
    for raw in diff_text.splitlines():
        if raw.startswith("+++ "):
            marker = raw[4:].strip()
            if marker.startswith("b/"):
                marker = marker[2:]
            current_path = marker if marker != "/dev/null" else ""
            new_line = None
            if current_path and _is_engine_code_path(current_path):
                checked_files.add(current_path)
            continue
        if raw.startswith("@@ "):
            match = re.search(r"\+(\d+)(?:,\d+)?", raw)
            new_line = int(match.group(1)) if match else None
            continue
        if not current_path:
            continue
        if raw.startswith("+") and not raw.startswith("+++"):
            text = raw[1:]
            if _is_engine_code_path(current_path):
                checked_added_lines += 1
            issues.extend(_lint_added_line(current_path, new_line, text))
            if new_line is not None:
                new_line += 1
        elif raw.startswith("-") and not raw.startswith("---"):
            continue
        elif new_line is not None:
            new_line += 1
    return issues, checked_added_lines, checked_files


def _untracked_engine_files(repo: Path) -> list[Path]:
    proc = _git(repo, ["status", "--porcelain", "--untracked-files=all"])
    files: list[Path] = []
    for row in (proc.stdout or "").splitlines():
        if not row.startswith("?? "):
            continue
        rel = row[3:].strip()
        if _is_engine_code_path(rel):
            files.append(repo / rel)
    return files


def _lint_untracked(repo: Path, paths: Iterable[Path]) -> tuple[list[Issue], int, set[str]]:
    issues: list[Issue] = []
    checked_lines = 0
    checked_files: set[str] = set()
    for path in paths:
        rel = path.relative_to(repo).as_posix()
        checked_files.add(rel)
        for index, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
            checked_lines += 1
            issues.extend(_lint_added_line(rel, index, line))
    return issues, checked_lines, checked_files


def run_design_lint(
    *,
    engine_repo: Path,
    diff_file: Path | None = None,
    include_untracked: bool = True,
) -> dict:
    diff_text = diff_file.read_text(encoding="utf-8") if diff_file else ""
    if diff_file is None:
        proc = _git(engine_repo, ["diff", "--", *ENGINE_CODE_ROOTS])
        if proc.returncode != 0:
            return {
                "schema_version": DESIGN_LINT_SCHEMA_VERSION,
                "ok": False,
                "error": proc.stderr.strip() or "git diff failed",
                "engine_repo": str(engine_repo),
                "generated_at": _now(),
            }
        cached = _git(engine_repo, ["diff", "--cached", "--", *ENGINE_CODE_ROOTS])
        diff_text = (proc.stdout or "") + ("\n" if proc.stdout and cached.stdout else "") + (cached.stdout or "")

    issues, checked_added_lines, checked_files = _parse_unified_diff(diff_text)
    untracked_lines = 0
    untracked_files: set[str] = set()
    if diff_file is None and include_untracked:
        extra_issues, untracked_lines, untracked_files = _lint_untracked(engine_repo, _untracked_engine_files(engine_repo))
        issues.extend(extra_issues)

    all_files = sorted(checked_files | untracked_files)
    return {
        "schema_version": DESIGN_LINT_SCHEMA_VERSION,
        "ok": not issues,
        "engine_repo": str(engine_repo),
        "diff_file": str(diff_file) if diff_file else "",
        "checked_files": all_files,
        "checked_added_lines": checked_added_lines,
        "checked_untracked_lines": untracked_lines,
        "issues": [issue.as_dict() for issue in issues],
        "generated_at": _now(),
        "policy": {
            "no_arg_no_ret": True,
            "convention_free": True,
            "no_case_or_helper_hardcoding": True,
            "source_sink_markers_stay_in_boundary_providers": True,
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Lint Engine11 edits for TDO design-rule violations.")
    parser.add_argument("--config", type=Path, default=ROOT / "harness" / "config.yaml")
    parser.add_argument("--engine-repo", type=Path, default=None)
    parser.add_argument("--diff-file", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--no-untracked", action="store_true", help="Do not scan untracked Engine11 code files.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = HarnessConfig.load(args.config if args.config.exists() else None)
    engine_repo = (args.engine_repo or config.path("repos", "engine_11")).expanduser()
    result = run_design_lint(
        engine_repo=engine_repo,
        diff_file=args.diff_file,
        include_untracked=not args.no_untracked,
    )
    if args.output:
        write_json(args.output, result)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        status = "ok" if result.get("ok") else "failed"
        print(f"design lint: {status}")
        for issue in result.get("issues") or []:
            line = f":{issue['line']}" if issue.get("line") else ""
            print(f"{issue['path']}{line}: {issue['rule_id']} - {issue['reason']}")
            print(f"  {issue['text']}")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
