#!/usr/bin/env python3
"""verify_flows.py — 손으로 작성한 expected_flow/forbidden_flow의 정합성 검사.

객관적으로 확인 가능한 것만 검증한다(흐름의 '의도'가 맞는지는 사람 몫):
  1) cpp offset이 offsetof 계산값과 일치하는가
  2) 흐름의 source/carries 라벨이 끝점 정답(expected_/forbidden_)과 일관되는가
  3) 흐름이 source로 시작해 sink로 끝나는가, 알 수 없는 source 라벨은 없는가
"""
import json, re, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

# offsetof로 계산된 cpp 구조체 오프셋 (tail-path 기준)
CPP_OFF = {
    "Inner.Secret": 256, "Inner.Noise": 260, "Other": 264,
    "Transform.Translation.X": 268, "Transform.Rotation.Y": 284,
    "Fields[10]": 16424, "Fields[20]": 16464, "Secret": 0, "Noise": 4,
}
# UE에서 정수 offset이 안정적인 within-struct 필드
UE_OFF = {"Secret": 0, "Noise": 4, "ItemId": 0, "Count": 4, "X": 0, "Y": 8, "Z": 16}

def tail(field):
    f = field.split("/")[0].strip()          # "A.Other / B.Other" -> "A.Other"
    parts = f.split(".")
    return ".".join(parts[1:]) if len(parts) > 1 else parts[0]

def base(label):  # "dfb_source_A.ret" -> "dfb_source_A"
    return label.split(".")[0]

def check(manifest_path, layer):
    d = json.load(open(manifest_path, encoding="utf-8"))
    errs = []
    for c in d["cases"]:
        cid = c["id"]
        ef = c.get("expected_flow") or []
        ff = c.get("forbidden_flow") or []
        if not ef:
            errs.append(f"{cid}: expected_flow 없음"); continue
        if ef[0].get("op") != "source": errs.append(f"{cid}: 첫 step이 source 아님")
        if ef[-1].get("op") != "sink":   errs.append(f"{cid}: 마지막 step이 sink 아님")

        exp = {base(x) for x in c.get("expected_data_sources",[])+c.get("expected_control_sources",[])}
        forb = {base(x) for x in c.get("forbidden_data_sources",[])+c.get("forbidden_control_sources",[])}

        # source 라벨 일관성
        for s in ef:
            if s.get("op") == "source":
                b = base(s["label"])
                if b not in exp:
                    errs.append(f"{cid}: flow source {b} 가 expected_*에 없음")
            for key in ("carries",):
                if key in s and base(s[key]) not in {"dfb_source_A","dfb_source_B","dfb_source_C"}:
                    errs.append(f"{cid}: 알 수 없는 carries {s[key]}")
        # expected_data_source가 flow에 등장하는가
        for ds in c.get("expected_data_sources",[]):
            b = base(ds)
            seen = any(st.get("carries")==b or base(st.get("label","")) == b for st in ef)
            if not seen: errs.append(f"{cid}: expected_data_source {b} 가 flow에 안 나타남")
        # forbidden_flow carries가 forbidden 끝점과 일치
        for s in ff:
            if "carries" in s and base(s["carries"]) not in forb:
                errs.append(f"{cid}: forbidden_flow carries {s['carries']} 가 forbidden_*에 없음")

        # offset 검증
        OFF = CPP_OFF if layer=="cpp" else UE_OFF
        for s in ef+ff:
            off = s.get("offset")
            fld = s.get("field")
            if isinstance(off,int) and fld:
                t = tail(fld)
                if t in OFF and OFF[t] != off:
                    errs.append(f"{cid}: offset 불일치 {fld} -> {off} (정답 {OFF[t]})")
    return errs

total = 0
for mp, layer in [("cpp_like/manifests/cases_v2_manifest.json","cpp"),
                  ("unreal_playground/manifests/cases_v2_manifest.json","ue")]:
    e = check(ROOT/mp, layer)
    total += len(e)
    print(f"=== {mp} ({layer}) ===")
    print("\n".join("  ✗ "+x for x in e) if e else "  ✓ 통과 (offset·일관성 이상 없음)")
print(f"\n총 오류: {total}")
sys.exit(1 if total else 0)
