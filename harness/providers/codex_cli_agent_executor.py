#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from harness.config import ROOT

REASONING_EFFORTS = {"low", "medium", "high", "xhigh"}


def _schema_for_agent(agent: str) -> dict:
    base = {
        "agent": {"type": "string"},
        "schema_version": {"type": "integer"},
    }
    if agent == "triage":
        props = {**base, "category": {"type": "string"}, "reason": {"type": "string"}, "evidence_ref": {"type": "string"}}
        return _object_schema(props, list(props))
    if agent == "coverage_planner":
        props = {
            **base,
            "capability_updates": {
                "type": "array",
                "items": _object_schema(
                    {
                        "case_class": {"type": "string"},
                        "status": {"type": "string"},
                        "evidence_ref": {"type": "string"},
                    },
                    ["case_class", "status", "evidence_ref"],
                ),
            },
        }
        return _object_schema(props, list(props))
    if agent == "diagnostician":
        props = {**base, "root_cause": {"type": "string"}, "evidence_ref": {"type": "string"}}
        return _object_schema(props, list(props))
    if agent == "adversary":
        props = {**base, "refuted": {"type": "boolean"}, "lens": {"type": "string"}, "evidence_ref": {"type": "string"}}
        return _object_schema(props, list(props))
    if agent == "engine_fixer":
        props = {
            **base,
            "summary": {"type": "string"},
            "selftest": {"type": "string"},
            "files_changed": {"type": "array", "items": {"type": "string"}},
        }
        return _object_schema(props, list(props))
    if agent == "case_author":
        props = {
            **base,
            "proposed_cases": {
                "type": "array",
                "items": _object_schema(
                    {
                        "id": {"type": "string"},
                        "target": {"type": "string"},
                        "tier": {"type": "integer"},
                        "cpp_or_ue": {"type": "string"},
                        "expected": _case_expected_schema(),
                        "expected_flow": {"type": "array", "items": _flow_step_schema()},
                        "forbidden_flow": {"type": "array", "items": _flow_step_schema()},
                        "oracle_basis": {"type": "string"},
                        "independent_check": {"type": "string"},
                    },
                    [
                        "id",
                        "target",
                        "tier",
                        "cpp_or_ue",
                        "expected",
                        "expected_flow",
                        "forbidden_flow",
                        "oracle_basis",
                        "independent_check",
                    ],
                ),
            },
        }
        return _object_schema(props, list(props))
    if agent == "memory_synth":
        props = {**base, "updated": {"type": "array", "items": {"type": "string"}}}
        return _object_schema(props, list(props))
    props = {**base, "category": {"type": "string"}, "reason": {"type": "string"}, "evidence_ref": {"type": "string"}}
    return _object_schema(props, list(props))


def _object_schema(properties: dict, required: list[str]) -> dict:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": required,
        "properties": properties,
    }


def _string_array_schema() -> dict:
    return {"type": "array", "items": {"type": "string"}}


def _anchor_schema() -> dict:
    props = {
        "callee": {"type": "string"},
        "arg_index": {"type": "integer"},
        "storage": {"type": "string"},
    }
    return _object_schema(props, list(props))


def _manifest_case_schema() -> dict:
    props = {
        "id": {"type": "string"},
        "tier": {"type": "integer"},
        "severity": {"type": "string"},
        "binary": {"type": "string"},
        "name": {"type": "string"},
        "function": {"type": "string"},
        "source_file": {"type": "string"},
        "anchor": _anchor_schema(),
        "expected_no_sources": {"type": "boolean"},
        "expected_data_sources": _string_array_schema(),
        "expected_control_sources": _string_array_schema(),
        "expected_global_sources": _string_array_schema(),
        "forbidden_data_sources": _string_array_schema(),
        "forbidden_control_sources": _string_array_schema(),
        "expected_features": _string_array_schema(),
        "allowed_warnings": _string_array_schema(),
    }
    return _object_schema(props, list(props))


