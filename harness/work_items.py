#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import HarnessConfig, ROOT
from .human_approval import load_items
from .memory.store import Memory
from .reporting import write_json


WORK_ITEM_SCHEMA_VERSION = 1


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _safe_name(text: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "_" for ch in text)[:160]


def _approval_status(config: HarnessConfig, key: str) -> dict:
    if not key:
        return {"approved": False, "reason": "missing approval key"}
    memory = Memory(config.path("output", "memory"))
    _queued, decisions = load_items(memory)
    decision = decisions.get(key)
    if not decision:
        return {"approved": False, "reason": f"approval key not found: {key}"}
    return {
        "approved": decision.get("decision") == "approve",
        "reason": decision.get("reason", ""),
        "decision": decision,
    }


def _guard_approval(args: argparse.Namespace, config: HarnessConfig) -> tuple[bool, dict]:
    if getattr(args, "allow_unapproved", False):
        return True, {"approved": False, "reason": "explicitly allowed unapproved dry/work item operation"}
    status = _approval_status(config, str(getattr(args, "approval_key", "") or ""))
    return bool(status.get("approved")), status


def doctor(args: argparse.Namespace, _config: HarnessConfig) -> int:
    manifest_path = args.proposal_root / "proposal_manifest.json"
    if not manifest_path.is_file():
        print(f"missing proposal manifest: {manifest_path}")
        return 1
    manifest = _read_json(manifest_path)
    rows = []
    missing = []
    for section in ("written", "work_items"):
        for item in manifest.get(section) or []:
            path = Path(str(item.get("path") or item.get("plan_path") or item.get("source_path") or item.get("expected_path") or ""))
            exists = path.is_file()
            if not exists:
                missing.append(str(path))
            rows.append({"section": section, "kind": item.get("kind"), "path": str(path), "exists": exists})
    summary = {
        "schema_version": WORK_ITEM_SCHEMA_VERSION,
        "proposal_root": str(args.proposal_root),
        "checked": len(rows),
        "missing": missing,
        "rows": rows,
    }
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"proposal_root: {args.proposal_root}")
        print(f"checked: {len(rows)}")
        for row in rows:
            status = "ok" if row["exists"] else "missing"
            print(f"{status:7} {row['section']:10} {row['kind'] or '-':24} {row['path']}")
    return 0 if not missing else 1


def engine_worktree(args: argparse.Namespace, config: HarnessConfig) -> int:
    plan = _read_json(args.plan)
    if plan.get("kind") != "engine_fix_work_item":
        print(f"not an engine_fix_work_item: {args.plan}")
        return 2
    proposal = plan.get("proposal") or {}
    branch = args.branch or str(proposal.get("branch") or f"harness/{_safe_name(str(proposal.get('summary') or 'engine-fix'))}")
    engine_repo = config.path("repos", "engine_11")
    worktree_root = args.worktree_root or config.path("output", "root") / "worktrees" / "engine"
    worktree_path = args.worktree_path or worktree_root / _safe_name(branch)
    ok, approval = _guard_approval(args, config)
    result = {
        "schema_version": WORK_ITEM_SCHEMA_VERSION,
        "kind": "engine_worktree_plan",
        "engine_repo": str(engine_repo),
        "branch": branch,
        "base_ref": args.base_ref,
        "worktree_path": str(worktree_path),
        "approval": approval,
        "created": False,
        "patch_written": False,
        "patch_applied": False,
        "generated_at": _now(),
    }
    patch_text = str(proposal.get("patch") or proposal.get("unified_diff") or proposal.get("diff") or "")
    if args.dry_run:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    if not ok:
        print(json.dumps({**result, "error": "approval required"}, ensure_ascii=False, indent=2, sort_keys=True))
        return 1
    if not args.create:
        print(json.dumps({**result, "error": "use --create or --dry-run"}, ensure_ascii=False, indent=2, sort_keys=True))
        return 2
    worktree_root.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "-C", str(engine_repo), "worktree", "add", "-b", branch, str(worktree_path), args.base_ref], check=True)
    result["created"] = True
    harness_dir = worktree_path / ".harness"
    harness_dir.mkdir(parents=True, exist_ok=True)
    write_json(harness_dir / "engine_fix_plan.json", plan)
    if patch_text:
        patch_path = harness_dir / "proposal.patch"
        patch_path.write_text(patch_text, encoding="utf-8")
        result["patch_written"] = True
        subprocess.run(["git", "-C", str(worktree_path), "apply", "--check", str(patch_path)], check=True)
        if args.apply_patch:
            subprocess.run(["git", "-C", str(worktree_path), "apply", str(patch_path)], check=True)
            result["patch_applied"] = True
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def case_bundle(args: argparse.Namespace, config: HarnessConfig) -> int:
    expected = _read_json(args.expected)
    if expected.get("kind") != "case_expected_proposal":
        print(f"not a case_expected_proposal: {args.expected}")
        return 2
    source_path = args.source or args.expected.with_name(args.expected.name.replace(".expected.proposal.json", ".proposal.cpp"))
    if not source_path.is_file():
        print(f"missing proposal source: {source_path}")
        return 1
    manifest_case = _manifest_case_from_expected(expected, args.target)
    bundle_root = args.bundle_dir or config.path("output", "root") / "case_bundles" / _safe_name(str(expected.get("case_id") or "unnamed_case"))
    bundle_root.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source_path, bundle_root / source_path.name)
    shutil.copyfile(args.expected, bundle_root / args.expected.name)
    write_json(bundle_root / "manifest_case.proposal.json", manifest_case)
    write_json(
        bundle_root / "apply_plan.json",
        {
            "schema_version": WORK_ITEM_SCHEMA_VERSION,
            "kind": "case_apply_plan",
            "target": args.target,
            "source": str(source_path),
            "expected": str(args.expected),
            "manifest_case": str(bundle_root / "manifest_case.proposal.json"),
            "policy": {
                "real_source_not_modified": True,
                "manifest_not_modified": True,
                "expected_not_applied": True,
                "requires_human_approval_for_apply": True,
            },
            "generated_at": _now(),
        },
    )
    print(f"case bundle: {bundle_root}")
    return 0


