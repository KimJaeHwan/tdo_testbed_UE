#!/usr/bin/env python3
"""inspect_cut.py — 한 케이스의 backward slice가 어디서 멈췄는지(cut point) 출력.

cut point = slice traversal이 도달했지만 in-policy predecessor가 없어 더 못 거슬러 간 leaf 노드.
source까지 닿지 못한 FAIL의 '끊긴 지점'을 보여준다.

사용: python tools/inspect_cut.py <case_..._low_pcode.json>
"""
import sys
from pathlib import Path

ELEVENTH = Path("D:/01_gitproject/11_tracing_Data_Origin_lowpcode/trace_data_origin_lowpcode")
sys.path.insert(0, str(ELEVENTH))

from analysis.interprocedural_summary import ProgramSliceGraphBuilder  # noqa: E402
from query.backward_slice import BackwardSliceQuery                     # noqa: E402


def node_desc(graph, n):
    a = graph.nodes[n]
    return (a.get("display") or str(n), a.get("kind"), a.get("space"),
            a.get("opcode"), a.get("addr"))


def main():
    jp = Path(sys.argv[1])
    fg = ProgramSliceGraphBuilder().build_for_target(jp)
    g = fg.slice_graph
    q = BackwardSliceQuery(fg)

    print(f"### {fg.function_name}  ({fg.architecture.name})")
    print(f"sinks={len(fg.sink_index)} sources={len(fg.source_index)} nodes={g.number_of_nodes()}")
    if fg.warnings:
        print("warnings:", fg.warnings)

    for sink in fg.sink_index.values():
        r = q.run(sink)
        print(f"\n-- sink {g.nodes[sink].get('display', sink)} -->")
        print("  reached sources:", sorted(r.source_labels) or "(none)")
        # leaf = visited node with no in-policy predecessor
        leaves = []
        for n in r.visited:
            has_pred = any(g.edges[p, n].get("kind") in q.edge_policy for p in g.predecessors(n))
            if not has_pred and g.nodes[n].get("kind") != "source_boundary":
                leaves.append(n)
        print(f"  CUT POINTS (slice stopped, {len(leaves)}):")
        for n in leaves[:12]:
            disp, kind, space, op, addr = node_desc(g, n)
            print(f"    - {disp}  [kind={kind} space={space} op={op} @{addr}]")


if __name__ == "__main__":
    raise SystemExit(main())