def _case_expected_schema() -> dict:
    props = {
        "tier": {"type": "integer"},
        "severity": {"type": "string"},
        "binary": {"type": "string"},
        "name": {"type": "string"},
        "function": {"type": "string"},
        "source_file": {"type": "string"},
        "anchor": _anchor_schema(),
        "expected_no_sources": {"type": "boolean"},
        "expected_data_sources": _string_array_schema(),
        "expected_control_sources": _string_array_schema(),
        "expected_global_sources": _string_array_schema(),
        "forbidden_data_sources": _string_array_schema(),
        "forbidden_control_sources": _string_array_schema(),
        "expected_features": _string_array_schema(),
        "allowed_warnings": _string_array_schema(),
        "manifest_case": _manifest_case_schema(),
    }
    return _object_schema(props, list(props))


def _flow_step_schema() -> dict:
    props = {
        "kind": {"type": "string"},
        "node": {"type": "string"},
        "function": {"type": "string"},
        "field": {"type": "string"},
        "offset": {"type": "string"},
        "size": {"type": "string"},
        "carries": {"type": "string"},
        "source": {"type": "string"},
        "sink": {"type": "string"},
        "from": {"type": "string"},
        "to": {"type": "string"},
        "reason": {"type": "string"},
    }
    return _object_schema(props, list(props))


def _read_stdin_json() -> dict:
    return json.loads(sys.stdin.read())


def _task_role_prompt(task: dict) -> str:
    path = task.get("role_prompt")
    if path and Path(str(path)).is_file():
        return Path(str(path)).read_text(encoding="utf-8")
    return ""


def _prompt(task: dict) -> str:
    role_prompt = _task_role_prompt(task)
    return "\n".join(
        [
            "You are running as a tdo_testbed_UE harness agent provider.",
            "Return exactly one JSON object that matches the requested agent role.",
            "Do not use markdown or code fences.",
            "Do not modify files. Do not run tests. Do not edit expected files, manifests, source files, or Engine11 code.",
            "Use only the evidence embedded in the task JSON and cite evidence_ref where possible.",
            "If evidence is insufficient, return a conservative JSON object with category/status unknown or frontier candidate.",
            "",
            "Role contract:",
            role_prompt,
            "",
            "Task JSON:",
            json.dumps(task, ensure_ascii=False, sort_keys=True, indent=2),
        ]
    ).strip()


def _error_output(agent: str, message: str) -> dict:
    return {
        "agent": agent,
        "schema_version": 1,
        "category": "environment_defect",
        "reason": message,
        "evidence_ref": "codex_cli_agent_executor",
    }


def _dry_run_output(agent: str, cmd: list[str]) -> dict:
    base = {"agent": agent, "schema_version": 1, "evidence_ref": "codex_cli_agent_executor", "dry_run_command": cmd}
    if agent == "triage":
        return {**base, "category": "unknown", "reason": "codex cli dry-run"}
    if agent == "coverage_planner":
        return {**base, "capability_updates": [{"case_class": "dry_run", "status": "frontier", "evidence_ref": "codex_cli_agent_executor"}]}
    if agent == "diagnostician":
        return {**base, "root_cause": "codex cli dry-run"}
    if agent == "adversary":
        return {**base, "refuted": False, "lens": "dry_run"}
    if agent == "engine_fixer":
        return {**base, "summary": "codex cli dry-run", "selftest": "not-run", "files_changed": []}
    if agent == "case_author":
        return {**base, "proposed_cases": [{"id": "dry_run_case", "oracle_basis": "dry-run", "independent_check": "dry-run"}]}
    if agent == "memory_synth":
        return {**base, "updated": ["dry_run"]}
    return {**base, "category": "unknown", "reason": "codex cli dry-run"}


def _append_reasoning_effort(cmd: list[str], effort: str) -> None:
    if not effort:
        return
    if effort not in REASONING_EFFORTS:
        raise ValueError(f"unsupported reasoning effort: {effort}")
    cmd.extend(["-c", f'model_reasoning_effort="{effort}"'])


