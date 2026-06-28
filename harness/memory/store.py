from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def _append_jsonl(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


class Memory:
    def __init__(self, base: Path):
        self.base = Path(base)
        self.base.mkdir(parents=True, exist_ok=True)

    @property
    def failure_ledger_path(self) -> Path:
        return self.base / "failure_ledger.jsonl"

    @property
    def hypothesis_ledger_path(self) -> Path:
        return self.base / "hypothesis_ledger.json"

    @property
    def decision_log_path(self) -> Path:
        return self.base / "decision_log.jsonl"

    @property
    def artifact_cache_path(self) -> Path:
        return self.base / "artifact_cache.json"

    @property
    def capability_map_path(self) -> Path:
        return self.base / "capability_map.json"

    @property
    def human_queue_path(self) -> Path:
        return self.base / "human_approval_queue.jsonl"

    @property
    def escalation_path(self) -> Path:
        return self.base / "escalations.jsonl"

    def capability_map(self) -> dict:
        return _read_json(self.capability_map_path, {})

    def history(self, case: str) -> list:
        if not self.failure_ledger_path.exists():
            return []
        rows = []
        with self.failure_ledger_path.open("r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                row = json.loads(line)
                if row.get("case") == case:
                    rows.append(row)
        return rows

    def known_root_cause(self, case: str) -> dict | None:
        hypotheses = _read_json(self.hypothesis_ledger_path, {})
        for row in reversed(self.history(case)):
            ref = row.get("root_cause_ref")
            if ref and ref in hypotheses:
                return hypotheses[ref]
        return None

    def mark_refuted(self, diagnosis: dict):
        self._update_hypothesis(diagnosis, "refuted")

    def mark_confirmed(self, diagnosis: dict, votes: dict):
        self._update_hypothesis(diagnosis, "confirmed", {"adversary_votes": votes})

    def merge(self, fix: dict, diagnosis: dict, votes: bool):
        row = {
            "time": _now(),
            "change": fix.get("branch") or fix.get("change") or fix.get("summary"),
            "why": diagnosis.get("root_cause") or diagnosis.get("claim"),
            "cites": diagnosis.get("case_refs") or [diagnosis.get("case")],
            "evidence": diagnosis.get("evidence_ref"),
            "adversary_votes": votes,
            "objective_delta": fix.get("selftest"),
        }
        _append_jsonl(self.decision_log_path, row)
        self._update_hypothesis(diagnosis, "fixed")

    def discard(self, fix: dict):
        _append_jsonl(
            self.decision_log_path,
            {
                "time": _now(),
                "change": fix.get("branch") or fix.get("change") or fix.get("summary"),
                "discarded": True,
                "why": fix.get("risk_note") or "gate_or_adversary_rejected",
            },
        )

    def route(self, failure: dict, triage: dict):
        _append_jsonl(
            self.failure_ledger_path,
            {
                "time": _now(),
                "case": failure.get("case"),
                "variant": failure.get("variant") or failure.get("variant_label"),
                "verdict": failure.get("verdict"),
                "missing": failure.get("missing", []),
                "forbidden_found": failure.get("forbidden_found", []),
                "cut": failure.get("cut", []),
                "triage": triage,
            },
        )

    def update_capability_map(self, report: list):
        cap = self.capability_map()
        grouped: dict[str, list[dict]] = {}
        for row in report:
            key = self._capability_key(row)
            grouped.setdefault(key, []).append(row)

        for key, rows in grouped.items():
            verdicts = [row.get("verdict") for row in rows]
            has_forbidden = any(row.get("forbidden_found") for row in rows)
            has_error = any(row.get("verdict") == "ERROR" for row in rows)
            all_pass = all(row.get("verdict") == "PASS" for row in rows)
            if all_pass:
                status = "can"
            elif has_forbidden or has_error:
                status = "contradictory"
            else:
                status = "frontier"
            cap[key] = {
                **cap.get(key, {}),
                "case_class": key,
                "status": status,
                "human_confirmed": False if status in {"frontier", "contradictory"} else cap.get(key, {}).get("human_confirmed", True),
                "cases": sorted({str(row.get("case")) for row in rows}),
                "last_run_id": rows[-1].get("run_id"),
                "last_variants": sorted({str(row.get("variant_label")) for row in rows}),
                "last_verdicts": sorted({str(verdict) for verdict in verdicts}),
                "last_false_positive": has_forbidden,
                "updated_at": _now(),
            }
        _write_json(self.capability_map_path, cap)

    def queue_for_human_approval(self, case: dict):
        _append_jsonl(self.human_queue_path, {"time": _now(), "case": case})

    def escalate(self, reason: str, detail):
        _append_jsonl(self.escalation_path, {"time": _now(), "reason": reason, "detail": detail})

    def record_run(self, run_id: str, report: list[dict], summary: dict, gate: dict, output_root: Path) -> None:
        self._record_failures(run_id, report)
        self._record_artifacts(run_id, report, summary, gate, output_root)
        self.update_capability_map(report)

    def cached_result(
        self,
        pcode_hash: str | None,
        engine_commit: str | None,
        run_config_hash: str | None,
        expected_hash: str | None,
    ) -> dict | None:
        if not pcode_hash or not engine_commit or not run_config_hash or not expected_hash:
            return None
        cache = _read_json(self.artifact_cache_path, {})
        engine_key = "|".join([pcode_hash, engine_commit, run_config_hash])
        verify_key = "|".join([engine_key, expected_hash, "expected_validator_v1"])
        verify = (cache.get("verify_result") or {}).get(verify_key)
        if not verify:
            return None
        engine_result = (cache.get("engine_result") or {}).get(engine_key) or {}
        cached_row = verify.get("row")
        if cached_row:
            row = deepcopy(cached_row)
            row["cache"] = {"hit": True, "source_result_path": engine_result.get("result_path")}
            return row

        result_path = engine_result.get("result_path")
        if not result_path:
            return None
        path = Path(result_path)
        if not path.exists():
            return None
        for row in _read_json(path, []):
            artifacts = row.get("artifacts") or {}
            engine = row.get("engine") or {}
            if (
                artifacts.get("pcode_hash") == pcode_hash
                and artifacts.get("expected_hash") == expected_hash
                and artifacts.get("run_config_hash") == run_config_hash
                and engine.get("commit") == engine_commit
            ):
                cached = deepcopy(row)
                cached["cache"] = {"hit": True, "source_result_path": result_path}
                return cached
        return None

    def _record_failures(self, run_id: str, report: list[dict]) -> None:
        for row in report:
            if row.get("verdict") == "PASS":
                continue
            _append_jsonl(
                self.failure_ledger_path,
                {
                    "time": _now(),
                    "run_id": run_id,
                    "case": row.get("case"),
                    "commit": (row.get("engine") or {}).get("commit"),
                    "variant": row.get("variant_label"),
                    "verdict": row.get("verdict"),
                    "missing": row.get("missing", []),
                    "forbidden_found": row.get("forbidden_found", []),
                    "cut": row.get("cut", []),
                    "root_cause_ref": None,
                    "result_path": (row.get("artifacts") or {}).get("result_path"),
                },
            )

    def _record_artifacts(
        self,
        run_id: str,
        report: list[dict],
        summary: dict,
        gate: dict,
        output_root: Path,
    ) -> None:
        cache = _read_json(
            self.artifact_cache_path,
            {"schema_version": 1, "build_artifact": {}, "pcode_metadata": {}, "engine_result": {}, "verify_result": {}, "runs": {}},
        )
        cache.setdefault("build_artifact", {})
        cache.setdefault("pcode_metadata", {})
        cache.setdefault("engine_result", {})
        cache.setdefault("verify_result", {})
        cache.setdefault("runs", {})

        for row in report:
            artifacts = row.get("artifacts") or {}
            binary_hash = artifacts.get("binary_hash")
            pcode_hash = artifacts.get("pcode_hash")
            expected_hash = artifacts.get("expected_hash")
            engine_commit = (row.get("engine") or {}).get("commit")
            run_config_hash = artifacts.get("run_config_hash")
            if binary_hash:
                cache["build_artifact"][binary_hash] = {
                    "path": artifacts.get("binary_path"),
                    "variant": row.get("variant_label"),
                    "updated_at": _now(),
                }
            if pcode_hash:
                pcode_key = "|".join(str(item or "") for item in [binary_hash, pcode_hash])
                cache["pcode_metadata"][pcode_key] = {
                    "pcode_path": artifacts.get("pcode_path"),
                    "metadata_path": artifacts.get("metadata_path"),
                    "pcode_hash": pcode_hash,
                    "updated_at": _now(),
                }
            if pcode_hash and engine_commit and run_config_hash:
                engine_key = "|".join([pcode_hash, engine_commit, run_config_hash])
                cache["engine_result"][engine_key] = {
                    "result_path": artifacts.get("result_path"),
                    "case": row.get("case"),
                    "variant": row.get("variant_label"),
                    "verdict": row.get("verdict"),
                    "updated_at": _now(),
                }
                if expected_hash:
                    verify_key = "|".join([engine_key, expected_hash, "expected_validator_v1"])
                    cache["verify_result"][verify_key] = {
                        "verdict": row.get("verdict"),
                        "missing": row.get("missing", []),
                        "forbidden_found": row.get("forbidden_found", []),
                        "row": self._cacheable_row(row),
                        "updated_at": _now(),
                    }
        cache["runs"][run_id] = {
            "time": _now(),
            "output_root": str(output_root),
            "summary": summary,
            "gate": gate,
        }
        _write_json(self.artifact_cache_path, cache)

    def _update_hypothesis(self, diagnosis: dict, status: str, extra: dict | None = None) -> None:
        hypotheses = _read_json(self.hypothesis_ledger_path, {})
        hid = diagnosis.get("id") or diagnosis.get("case") or f"H-{len(hypotheses) + 1:04d}"
        hypotheses[hid] = {
            **hypotheses.get(hid, {}),
            **diagnosis,
            "id": hid,
            "status": status,
            "updated_at": _now(),
            **(extra or {}),
        }
        _write_json(self.hypothesis_ledger_path, hypotheses)

    def _capability_key(self, row: dict) -> str:
        features = row.get("features") or []
        if features:
            return "+".join(sorted(str(item) for item in features))
        return str(row.get("case") or row.get("function") or "unknown")

    def _cacheable_row(self, row: dict) -> dict:
        cached = deepcopy(row)
        cached["cache"] = {"hit": False}
        return cached