def case_apply(args: argparse.Namespace, config: HarnessConfig) -> int:
    expected = _read_json(args.expected)
    if expected.get("kind") != "case_expected_proposal":
        print(f"not a case_expected_proposal: {args.expected}")
        return 2
    source_path = args.source or args.expected.with_name(args.expected.name.replace(".expected.proposal.json", ".proposal.cpp"))
    if not source_path.is_file():
        print(f"missing proposal source: {source_path}")
        return 1
    target = _target_paths(config.root, args.target)
    manifest_case = _manifest_case_from_expected(expected, args.target)
    ok, approval = _guard_approval(args, config)
    plan = {
        "schema_version": WORK_ITEM_SCHEMA_VERSION,
        "kind": "case_apply_dry_run" if args.dry_run else "case_apply",
        "target": args.target,
        "source_file": str(target["source_file"]),
        "manifest": str(target["manifest"]),
        "case_id": manifest_case["id"],
        "approval": approval,
        "manifest_case": manifest_case,
    }
    if args.dry_run:
        print(json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    if not args.apply:
        print(json.dumps({**plan, "error": "use --apply or --dry-run"}, ensure_ascii=False, indent=2, sort_keys=True))
        return 2
    if not ok:
        print(json.dumps({**plan, "error": "approval required"}, ensure_ascii=False, indent=2, sort_keys=True))
        return 1
    _append_source(target["source_file"], source_path.read_text(encoding="utf-8"), args.target)
    _append_manifest_case(target["manifest"], manifest_case, replace=args.replace)
    print(json.dumps({**plan, "applied": True}, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _target_paths(root: Path, target: str) -> dict[str, Path]:
    if target == "suite10-cpp":
        return {
            "source_file": root / "cpp_like" / "src" / "cases_fusion.cpp",
            "manifest": root / "cpp_like" / "manifests" / "cases_v2_manifest.json",
        }
    if target == "suite10-ue":
        return {
            "source_file": root
            / "unreal_playground"
            / "TraceUnrealPlayground"
            / "Source"
            / "TraceUnrealPlayground"
            / "TraceCases2.cpp",
            "manifest": root / "unreal_playground" / "manifests" / "cases_v2_manifest.json",
        }
    raise ValueError(f"unknown target: {target}")


def _manifest_case_from_expected(expected: dict, target: str) -> dict:
    case_id = str(expected.get("case_id") or "unnamed_case")
    payload = expected.get("expected") or {}
    binary = "tv2_cpp_like" if target == "suite10-cpp" else "tv2_unreal"
    source_file = "src/cases_fusion.cpp" if target == "suite10-cpp" else "Source/TraceUnrealPlayground/TraceCases2.cpp"
    explicit = payload.get("manifest_case") if isinstance(payload, dict) else None
    if isinstance(explicit, dict):
        return dict(explicit)
    return {
        "id": case_id,
        "tier": int(payload.get("tier", 0) if isinstance(payload, dict) else 0),
        "severity": payload.get("severity", "proposed-regression") if isinstance(payload, dict) else "proposed-regression",
        "binary": payload.get("binary", binary) if isinstance(payload, dict) else binary,
        "name": payload.get("name", _safe_name(case_id)) if isinstance(payload, dict) else _safe_name(case_id),
        "function": payload.get("function", f"case_{case_id}") if isinstance(payload, dict) else f"case_{case_id}",
        "source_file": payload.get("source_file", source_file) if isinstance(payload, dict) else source_file,
        "anchor": payload.get("anchor", {"callee": "dfb_sink_int", "arg_index": 0}) if isinstance(payload, dict) else {"callee": "dfb_sink_int", "arg_index": 0},
        "expected_data_sources": _source_list(payload, "expected_data_sources", "data_sources"),
        "expected_control_sources": _source_list(payload, "expected_control_sources", "control_sources"),
        "expected_global_sources": _source_list(payload, "expected_global_sources", "global_sources"),
        "forbidden_data_sources": _source_list(payload, "forbidden_data_sources", "forbidden_data_sources"),
        "forbidden_control_sources": _source_list(payload, "forbidden_control_sources", "forbidden_control_sources"),
        "expected_features": payload.get("expected_features", ["proposed"]) if isinstance(payload, dict) else ["proposed"],
        "allowed_warnings": payload.get("allowed_warnings", []) if isinstance(payload, dict) else [],
        "expected_flow": expected.get("expected_flow") or [],
        "forbidden_flow": expected.get("forbidden_flow") or [],
    }


def _source_list(payload: Any, canonical: str, short: str) -> list:
    if not isinstance(payload, dict):
        return []
    value = payload.get(canonical, payload.get(short, []))
    return value if isinstance(value, list) else [value]


def _append_source(target_file: Path, snippet: str, target: str) -> None:
    text = target_file.read_text(encoding="utf-8")
    snippet = "\n\n" + snippet.strip() + "\n"
    if target == "suite10-cpp" and "} /* extern \"C\" */" in text:
        text = text.replace("\n} /* extern \"C\" */", snippet + "\n} /* extern \"C\" */")
    else:
        text = text.rstrip() + snippet + "\n"
    target_file.write_text(text, encoding="utf-8")


def _append_manifest_case(manifest_path: Path, manifest_case: dict, replace: bool) -> None:
    manifest = _read_json(manifest_path)
    cases = manifest.setdefault("cases", [])
    case_id = manifest_case.get("id")
    existing_index = next((index for index, row in enumerate(cases) if row.get("id") == case_id), None)
    if existing_index is not None:
        if not replace:
            raise ValueError(f"case already exists in manifest: {case_id}")
        cases[existing_index] = manifest_case
    else:
        cases.append(manifest_case)
    write_json(manifest_path, manifest)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Promote proposal work items without bypassing human gates.")
    parser.add_argument("--config", type=Path, default=ROOT / "harness" / "config.yaml")
    sub = parser.add_subparsers(dest="command", required=True)

    doctor_p = sub.add_parser("doctor", help="Validate proposal/work item files.")
    doctor_p.add_argument("--proposal-root", type=Path, required=True)
    doctor_p.add_argument("--json", action="store_true")
    doctor_p.set_defaults(func=doctor)

    engine_p = sub.add_parser("engine-worktree", help="Prepare an isolated Engine11 worktree from an engine fix work item.")
    engine_p.add_argument("--plan", type=Path, required=True)
    engine_p.add_argument("--branch", default="")
    engine_p.add_argument("--base-ref", default="HEAD")
    engine_p.add_argument("--worktree-root", type=Path, default=None)
    engine_p.add_argument("--worktree-path", type=Path, default=None)
    engine_p.add_argument("--approval-key", default="")
    engine_p.add_argument("--allow-unapproved", action="store_true")
    engine_p.add_argument("--dry-run", action="store_true")
    engine_p.add_argument("--create", action="store_true")
    engine_p.add_argument("--apply-patch", action="store_true")
    engine_p.set_defaults(func=engine_worktree)

    bundle_p = sub.add_parser("case-bundle", help="Create a review bundle from a proposed case work item.")
    bundle_p.add_argument("--expected", type=Path, required=True)
    bundle_p.add_argument("--source", type=Path, default=None)
    bundle_p.add_argument("--target", choices=["suite10-cpp", "suite10-ue"], required=True)
    bundle_p.add_argument("--bundle-dir", type=Path, default=None)
    bundle_p.set_defaults(func=case_bundle)

    apply_p = sub.add_parser("case-apply", help="Apply an approved proposed case to a real testbed manifest/source file.")
    apply_p.add_argument("--expected", type=Path, required=True)
    apply_p.add_argument("--source", type=Path, default=None)
    apply_p.add_argument("--target", choices=["suite10-cpp", "suite10-ue"], required=True)
    apply_p.add_argument("--approval-key", default="")
    apply_p.add_argument("--allow-unapproved", action="store_true")
    apply_p.add_argument("--dry-run", action="store_true")
    apply_p.add_argument("--apply", action="store_true")
    apply_p.add_argument("--replace", action="store_true")
    apply_p.set_defaults(func=case_apply)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = HarnessConfig.load(args.config if args.config.exists() else None)
    return args.func(args, config)


if __name__ == "__main__":
    raise SystemExit(main())
