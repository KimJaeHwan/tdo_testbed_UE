#!/usr/bin/env python3
"""
generate_expected_from_manifest.py — Testbed V2 정답 JSON 생성기

cases_v2_manifest.json(단일 진실 원본)을 읽어 바이너리별 *.expected.json을 생성한다.
스키마는 11_tracing_Data_Origin_lowpcode V8 §24 (data/control/global source 분리)를 따른다.
09식 expected_sources/forbidden_sources도 호환 처리한다.

사용법:
  python tools/generate_expected_from_manifest.py

주의: expected JSON을 직접 수정하지 말 것. manifest 수정 후 재실행하면 덮어쓴다.
"""

import json
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "manifests" / "cases_v2_manifest.json"


def _get(case, key, default):
    """09 호환: expected_sources -> expected_data_sources 등으로 흡수."""
    if key in case:
        return case[key]
    if key == "expected_data_sources" and "expected_sources" in case:
        return case["expected_sources"]
    if key == "forbidden_data_sources" and "forbidden_sources" in case:
        return case["forbidden_sources"]
    return default


def main():
    with open(MANIFEST_PATH, encoding="utf-8") as f:
        manifest = json.load(f)

    binary_meta = {b["name"]: b for b in manifest["binaries"]}
    cases_by_binary = defaultdict(list)
    for case in manifest["cases"]:
        cases_by_binary[case["binary"]].append(case)

    for binary_name, meta in binary_meta.items():
        cases = cases_by_binary.get(binary_name, [])
        output = {
            "schema_version": 2,
            "program": binary_name,
            "generated_from": "manifests/cases_v2_manifest.json",
            "arch_variants": meta.get("arch_variants", []),
            "cases": [],
        }

        for case in cases:
            entry = {
                "id": case["id"],
                "binary": binary_name,
                "tier": case.get("tier"),
                "severity": case.get("severity"),
                "function": case["function"],
                "anchor": case["anchor"],
                "expected_data_sources": _get(case, "expected_data_sources", []),
                "expected_control_sources": _get(case, "expected_control_sources", []),
                "expected_global_sources": _get(case, "expected_global_sources", []),
                "forbidden_data_sources": _get(case, "forbidden_data_sources", []),
                "forbidden_control_sources": _get(case, "forbidden_control_sources", []),
                "expected_features": case.get("expected_features", []),
                "allowed_warnings": case.get("allowed_warnings", []),
            }
            # 중간 slice 흐름(정답 경로). 끝점뿐 아니라 의도된 경유점을 오라클에 박는다.
            # source→sink 순서. field/semantic 라벨은 overlay 힌트이고, 핵심은
            # op/edge/size/carries(어느 source를 실어 나르는지) + 순서다.
            for opt in ("expected_flow", "forbidden_flow", "expected_edge_kinds",
                        "expected_memory_ranges", "forbidden_memory_ranges"):
                if opt in case:
                    entry[opt] = case[opt]
            output["cases"].append(entry)

        out_path = ROOT / meta["expected_file"]
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps(output, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"[generated] {meta['expected_file']}  ({len(cases)} cases)")

    print("[done] expected JSON generation complete.")


if __name__ == "__main__":
    main()
