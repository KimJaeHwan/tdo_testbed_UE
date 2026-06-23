#!/usr/bin/env python3
"""render_flows.py — manifest의 expected_flow/forbidden_flow를 사람이 읽는 흐름도(dist/flows.md)로 렌더.
릴리스 첨부용. 케이스별 source→sink 경로 + 거치면 안 되는 경유점을 보여준다."""
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "dist"; OUT.mkdir(exist_ok=True)

def off(s):
    o = s.get("offset")
    return f"@{o}" if isinstance(o, int) else (f"@{o}" if o else "")

def step_line(s):
    op = s.get("op")
    if op == "source": return f"source {s['label']}" + (f"  ({s['role']})" if s.get("role") else "")
    if op == "sink":   return f"sink {s['label']}"
    if op == "store":  return f"store {s.get('field','')} {off(s)} (carries {s.get('carries','')})" + (f"  [{s['detail']}]" if s.get('detail') else "") + (f"  branch={s['branch']}" if s.get('branch') else "")
    if op == "load":   return f"load {s.get('field','')} {off(s)}" + (f"  [{s['detail']}]" if s.get('detail') else "")
    if op == "copy":   return f"copy [{s.get('edge')}]  {s.get('detail','')}"
    if op == "phi":    return f"phi {s.get('field','')} {off(s)}  {s.get('note','')}"
    if op == "deref":  return f"deref  {s.get('detail','')}"
    if op == "call_out_mem": return f"call_out_mem  {s.get('detail','')}"
    if op == "branch_cond":  return f"branch_cond (carries {s.get('carries','')})  {s.get('note','')}"
    return f"{op}  {s}"

def fb_line(s):
    return f"✗ {s.get('node','')} {s.get('field','')} {off(s)} (carries {s.get('carries','')}) — {s.get('reason','')}"

def render(manifest, title):
    d = json.load(open(manifest, encoding="utf-8"))
    L = [f"## {title}", ""]
    for c in d["cases"]:
        L.append(f"### {c['id']} {c.get('name','')}  [{c.get('severity','')}]")
        ed = ", ".join(c.get("expected_data_sources",[])) or "-"
        ec = ", ".join(c.get("expected_control_sources",[]))
        fb = ", ".join(c.get("forbidden_data_sources",[])) or "-"
        L.append(f"- expected data: `{ed}`" + (f" | control: `{ec}`" if ec else "") + f" | forbidden: `{fb}`")
        L.append("")
        L.append("```")
        flow = c.get("expected_flow") or []
        for i, s in enumerate(flow):
            prefix = "  " + ("└→ " if i else "")
            L.append(prefix + step_line(s))
        for s in (c.get("forbidden_flow") or []):
            L.append("  " + fb_line(s))
        L.append("```")
        L.append("")
    return "\n".join(L)

doc = ["# Testbed V2 — 케이스별 데이터 흐름 (정답 경로)", "",
       "> 각 케이스의 **의도된 slice 흐름**(source→sink 경유점)과 **거치면 안 되는 경유점**(✗).",
       "> 저자가 소스코드 기반으로 작성. offset은 cpp=정확(offsetof), UE=pdb/heap(빌드결정).",
       "> 자세한 원리는 docs/expected_generation.md 참조.", ""]
doc.append(render(ROOT/"cpp_like/manifests/cases_v2_manifest.json", "Tier 0 — Pure C++ Fusion"))
doc.append(render(ROOT/"unreal_playground/manifests/cases_v2_manifest.json", "Tier 2/3 — Unreal USTRUCT / Container"))
(OUT/"flows.md").write_text("\n".join(doc), encoding="utf-8")
print(f"[generated] {OUT/'flows.md'}")
