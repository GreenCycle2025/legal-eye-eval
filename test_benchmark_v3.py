from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path
from unittest.mock import patch

import benchmark_v3
import benchmark_v3_report
import eval_graph_arguments


class BenchmarkV3Tests(unittest.TestCase):
    def test_source_manifest_integrity_and_shape(self):
        source_path = Path("benchmarks/benchmark_v3_sources.json")
        payload = json.loads(source_path.read_text(encoding="utf-8"))
        clone = dict(payload)
        expected_sha = clone.pop("manifest_sha256")
        canonical = json.dumps(clone, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        self.assertEqual(expected_sha, hashlib.sha256(canonical.encode("utf-8")).hexdigest())
        self.assertEqual(80, payload["source_document_count"])
        self.assertEqual(80, len(payload["sources"]))
        self.assertEqual(80, len({row["source_doc_id"] for row in payload["sources"]}))
        self.assertEqual({10}, set(payload["group_counts"].values()))

    def test_suite_shape_and_reproducibility(self):
        built = benchmark_v3.build_suite()
        checked = json.loads(
            Path("benchmarks/benchmark_v3_independent_100.json").read_text(encoding="utf-8")
        )
        self.assertEqual([], benchmark_v3.validate_suite(built))
        self.assertEqual(built, checked)
        self.assertEqual(100, built["total"])
        self.assertEqual(80, built["independent_total"])
        self.assertEqual(20, built["oos_total"])
        self.assertEqual({10}, set(built["group_counts"].values()))

    def test_independent_cases_require_unique_exact_source_docs(self):
        suite = benchmark_v3.build_suite()
        legal = [case for case in suite["cases"] if case["split"] == "independent"]
        doc_ids = [case["expect_source_doc_id"] for case in legal]
        self.assertEqual(80, len(set(doc_ids)))
        self.assertTrue(all(case["expect_no_promotion"] is False for case in legal))

    def test_oos_cases_fail_closed(self):
        suite = benchmark_v3.build_suite()
        oos = [case for case in suite["cases"] if case["split"] == "oos"]
        self.assertEqual(20, len(oos))
        self.assertTrue(all(case["expect_no_promotion"] is True for case in oos))
        self.assertTrue(all("expect_source_doc_id" not in case for case in oos))

    def test_evaluator_requires_exact_source_doc_when_requested(self):
        bundle = {
            "cluster_score": 0.90,
            "coverage": 0.30,
            "anchor_quote": "ראיה מאומתת",
            "anchor_label": "חוק לדוגמה",
            "MIN_PROMOTE_SCORE": 0.50,
            "MIN_PROMOTE_COVERAGE": 0.15,
            "HIGH_SCORE_BYPASS": 0.65,
            "diagnostic": {
                "anchor_quote_doc_id": "doc-correct",
                "anchor_quote_source": "verified_primary_statute",
            },
        }
        payload = {"bundle": bundle}

        with patch.object(eval_graph_arguments, "_post_json", return_value=payload):
            good = eval_graph_arguments.evaluate(
                "http://example.invalid",
                {
                    "case_id": "good",
                    "question": "שאלה",
                    "expect_source_doc_id": "doc-correct",
                },
                timeout=1,
                via="hgraph",
            )
            bad = eval_graph_arguments.evaluate(
                "http://example.invalid",
                {
                    "case_id": "bad",
                    "question": "שאלה",
                    "expect_source_doc_id": "doc-wrong",
                },
                timeout=1,
                via="hgraph",
            )

        self.assertEqual("PASS", good["verdict"])
        self.assertTrue(good["source_doc_match"])
        self.assertEqual("FAIL", bad["verdict"])
        self.assertFalse(bad["source_doc_match"])

    def test_v2_semantics_remain_backward_compatible_without_source_requirement(self):
        bundle = {
            "cluster_score": 0.90,
            "coverage": 0.30,
            "anchor_quote": "תוכן מתאים",
            "anchor_label": "עוגן",
            "MIN_PROMOTE_SCORE": 0.50,
            "MIN_PROMOTE_COVERAGE": 0.15,
            "HIGH_SCORE_BYPASS": 0.65,
            "diagnostic": {"anchor_quote_doc_id": "any-doc"},
        }
        with patch.object(eval_graph_arguments, "_post_json", return_value={"bundle": bundle}):
            row = eval_graph_arguments.evaluate(
                "http://example.invalid",
                {"question": "שאלה ללא דרישת מקור"},
                timeout=1,
                via="hgraph",
            )
        self.assertEqual("PASS", row["verdict"])
        self.assertTrue(row["source_doc_match"])

    def test_reporter_separates_exact_source_and_oos(self):
        suite = benchmark_v3.build_suite()
        rows = []
        for case in suite["cases"]:
            if case["split"] == "oos":
                rows.append({
                    "case_id": case["case_id"],
                    "verdict": "PASS",
                    "promoted_to_arguments": False,
                    "source_doc_match": True,
                })
            else:
                rows.append({
                    "case_id": case["case_id"],
                    "verdict": "PASS",
                    "promoted_to_arguments": True,
                    "source_doc_match": True,
                })
        report = benchmark_v3_report.build_report(suite, rows)
        self.assertEqual(100, report["matched_total"])
        self.assertEqual(80, report["independent"]["exact_source_hits"])
        self.assertEqual(1.0, report["independent"]["exact_source_hit_rate"])
        self.assertEqual(20, report["oos"]["rejected"])
        self.assertEqual(1.0, report["oos"]["rejection_rate"])


if __name__ == "__main__":
    unittest.main()
