"""
store.py — 외부 메모리 원장 접근 스켈레톤 (schema.json 구현체).
JSON 파일/​sqlite 어느 쪽으로 구현해도 됨. 여기선 인터페이스만 정의(STUB).
각 메서드는 schema.json의 해당 원장을 읽고/쓴다. 에이전트는 필요한 슬라이스만 조회.
"""
from __future__ import annotations
from pathlib import Path


class Memory:
    def __init__(self, base: Path):
        self.base = Path(base)

    # 조회 (에이전트가 필요한 슬라이스만)
    def capability_map(self) -> dict: ...
    def history(self, case: str) -> list: ...          # failure_ledger 슬라이스
    def known_root_cause(self, case: str) -> dict | None: ...

    # hypothesis_ledger (신뢰의 원장, A §P2)
    def mark_refuted(self, diagnosis: dict): ...
    def mark_confirmed(self, diagnosis: dict, votes: dict): ...

    # decision_log / 수정 결과
    def merge(self, fix: dict, diagnosis: dict, votes: bool): ...   # decision_log 기록 + 상태 fixed
    def discard(self, fix: dict): ...

    # 라우팅 / 캐시 / 갱신
    def route(self, failure: dict, triage: dict): ...   # harness_defect/frontier/env_artifact
    def update_capability_map(self, report: list): ...
    def queue_for_human_approval(self, case: dict): ...  # 오라클 by-construction (A §P7)

    # 에스컬레이션 (A §7)
    def escalate(self, reason: str, detail): ...
