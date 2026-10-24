from __future__ import annotations

import json
import unittest
from pathlib import Path

import benchmark_v2
import benchmark_v2_report
import eval_graph_arguments


class BenchmarkV2Tests(unittest.TestCase):
    def test_suite_shape_and_provenance(self):
        payload = benchmark_v2.build_suite()
        self.assertEqual([], benchmark_v2.validate_suite(payload))
        self.assertEqual(500, payload["total"])
        self.assertEqual(50, payload["canonical_total"])
        self.assertEqual(450, payload["holdout_total"])
        self.assertEqual(50, payload["independent_doctrine_count"])
        self.assertEqual(10, payload["variant_count_per_doctrine"])

    def test_checked_in_suite_is_reproducible(self):
        checked = json.loads(
            Path("benchmarks/benchmark_v2_500.json").read_text(encoding="utf-8")
        )
        built = benchmark_v2.build_suite()
        self.assertEqual(checked, built)
        self.assertEqual([], benchmark_v2.validate_suite(checked))

    def test_canonical_shard_is_original_50(self):
        rows, name = eval_graph_arguments.load_question_suite(
            "benchmarks/benchmark_v2_500.json"
        )
        self.assertEqual("legal-eye-benchmark-v2-500", name)
        canonical = eval_graph_arguments.shard_questions(
            rows, shard_index=0, shard_count=10
        )
        self.assertEqual(50, len(canonical))
        self.assertEqual(
            [row["question"] for row in eval_graph_arguments.QUESTIONS],
            [row["question"] for row in canonical],
        )
        self.assertEqual({"canonical"}, {row["variant_kind"] for row in canonical})

    def test_each_holdout_shard_is_one_stable_variant_kind(self):
        rows, _ = eval_graph_arguments.load_question_suite(
            "benchmarks/benchmark_v2_500.json"
        )
        expected = benchmark_v2.build_suite()["variant_kinds"]
        for index, kind in enumerate(expected):
            shard = eval_graph_arguments.shard_questions(
                rows, shard_index=index, shard_count=10
            )
            self.assertEqual(50, len(shard))
            self.assertEqual({kind}, {row["variant_kind"] for row in shard})

    def test_bad_shard_parameters_fail_closed(self):
        rows = [{"question": "x"}]
        with self.assertRaises(SystemExit):
            eval_graph_arguments.shard_questions(rows, shard_index=0, shard_count=0)
        with self.assertRaises(SystemExit):
            eval_graph_arguments.shard_questions(rows, shard_index=2, shard_count=2)

    def test_reporter_separates_canonical_holdout_and_oos(self):
        suite = benchmark_v2.build_suite()
        rows = []
        for case in suite["cases"]:
            is_oos = bool(case.get("expect_no_promotion"))
            rows.append({
                "case_id": case["case_id"],
                "ok": True,
                "verdict": "PASS",
                "promoted_to_arguments": not is_oos,
            })
        report = benchmark_v2_report.build_report(suite, rows)
        self.assertEqual(500, report["result_total"])
        self.assertEqual(50, report["splits"]["canonical"]["pass"])
        self.assertEqual(450, report["splits"]["holdout"]["pass"])
        self.assertEqual(50, report["oos_total"])
        self.assertEqual(50, report["oos_rejected"])
        self.assertEqual(1.0, report["oos_rejection_rate"])


if __name__ == "__main__":
    unittest.main()
