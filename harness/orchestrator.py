#!/usr/bin/env python3
"""
orchestrator.py — 하니스 결정적 control loop (설계 A §3).

이것은 스켈레톤이다. 결정적 control flow는 완성형이고, LLM 호출(agent())과
실제 빌드/추출 연결부는 STUB로 두어 GPT5.5가 자기 에이전트 런타임에 배선한다.
LLM은 판단 노드(triage/diagnose/adversary/fix/author)에만 들어간다(A §P1).
"""
from __future__ import annotations
import subprocess, json
from pathlib import Path
from gates import objective_vector, objective_improves, regression_ok, oracle_locked, INVARIANTS
from memory.store import Memory   # harness/memory/store.py (스켈레톤)

ROOT = Path(__file__).resolve().parents[1]


# ── 결정적 층 (A §2 Test Runner) — 기존 도구 호출만 한다 (A §8) ──────────────
def run_tests(changed_only: bool = True) -> dict:
    """build → ghidra 추출(변경분만) → 엔진 실행 → expected diff.
    산출: dist/failure_report.json 파싱 결과(verdict/missing/forbidden_found/cut)."""
    # STUB 배선: 입력 해시 비교로 changed_only 캐시 스킵(A §P5, artifact_cache)
    subprocess.run(["bash", str(ROOT / "build.sh"), "all"], check=False)
    # extract는 변경된 바이너리만 (artifact_cache 키 = source/commit hash)
    subprocess.run(["python", str(ROOT / "tools" / "collect_failures.py")], check=False)
    return json.loads((ROOT / "dist" / "failure_report.json").read_text(encoding="utf-8"))


def flatten_failures(report: list[dict]) -> list[dict]:
    out = []
    for variant in report:
        for cid, c in variant.get("cases", {}).items():
            if c.get("verdict") != "PASS":
                out.append({"variant": variant["label"], "case": cid, **c})
    return out


# ── 에이전트 호출 STUB (GPT5.5 런타임에 배선) ────────────────────────────────
def agent(role: str, payload: dict) -> dict:
    """role ∈ {triage,diagnose,adversary,engine_fix,case_author,memory_synth}.
    계약(I/O 스키마·규칙)은 harness/agents/<role>.md. 반드시 그 스키마로 반환."""
    raise NotImplementedError(f"wire agent({role}) to LLM runtime per harness/agents/{role}.md")


def adversary_panel(kind: str, subject: dict, n: int = 3) -> bool:
    """서로 다른 렌즈(correctness/regression/fp_risk)로 독립 반박. 다수결 통과 여부 (A §P2)."""
    lenses = ["correctness", "regression", "fp_risk"][:n]
    votes = [agent("adversary", {"kind": kind, "subject": subject, "lens": L}) for L in lenses]
    # 각 표는 {"refuted": bool, "evidence_ref": ...}. 증거 없는 confirm은 무효(refuted 취급).
    confirms = [v for v in votes if not v.get("refuted") and v.get("evidence_ref")]
    return len(confirms) > n // 2


# ── 메인 루프 (A §3) ─────────────────────────────────────────────────────────
def loop(mem: Memory, max_iter: int = 100):
    for it in range(max_iter):
        report = run_tests(changed_only=True)

        # 불변검사 I1: 크래시 0 (A §5). 아니면 멈춤·에스컬레이트 — 절대 무시 금지.
        crashes = [c for v in report for cid, c in v.get("cases", {}).items() if c["verdict"] == "ERROR"]
        if crashes:
            mem.escalate("crash", crashes); return "ESCALATE: analysis ERROR(I1) — 사람 확인 필요"

        failures = flatten_failures(report)
        if done(report):
            return "DONE"  # A §7 종료조건

        for f in failures:
            tri = agent("triage", {"failure": f, "capability_map": mem.capability_map()})
            if tri["category"] != "engine_defect":
                mem.route(f, tri); continue  # harness_defect/frontier/env_artifact

            diag = agent("diagnostician", {"failure": f})   # 증거 인용 필수(계약)
            if not diag.get("evidence_ref") or not adversary_panel("diagnosis", diag):
                mem.mark_refuted(diag); continue            # A §P2

            fix = agent("engine_fixer", {"diagnosis": diag, "isolation": "worktree"})  # 11_ 격리
            if not adversary_panel("fix", fix):
                mem.discard(fix); continue

            # 결정적 게이트 (A §5 불변식·목적함수)
            after = run_tests(changed_only=False)           # 전수 회귀
            if not oracle_locked(ROOT):                     # I4: 오라클 미변경
                mem.escalate("oracle_touched", fix); return "ESCALATE: 오라클 변경 감지(I4)"
            if regression_ok(report, after) and objective_improves(report, after):
                mem.merge(fix, diag, votes=True);
            else:
                mem.discard(fix)                            # 회귀/FP/목적함수 미개선 → 폐기

        # 갭/frontier 기반 신규 케이스 (오라클은 휴먼 게이트, A §P3/§P7)
        gaps = agent("case_author", {"capability_map": mem.capability_map(), "report": report})
        for c in gaps.get("proposed_cases", []):
            mem.queue_for_human_approval(c)                 # 오라클 by-construction 검토 후 적용
        mem.update_capability_map(report)
    return "MAX_ITER"


def done(report) -> bool:
    """A §7: FP=0 AND P0/DebugGame PASS 목표 AND frontier 문서화."""
    fp = sum(1 for v in report for c in v["cases"].values() if c.get("forbidden_found"))
    return fp == 0 and _pass_targets_met(report) and _frontier_documented()


def _pass_targets_met(report) -> bool: ...   # STUB: P0/DebugGame 목표치 비교
def _frontier_documented() -> bool: ...       # STUB: capability_map의 frontier 항목 문서화 확인


if __name__ == "__main__":
    print(loop(Memory(ROOT / "harness" / "memory")))
