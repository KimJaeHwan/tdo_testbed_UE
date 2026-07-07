#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from harness.config import ROOT


def _read_stdin_json() -> dict:
    raw = sys.stdin.read().strip()
    return json.loads(raw) if raw else {}


def _existing_case_ids() -> set[str]:
    found: set[str] = set()
    for path in (
        ROOT / "cpp_like" / "manifests" / "cases_v2_manifest.json",
        ROOT / "unreal_playground" / "manifests" / "cases_v2_manifest.json",
        ROOT.parent / "tdo_testbed_Obf" / "manifests" / "cases_obf_manifest.json",
    ):
        if not path.is_file():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        for row in payload.get("cases") or []:
            if isinstance(row, dict) and row.get("id"):
                found.add(str(row["id"]))
    for path in (ROOT / "cpp_like" / "src" / "cases_fusion.cpp",):
        if path.is_file():
            found.update(re.findall(r"\bTV2C\d{3}\b", path.read_text(encoding="utf-8")))
    obf_source = ROOT.parent / "tdo_testbed_Obf" / "src" / "cases_basic_obf.c"
    if obf_source.is_file():
        found.update(re.findall(r"\bOBF\d{3}\b", obf_source.read_text(encoding="utf-8")))
    return found


def _next_cpp_case_ids(count: int, requested: str = "") -> list[str]:
    existing = _existing_case_ids()
    numbers = [
        int(match.group(1))
        for case_id in existing
        for match in [re.match(r"TV2C(\d{3})$", case_id)]
        if match
    ]
    if requested:
        match = re.match(r"TV2C(\d{3})$", requested)
        next_number = int(match.group(1)) if match else max(numbers or [604]) + 1
    else:
        next_number = max(numbers or [604]) + 1

    case_ids: list[str] = []
    while len(case_ids) < max(1, count):
        candidate = f"TV2C{next_number:03d}"
        if candidate not in existing and candidate not in case_ids:
            case_ids.append(candidate)
        next_number += 1
    return case_ids


def _next_obf_case_ids(count: int, requested: str = "") -> list[str]:
    existing = _existing_case_ids()
    numbers = [
        int(match.group(1))
        for case_id in existing
        for match in [re.match(r"OBF(\d{3})$", case_id)]
        if match
    ]
    if requested:
        match = re.match(r"OBF(\d{3})$", requested)
        next_number = int(match.group(1)) if match else max(numbers or [7]) + 1
    else:
        next_number = max(numbers or [7]) + 1

    case_ids: list[str] = []
    while len(case_ids) < max(1, count):
        candidate = f"OBF{next_number:03d}"
        if candidate not in existing and candidate not in case_ids:
            case_ids.append(candidate)
        next_number += 1
    return case_ids


