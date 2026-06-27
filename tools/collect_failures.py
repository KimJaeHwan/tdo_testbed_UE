#!/usr/bin/env python3
"""collect_failures.py — 빌드 변형별로 전 케이스를 11_엔진에 돌려 verdict + cut point 수집.
사용: python tools/collect_failures.py  (변형 목록은 하단 VARIANTS)"""
import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from tdo_paths import add_engine_to_syspath, ensure_engine_python

ensure_engine_python(ROOT)
add_engine_to_syspath(ROOT)
from analysis.interprocedural_summary import ProgramSliceGraphBuilder
from core.edge import DATA_CONTROL_SLICE_EDGES
from query.backward_slice import BackwardSliceQuery
from report.expected_validator import ExpectedValidator

VARIANTS = [
    ("tier0-P0-x64",    "cpp_like/samples/low_pcode/x64",    "cpp_like/expected/tv2_cpp_like.expected.json"),
    ("tier0-P0-x86",    "cpp_like/samples/low_pcode/x86",    "cpp_like/expected/tv2_cpp_like.expected.json"),
    ("tier0-P0-armv7",  "cpp_like/samples/low_pcode/armv7",  "cpp_like/expected/tv2_cpp_like.expected.json"),
    ("tier0-P0-aarch64","cpp_like/samples/low_pcode/aarch64","cpp_like/expected/tv2_cpp_like.expected.json"),
    ("tier0-P1-x64",    "cpp_like/samples/low_pcode/P1_x64", "cpp_like/expected/tv2_cpp_like.expected.json"),
    ("ue-Dev-x64",      "unreal_playground/TraceUnrealPlayground/samples/low_pcode",    "unreal_playground/expected/tv2_unreal.expected.json"),
    ("ue-DebugGame-x64","unreal_playground/TraceUnrealPlayground/samples/low_pcode_P0", "unreal_playground/expected/tv2_unreal.expected.json"),
]

def cut_points(fg, q, sink):
    r = q.run(sink); g = fg.slice_graph
    leaves = []
    for n in r.visited:
        if any(g.edges[p, n].get("kind") in q.edge_policy for p in g.predecessors(n)):
            continue
        a = g.nodes[n]
        if a.get("kind") == "source_boundary":
            continue
        op = a.get("opcode") or a.get("kind")
        parts = str(n).split(":")
        base = parts[-3] if len(parts) >= 3 else (parts[0] if parts else str(n))
        leaves.append(f"{op}:{base}")
    return leaves

def run_variant(label, indir, expf):
    indir, expf = ROOT / indir, ROOT / expf
    if not indir.exists():
        return {"label": label, "error": "no samples"}
    val = ExpectedValidator(expf); b = ProgramSliceGraphBuilder()
    cases = {}
    for jp in sorted(indir.rglob("case_TV2*_low_pcode.json")):
        try:
            fg = b.build_for_target(jp); q = BackwardSliceQuery(fg)
            act, ctrl, cuts = set(), set(), []
            for sink in fg.sink_index.values():
                act |= q.run(sink).source_labels
                ctrl |= BackwardSliceQuery(fg, DATA_CONTROL_SLICE_EDGES, mode="data+control").run(sink).source_labels
                cuts += cut_points(fg, q, sink)
            ctrl -= act
            v = val.validate(fg.function_name, act, ctrl)
            cid = v.get("case_id") or jp.name
            cases[cid] = {"verdict": v["verdict"],
                          "missing": v.get("missing_expected_sources", []) + v.get("missing_expected_control_sources", []),
                          "forbidden_found": v.get("forbidden_sources_found", []) + v.get("forbidden_control_sources_found", []),
                          "cut": sorted(set(cuts)) if v["verdict"] != "PASS" else []}
        except Exception as e:
            cases[jp.name] = {"verdict": "ERROR", "error": str(e)[:120]}
    pc = sum(1 for c in cases.values() if c["verdict"] == "PASS")
    fp = sum(1 for c in cases.values() if c.get("forbidden_found"))
    return {"label": label, "pass": pc, "fail": len(cases) - pc, "false_pos": fp, "cases": cases}

out = [run_variant(*v) for v in VARIANTS]
(ROOT / "dist").mkdir(exist_ok=True)
(ROOT / "dist" / "failure_report.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
for r in out:
    if "error" in r: print(f"{r['label']:20} (skip: {r['error']})"); continue
    print(f"{r['label']:20} PASS {r['pass']:2}  FAIL {r['fail']:2}  FP {r['false_pos']}")
print("\n[saved] dist/failure_report.json")
