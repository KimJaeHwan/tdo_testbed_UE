from __future__ import annotations

import unittest

from harness.evaluation import report_metrics, report_primary_green
from harness.engine_dev_loop import _compare_reports, _repair_context_from_cycle
from harness.gates import human_gate_items, invariant_status, objective_vector
from harness.reporting import precision_report, summarize


def _row(**overrides) -> dict:
    row = {
        "suite": "test",
        "variant_label": "P0-test",
        "case": "CASE001",
        "function": "case_CASE001",
        "verdict": "PASS",
        "missing": [],
        "forbidden_found": [],
        "negative_case": False,
        "recall_pass": True,
        "precision_status": "CLEAN",
        "artifacts": {},
    }
    row.update(overrides)
    return row


class RecallFirstGateTest(unittest.TestCase):
    def test_precision_candidate_is_primary_green(self):
        report = [
            _row(
                forbidden_found=["source_B.ret"],
                precision_candidates=["source_B.ret"],
                precision_status="REFINEMENT_PENDING",
                precision_clean=False,
            )
        ]

        gate = invariant_status(report)
        metrics = report_metrics(report)

        self.assertTrue(gate["I2_recall_complete"])
        self.assertTrue(gate["I5_negative_controls_clean"])
        self.assertFalse(gate["precision_clean"])
        self.assertEqual(1, metrics["precision_pending"])
        self.assertTrue(report_primary_green(report))
        self.assertEqual(1, precision_report(report)["candidate_count"])
        self.assertEqual(1, summarize(report)["suites"]["test"]["precision_pending"])
        self.assertEqual([], human_gate_items(report, gate))

    def test_precision_does_not_change_recall_objective(self):
        clean = [_row()]
        pending = [
            _row(
                forbidden_found=[],
                precision_candidates=["source_unlisted.ret"],
                precision_status="REFINEMENT_PENDING",
            )
        ]

        self.assertEqual(objective_vector(clean), objective_vector(pending))

    def test_precision_candidate_does_not_schedule_engine_repair(self):
        clean = [_row()]
        pending = [
            _row(
                precision_candidates=["source_unlisted.ret"],
                precision_status="REFINEMENT_PENDING",
                precision_clean=False,
            )
        ]

        comparison = _compare_reports(clean, pending)
        cycle = {
            "cycle": 1,
            "comparison": comparison,
            "pre_regression": {"report_path": "before.json"},
            "post_regression": {"report_path": "after.json"},
        }

        self.assertTrue(comparison["no_worse"])
        self.assertFalse(comparison["objective_improved"])
        self.assertIsNone(_repair_context_from_cycle(cycle))

    def test_missing_expected_source_fails_recall_gate(self):
        report = [_row(verdict="FAIL", recall_pass=False, missing=["source_A.ret"])]

        gate = invariant_status(report)

        self.assertFalse(gate["I2_recall_complete"])
        self.assertFalse(report_primary_green(report))
        self.assertEqual("frontier_candidate", human_gate_items(report, gate)[0]["kind"])

    def test_negative_control_remains_a_hard_failure(self):
        report = [
            _row(
                verdict="FAIL",
                negative_case=True,
                negative_control_pass=False,
                forbidden_found=["unexpected_source.ret"],
                precision_status="NEGATIVE_CONTROL_VIOLATION",
            )
        ]

        gate = invariant_status(report)

        self.assertFalse(gate["I5_negative_controls_clean"])
        self.assertFalse(report_primary_green(report))
        self.assertEqual("negative_control_violation", human_gate_items(report, gate)[0]["kind"])


if __name__ == "__main__":
    unittest.main()
