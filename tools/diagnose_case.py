#!/usr/bin/env python3
"""diagnose_case.py — 한 케이스의 backward slice를 storage 키까지 전부 덤프(증거 수집용).
사용: python tools/diagnose_case.py <case_..._low_pcode.json>
출력: 도달한 source, 끝까지 못 간 cut leaf(키 포함), sink→source 경로의 edge(양끝 storage)."""
import sys
from pathlib import Path
sys.path.insert(0, "D:/01_gitproject/11_tracing_Data_Origin_lowpcode/trace_data_origin_lowpcode")
from analysis.interprocedural_summary import ProgramSliceGraphBuilder
from query.backward_slice import BackwardSliceQuery

def desc(g, n):
    a = g.nodes[n]
    bits = [a.get("opcode") or a.get("kind")]
    if a.get("storage"): bits.append(a["storage"])
    if a.get("source_label"): bits.append(f"SOURCE={a['source_label']}")
    return " | ".join(str(b) for b in bits)

def main():
    jp = Path(sys.argv[1])
    fg = ProgramSliceGraphBuilder().build_for_target(jp)
    g = fg.slice_graph
    q = BackwardSliceQuery(fg)
    print(f"### {fg.function_name}  arch={fg.architecture.name}")
    for sink in fg.sink_index.values():
        r = q.run(sink)
        srcs = sorted(r.source_labels)
        print(f"\nSINK {desc(g,sink)}")
        print(f"  reached sources: {srcs or '(none)'}")
        # cut leaves
        print("  CUT LEAVES (no in-policy predecessor):")
        for n in r.visited:
            if any(g.edges[p,n].get('kind') in q.edge_policy for p in g.predecessors(n)): continue
            if g.nodes[n].get('kind') == 'source_boundary': continue
            print(f"    - {desc(g,n)}")
        # 전체 reached 서브그래프 edge (sink에서 BFS 순서로)
        print("  REACHED SUBGRAPH (pred --[kind]--> node):")
        from collections import deque
        seen=set([sink]); dq=deque([sink]); order=[]
        while dq:
            n=dq.popleft()
            for p in g.predecessors(n):
                if g.edges[p,n].get('kind') not in q.edge_policy: continue
                order.append((p,n,g.edges[p,n].get('kind')))
                if p not in seen: seen.add(p); dq.append(p)
        for p,n,k in order[:40]:
            print(f"    {desc(g,p)}  --[{k}]-->  {desc(g,n)}")

if __name__ == "__main__":
    main()
