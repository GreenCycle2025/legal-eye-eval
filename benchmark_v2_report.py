#!/usr/bin/env python3
"""Summarize a Benchmark v2 result file without conflating it with canonical-50."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
from typing import Any


def _rate(n: int, d: int) -> float:
    return n / d if d else 0.0


def build_report(suite: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    cases = suite.get("cases") or []
    expected = {str(c.get("case_id") or ""): c for c in cases}
    result_by_id: dict[str, dict[str, Any]] = {}
    duplicates: list[str] = []
    for row in rows:
        cid = str(row.get("case_id") or "")
        if cid in result_by_id:
            duplicates.append(cid)
        result_by_id[cid] = row

    missing = sorted(set(expected) - set(result_by_id))
    unknown = sorted(set(result_by_id) - set(expected))
    verdicts = Counter(str(r.get("verdict") or "ERROR") for r in rows)
    errors = sum(1 for r in rows if not bool(r.get("ok", True)))

    split_stats: dict[str, Counter] = defaultdict(Counter)
    variant_stats: dict[str, Counter] = defaultdict(Counter)
    for cid, case in expected.items():
        row = result_by_id.get(cid)
        if row is None:
            continue
        verdict = str(row.get("verdict") or "ERROR")
        split_stats[str(case.get("split") or "unknown")][verdict] += 1
        variant_stats[str(case.get("variant_kind") or "unknown")][verdict] += 1

    oos_ids = [cid for cid, case in expected.items() if bool(case.get("expect_no_promotion"))]
    oos_rejected = sum(
        1 for cid in oos_ids
        if cid in result_by_id
        and str(result_by_id[cid].get("verdict") or "") == "PASS"
        and not bool(result_by_id[cid].get("promoted_to_arguments"))
    )

    def pack(counter: Counter) -> dict[str, Any]:
        total = sum(counter.values())
        return {
            "total": total,
            "pass": counter.get("PASS", 0),
            "weak": counter.get("WEAK", 0),
            "fail": counter.get("FAIL", 0),
            "error": counter.get("ERROR", 0),
            "pass_rate": _rate(counter.get("PASS", 0), total),
        }

    return {
        "schema_version": 1,
        "suite_name": suite.get("name"),
        "suite_sha256": suite.get("suite_sha256"),
        "expected_total": len(cases),
        "result_total": len(rows),
        "missing_case_ids": missing,
        "unknown_case_ids": unknown,
        "duplicate_case_ids": sorted(set(duplicates)),
        "verdicts": dict(sorted(verdicts.items())),
        "eval_errors": errors,
        "splits": {name: pack(counter) for name, counter in sorted(split_stats.items())},
        "variants": {name: pack(counter) for name, counter in sorted(variant_stats.items())},
        "oos_total": len(oos_ids),
        "oos_rejected": oos_rejected,
        "oos_rejection_rate": _rate(oos_rejected, len(oos_ids)),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("result", type=Path)
    ap.add_argument("--suite", type=Path, default=Path("benchmarks/benchmark_v2_500.json"))
    ap.add_argument("--json-out", type=Path, default=None)
    args = ap.parse_args()

    suite = json.loads(args.suite.read_text(encoding="utf-8"))
    rows = json.loads(args.result.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise SystemExit("result must be a JSON list")
    report = build_report(suite, rows)
    text = json.dumps(report, ensure_ascii=False, indent=2)
    print(text)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(text + "\n", encoding="utf-8")

    integrity_bad = bool(
        report["missing_case_ids"]
        or report["unknown_case_ids"]
        or report["duplicate_case_ids"]
        or report["result_total"] != report["expected_total"]
    )
    quality_bad = report["verdicts"].get("FAIL", 0) > 0 or report["eval_errors"] > 0
    return 1 if integrity_bad or quality_bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