def _cpp_case(case_id: str) -> dict:
    lower = case_id.lower()
    function = f"case_{case_id}_offline_indirect_field_loop_guard"
    name = "offline indirect callback field loop guard"
    source = f"""
/* {case_id} - Offline local case-author seed.
 *           expect A / forbid B,C
 */
struct {case_id}_Cell {{
    int target;
    int neighbor;
    int killed;
}};

struct {case_id}_Box {{
    {case_id}_Cell cells[2];
    int guard;
}};

typedef void (*{case_id}_Writer)({case_id}_Box*, int, int);

TV2_HELPER void {lower}_write_target({case_id}_Box *box, int value, int noise) {{
    box->cells[1].target = value;
    box->cells[0].neighbor = noise;
}}

TV2_HELPER void {lower}_overwrite_neighbor({case_id}_Box *box, int value) {{
    box->cells[1].neighbor = value;
}}

TV2_CASE void {function}(void) {{
    {case_id}_Box box = {{}};
    {case_id}_Writer writers[2] = {{
        {lower}_write_target,
        {lower}_write_target,
    }};
    int a = dfb_source_A();
    int b = dfb_source_B();
    int c = dfb_source_C();

    for (int i = 0; i < 2; ++i) {{
        box.cells[i].neighbor = b + i;
    }}

    writers[(c & 1) ^ (c & 1)](&box, a, c);
    {lower}_overwrite_neighbor(&box, b);
    box.cells[1].killed = c;

    dfb_sink_int(box.cells[1].target);
}}
""".strip()
    expected = {
        "tier": 0,
        "severity": "proposed-regression",
        "binary": "tv2_cpp_like",
        "name": name,
        "function": function,
        "source_file": "src/cases_fusion.cpp",
        "anchor": {"callee": "dfb_sink_int", "arg_index": 0, "storage": "test-wrapper-only"},
        "expected_data_sources": ["dfb_source_A.ret"],
        "expected_control_sources": [],
        "expected_global_sources": [],
        "forbidden_data_sources": ["dfb_source_B.ret", "dfb_source_C.ret"],
        "forbidden_control_sources": [],
        "expected_features": [
            "fusion",
            "offline-local-case-author",
            "indirect-call",
            "callback-table",
            "field-sensitive-memory",
            "loop-noise",
            "neighbor-field-forbidden",
            "overwrite-distraction",
        ],
        "allowed_warnings": [],
    }
    expected["manifest_case"] = {"id": case_id, **expected}
    return {
        "id": case_id,
        "tier": 0,
        "target": "suite10-cpp",
        "cpp_or_ue": source,
        "expected": expected,
        "expected_flow": [
            {
                "kind": "source",
                "node": "dfb_source_A.ret",
                "function": function,
                "field": "local a",
                "offset": "n/a",
                "size": "4",
                "carries": "dfb_source_A.ret",
                "source": "dfb_source_A.ret",
                "sink": "dfb_sink_int.arg0",
                "from": "dfb_source_A()",
                "to": "callback value argument",
                "reason": "By construction, A is passed to the selected callback value parameter.",
            },
            {
                "kind": "field_store",
                "node": f"{lower}_write_target",
                "function": function,
                "field": f"{case_id}_Box.cells[1].target",
                "offset": "offsetof(Box.cells[1].target)",
                "size": "4",
                "carries": "dfb_source_A.ret",
                "source": "dfb_source_A.ret",
                "sink": "dfb_sink_int.arg0",
                "from": "callback value argument",
                "to": "box.cells[1].target",
                "reason": "The callback writes only the value parameter into the target field read by the sink.",
            },
        ],
        "forbidden_flow": [
            {
                "kind": "neighbor_store",
                "node": "loop neighbor writes",
                "function": function,
                "field": f"{case_id}_Box.cells[*].neighbor",
                "offset": "offsetof(Box.cells[*].neighbor)",
                "size": "4",
                "carries": "dfb_source_B.ret",
                "source": "dfb_source_B.ret",
                "sink": "dfb_sink_int.arg0",
                "from": "dfb_source_B()",
                "to": "neighbor fields only",
                "reason": "B is written to neighbor fields and never to cells[1].target.",
            },
            {
                "kind": "killed_field",
                "node": "box.cells[1].killed",
                "function": function,
                "field": f"{case_id}_Box.cells[1].killed",
                "offset": "offsetof(Box.cells[1].killed)",
                "size": "4",
                "carries": "dfb_source_C.ret",
                "source": "dfb_source_C.ret",
                "sink": "dfb_sink_int.arg0",
                "from": "dfb_source_C()",
                "to": "index/noise/killed field",
                "reason": "C selects a callback through an expression that cancels to zero and is written away from the sink field.",
            },
        ],
        "oracle_basis": (
            "By construction, only dfb_source_A reaches cells[1].target. "
            "B is confined to neighbor fields, and C is confined to callback selection/noise/killed fields."
        ),
        "independent_check": (
            "Local deterministic proposal; compile and targeted regression are required before promotion. "
            "The generated case is intentionally proposed-regression only."
        ),
    }


