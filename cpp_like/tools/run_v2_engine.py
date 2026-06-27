#!/usr/bin/env python3
"""
run_v2_engine.py — 추출된 Low P-code JSON을 11_ BackwardSlice 엔진으로 돌려 expected와 대조.

11_tracing_Data_Origin_lowpcode 엔진 모듈을 그대로 import한다(소스 사본 없음).
phase1 러너가 `case_DFB*`만 글롭하므로, 여기서는 `case_TV2C*`를 글롭한다.

사용: python tools/run_v2_engine.py [input_dir] [expected_file]
기본 input_dir = samples/low_pcode , expected = expected/tv2_cpp_like.expected.json
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from tdo_paths import add_engine_to_syspath, ensure_engine_python  # noqa: E402

ensure_engine_python(ROOT)
add_engine_to_syspath(ROOT)

from analysis.interprocedural_summary import ProgramSliceGraphBuilder  # noqa: E402
from core.edge import DATA_CONTROL_SLICE_EDGES                          # noqa: E402
from query.backward_slice import BackwardSliceQuery                     # noqa: E402
from report.expected_validator import ExpectedValidator                # noqa: E402

HERE = Path(__file__).resolve().parents[1]


def main() -> int:
    input_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "samples" / "low_pcode"
    expected = Path(sys.argv[2]) if len(sys.argv) > 2 else HERE / "expected" / "tv2_cpp_like.expected.json"

    validator = ExpectedValidator(expected)
    builder = ProgramSliceGraphBuilder()

    rows, counts = [], {}
    for jp in sorted(input_dir.rglob("case_TV2*_low_pcode.json")):
        try:
            fg = builder.build_for_target(jp)
            q = BackwardSliceQuery(fg)
            actual, actual_ctrl = set(), set()
            for sink in fg.sink_index.values():
                actual.update(q.run(sink).source_labels)
                rc = BackwardSliceQuery(fg, DATA_CONTROL_SLICE_EDGES, mode="data+control").run(sink)
                actual_ctrl.update(rc.source_labels)
            actual_ctrl -= actual
            v = validator.validate(fg.function_name, actual, actual_ctrl)
            arch = fg.architecture.name
            verdict = v["verdict"]
        except Exception as exc:  # noqa: BLE001
            arch, verdict = "-", "ERROR"
            v = {"case_id": jp.name, "actual_sources": [], "actual_control_sources": [],
                 "forbidden_sources_found": [f"EXC:{exc}"], "missing_expected_sources": []}
        counts[verdict] = counts.get(verdict, 0) + 1
        rows.append((verdict, arch, v.get("case_id"), v.get("actual_sources"),
                     v.get("actual_control_sources"), v.get("forbidden_sources_found"),
                     v.get("missing_expected_sources")))

    print(f"{'verdict':8} {'arch':8} {'case':10} actual / control / forbidden_found / missing")
    print("-" * 100)
    for verdict, arch, cid, act, ctrl, forb, miss in rows:
        print(f"{verdict:8} {arch:8} {str(cid):10} {act} / {ctrl} / {forb} / {miss}")
    print("-" * 100)
    print("counts:", counts)
    return 1 if counts.get("FAIL") or counts.get("ERROR") else 0


if __name__ == "__main__":
    raise SystemExit(main())
