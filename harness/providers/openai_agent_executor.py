#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


API_URL = "https://api.openai.com/v1/responses"


def _read_stdin_json() -> dict:
    return json.loads(sys.stdin.read())


def _task_role_prompt(task: dict) -> str:
    path = task.get("role_prompt")
    if path and Path(str(path)).is_file():
        return Path(str(path)).read_text(encoding="utf-8")
    return ""


def _developer_prompt(task: dict) -> str:
    role_prompt = _task_role_prompt(task)
    return "\n".join(
        [
            "You are a harness agent executor.",
            "Return exactly one JSON object and no markdown.",
            "Do not change expected files, manifests, source files, or engine code.",
            "Every claim must cite evidence_ref from the provided task when possible.",
            "If evidence is insufficient, return a conservative JSON object that says so.",
            "",
            role_prompt,
        ]
    ).strip()


def _build_request(args: argparse.Namespace, task: dict) -> dict:
    payload: dict[str, Any] = {
        "model": args.model or os.environ.get("OPENAI_MODEL", ""),
        "input": [
            {"role": "developer", "content": _developer_prompt(task)},
            {"role": "user", "content": json.dumps(task, ensure_ascii=False, sort_keys=True)},
        ],
    }
    if args.max_output_tokens:
        payload["max_output_tokens"] = args.max_output_tokens
    reasoning_effort = args.reasoning_effort or os.environ.get("OPENAI_REASONING_EFFORT", "")
    if reasoning_effort:
        payload["reasoning"] = {"effort": reasoning_effort}
    return payload


def _extract_text(response: dict) -> str:
    if isinstance(response.get("output_text"), str):
        return response["output_text"]
    chunks: list[str] = []
    for item in response.get("output") or []:
        for content in item.get("content") or []:
            text = content.get("text")
            if isinstance(text, str):
                chunks.append(text)
    return "\n".join(chunks).strip()


def _parse_model_json(text: str) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start : end + 1])
        raise


def _error_output(agent: str, message: str) -> dict:
    return {
        "agent": agent,
        "schema_version": None,
        "category": "environment_defect",
        "reason": message,
        "evidence_ref": "openai_agent_executor",
    }


def execute(args: argparse.Namespace) -> int:
    task = _read_stdin_json()
    agent = str(task.get("agent") or "unknown")
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        print(json.dumps(_error_output(agent, "OPENAI_API_KEY is not set"), ensure_ascii=False))
        return 2
    payload = _build_request(args, task)
    if not payload.get("model"):
        print(json.dumps(_error_output(agent, "OpenAI model is not configured"), ensure_ascii=False))
        return 2
    base_url = (args.base_url or os.environ.get("OPENAI_BASE_URL") or API_URL).rstrip("/")
    url = base_url if base_url.endswith("/responses") else base_url + "/responses" if base_url.endswith("/v1") else base_url
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=args.timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
        output = _parse_model_json(_extract_text(body))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
        print(json.dumps(_error_output(agent, f"OpenAI executor failed: {exc}"), ensure_ascii=False))
        return 1
    if output.get("agent") is None:
        output["agent"] = agent
    if output.get("schema_version") is None:
        output["schema_version"] = 1
    print(json.dumps(output, ensure_ascii=False, sort_keys=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="OpenAI Responses API executor for harness agent tasks.")
    parser.add_argument("--model", default="", help="OpenAI API model id. Overrides OPENAI_MODEL.")
    parser.add_argument("--base-url", default="", help="Responses API URL or API base URL. Defaults to OpenAI.")
    parser.add_argument("--timeout", type=float, default=float(os.environ.get("OPENAI_TIMEOUT_SECONDS", "120")))
    parser.add_argument("--max-output-tokens", type=int, default=int(os.environ.get("OPENAI_MAX_OUTPUT_TOKENS", "2000")))
    parser.add_argument("--reasoning-effort", default="", help="Optional reasoning effort if supported by the selected model.")
    return parser


def main(argv: list[str] | None = None) -> int:
    return execute(build_parser().parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