def _obf_case(case_id: str) -> dict:
    lower = case_id.lower()
    function = f"case_{case_id}_opaque_indirect_field_store"
    name = "opaque indirect field store"
    source = f"""
/* {case_id} - Offline local Suite12 case-author seed.
 *           expect A / forbid B,C
 */
typedef struct {case_id}_Cell {{
    int live;
    int noise;
    int killed;
}} {case_id}_Cell;

typedef void (*{case_id}_writer_fn)({case_id}_Cell *, int, int);

DFB_HELPER void {lower}_store_live({case_id}_Cell *cell, int value, int noise) {{
    cell->live = obf_identity_i32(value);
    cell->noise = obf_identity_i32(noise);
}}

DFB_HELPER void {lower}_kill_noise({case_id}_Cell *cell, int value) {{
    cell->noise = obf_identity_i32(value);
    cell->killed = value ^ value;
}}

DFB_CASE void {function}(void) {{
    {case_id}_Cell cells[2] = {{{{0}}}};
    {case_id}_writer_fn writer = {lower}_store_live;
    int a = dfb_source_A();
    int b = dfb_source_B();
    int c = dfb_source_C();

    for (int i = 0; i < 2; ++i) {{
        cells[i].noise = obf_identity_i32(b + i);
    }}

    if (obf_opaque_true()) {{
        writer(&cells[1], a, c);
    }} else {{
        writer(&cells[0], b, c);
    }}
    {lower}_kill_noise(&cells[1], b);
    cells[0].live = obf_identity_i32(c);

    dfb_sink_int(cells[1].live);
}}
""".strip()
    manifest_case = {
        "id": case_id,
        "name": name,
        "binary": "dfbench_obf_basic",
        "source_file": "src/cases_basic_obf.c",
        "function": function,
        "anchor": {"callee": "dfb_sink_int", "arg_index": 0},
        "expected_sources": ["dfb_source_A.ret"],
        "forbidden_sources": ["dfb_source_B.ret", "dfb_source_C.ret"],
        "expected_features": [
            "obfuscation",
            "offline-local-case-author",
            "opaque_predicate",
            "indirect-call",
            "field-sensitive-memory",
            "loop-noise",
            "strong-update-distraction",
        ],
        "allowed_warnings": [],
        "severity": "proposed-regression",
    }
    return {
        "id": case_id,
        "tier": 0,
        "target": "suite12-obf",
        "cpp_or_ue": source,
        "expected": {**manifest_case, "manifest_case": manifest_case},
        "expected_flow": [
            {
                "kind": "source",
                "node": "dfb_source_A.ret",
                "function": function,
                "field": "local a",
                "carries": "dfb_source_A.ret",
                "source": "dfb_source_A.ret",
                "sink": "dfb_sink_int.arg0",
                "reason": "A is the value stored by the selected writer into cells[1].live.",
            },
            {
                "kind": "field_store",
                "node": f"{lower}_store_live",
                "function": function,
                "field": f"{case_id}_Cell.live",
                "carries": "dfb_source_A.ret",
                "source": "dfb_source_A.ret",
                "sink": "dfb_sink_int.arg0",
                "reason": "The sink reads cells[1].live after the opaque-true branch stores A there.",
            },
        ],
        "forbidden_flow": [
            {
                "kind": "noise_field",
                "node": "loop noise writes",
                "function": function,
                "field": f"{case_id}_Cell.noise",
                "carries": "dfb_source_B.ret",
                "source": "dfb_source_B.ret",
                "sink": "dfb_sink_int.arg0",
                "reason": "B is confined to noise/killed fields and a branch that is unreachable by construction.",
            },
            {
                "kind": "dead_field",
                "node": "cells[0].live",
                "function": function,
                "field": "cells[0].live",
                "carries": "dfb_source_C.ret",
                "source": "dfb_source_C.ret",
                "sink": "dfb_sink_int.arg0",
                "reason": "C is written to cells[0].live, while the sink reads cells[1].live.",
            },
        ],
        "oracle_basis": (
            "obf_opaque_true is mathematically true for n*(n+1), so only A is stored into cells[1].live. "
            "B and C are confined to other fields or other elements."
        ),
        "independent_check": (
            "Local deterministic Suite12 proposal; OLLVM build, low-pcode extraction, and targeted regression are required before promotion."
        ),
    }


def _target_from_task(task: dict, requested: str) -> str:
    if requested:
        return requested
    payload = task.get("input") if isinstance(task.get("input"), dict) else {}
    report = payload.get("report") if isinstance(payload.get("report"), list) else []
    suites = {str(row.get("suite") or "") for row in report if isinstance(row, dict)}
    gap_note = str(payload.get("gap_note") or "").lower()
    if any("12_tdo_testbed_obf" in suite.lower() for suite in suites) or "suite12" in gap_note or "obf" in gap_note:
        return "suite12-obf"
    return "suite10-cpp"


def execute(args: argparse.Namespace) -> int:
    task = _read_stdin_json()
    if isinstance(task, list):
        task = task[0] if task else {}
    if str(task.get("agent") or "") != "case_author":
        print(
            json.dumps(
                {
                    "agent": task.get("agent") or "unknown",
                    "schema_version": 1,
                    "category": "unsupported",
                    "reason": "local_case_author_executor only handles case_author tasks",
                    "evidence_ref": "local_case_author_executor",
                },
                ensure_ascii=False,
            )
        )
        return 2
    target = _target_from_task(task, args.target)
    if target == "suite12-obf":
        proposed = [_obf_case(case_id) for case_id in _next_obf_case_ids(args.max_cases, args.case_id)]
    else:
        proposed = [_cpp_case(case_id) for case_id in _next_cpp_case_ids(args.max_cases, args.case_id)]
    print(
        json.dumps(
            {
                "agent": "case_author",
                "schema_version": 1,
                "proposed_cases": proposed,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Deterministic local case_author provider for offline frontier-loop smoke.")
    parser.add_argument("--max-cases", type=int, default=1)
    parser.add_argument("--case-id", default="")
    parser.add_argument("--target", choices=["suite10-cpp", "suite12-obf"], default="")
    return parser


def main(argv: list[str] | None = None) -> int:
    return execute(build_parser().parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