def _codex_process_env() -> dict[str, str]:
    env = os.environ.copy()
    home_codex = Path.home() / ".codex"
    if not env.get("CODEX_HOME") and (not home_codex.exists() or not os.access(home_codex, os.W_OK)):
        codex_home = ROOT / "output" / "harness" / ".codex_cli_home"
        codex_home.mkdir(parents=True, exist_ok=True)
        env["CODEX_HOME"] = str(codex_home)
    if env.get("CODEX_HOME"):
        codex_home = Path(env["CODEX_HOME"])
        for key, name in (
            ("XDG_STATE_HOME", "xdg_state"),
            ("XDG_CACHE_HOME", "xdg_cache"),
            ("XDG_CONFIG_HOME", "xdg_config"),
        ):
            env.setdefault(key, str(codex_home / name))
            Path(env[key]).mkdir(parents=True, exist_ok=True)
    return env


def _parse_json_text(text: str) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start : end + 1])
        raise


def execute(args: argparse.Namespace) -> int:
    task = _read_stdin_json()
    agent = str(task.get("agent") or "unknown")
    codex_bin = shutil.which(args.codex_bin)
    if not codex_bin:
        print(json.dumps(_error_output(agent, f"codex executable not found: {args.codex_bin}"), ensure_ascii=False))
        return 2
    with tempfile.TemporaryDirectory(prefix="tdo-codex-agent-") as tmp:
        tmpdir = Path(tmp)
        schema_path = tmpdir / "agent_output_schema.json"
        output_path = tmpdir / "last_message.json"
        schema_path.write_text(json.dumps(_schema_for_agent(agent), ensure_ascii=False, indent=2), encoding="utf-8")
        cmd = [
            codex_bin,
            "exec",
            "--ephemeral",
            "--sandbox",
            args.sandbox,
            "--output-schema",
            str(schema_path),
            "--output-last-message",
            str(output_path),
            "--cd",
            str(args.cwd),
        ]
        if args.model:
            cmd.extend(["--model", args.model])
        try:
            _append_reasoning_effort(cmd, args.reasoning_effort)
        except ValueError as exc:
            print(json.dumps(_error_output(agent, str(exc)), ensure_ascii=False))
            return 2
        if args.profile:
            cmd.extend(["--profile", args.profile])
        if args.oss:
            cmd.append("--oss")
        if args.local_provider:
            cmd.extend(["--local-provider", args.local_provider])
        cmd.append("-")
        if args.dry_run:
            print(json.dumps(_dry_run_output(agent, cmd), ensure_ascii=False, sort_keys=True))
            return 0
        proc = subprocess.run(
            cmd,
            input=_prompt(task),
            text=True,
            capture_output=True,
            check=False,
            timeout=args.timeout,
            env=_codex_process_env(),
        )
        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout or "").strip()[-2000:]
            print(json.dumps(_error_output(agent, f"codex exec failed: {detail}"), ensure_ascii=False))
            return proc.returncode or 1
        try:
            text = output_path.read_text(encoding="utf-8") if output_path.is_file() else proc.stdout
            output = _parse_json_text(text.strip())
        except (OSError, json.JSONDecodeError) as exc:
            print(json.dumps(_error_output(agent, f"codex output parse failed: {exc}"), ensure_ascii=False))
            return 1
        if output.get("agent") is None:
            output["agent"] = agent
        if output.get("schema_version") is None:
            output["schema_version"] = 1
        print(json.dumps(output, ensure_ascii=False, sort_keys=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Codex CLI executor for harness agent tasks.")
    parser.add_argument("--model", default=os.environ.get("CODEX_AGENT_MODEL", ""))
    parser.add_argument("--reasoning-effort", default=os.environ.get("CODEX_AGENT_REASONING_EFFORT", ""), choices=["", *sorted(REASONING_EFFORTS)])
    parser.add_argument("--profile", default=os.environ.get("CODEX_AGENT_PROFILE", ""))
    parser.add_argument("--codex-bin", default=os.environ.get("CODEX_BIN", "codex"))
    parser.add_argument("--cwd", type=Path, default=ROOT)
    parser.add_argument("--sandbox", default=os.environ.get("CODEX_AGENT_SANDBOX", "read-only"), choices=["read-only", "workspace-write", "danger-full-access"])
    parser.add_argument("--timeout", type=float, default=float(os.environ.get("CODEX_AGENT_TIMEOUT_SECONDS", "600")))
    parser.add_argument("--oss", action="store_true")
    parser.add_argument("--local-provider", default="")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    return execute(build_parser().parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
