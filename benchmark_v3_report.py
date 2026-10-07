#!/usr/bin/env python3
"""Report Legal Eye Benchmark v3 independent-doctrine results."""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def _rates(rows: list[dict[str, Any]]) -> dict[str, Any]:
    counts = Counter(str(row.get("verdict") or "UNKNOWN") for row in rows)
    total = len(rows)
    return {
        "total": total,
        "pass": counts.get("PASS", 0),
        "weak": counts.get("WEAK", 0),
        "fail": counts.get("FAIL", 0),
        "pass_rate": (counts.get("PASS", 0) / total) if total else 0.0,
    }


def build_report(suite: dict[str, Any], result_rows: list[dict[str, Any]]) -> dict[str, Any]:
    expected = {str(case["case_id"]): case for case in suite["cases"]}
    actual = {str(row.get("case_id") or ""): row for row in result_rows if row.get("case_id")}
    missing = sorted(set(expected) - set(actual))
    extra = sorted(set(actual) - set(expected))

    aligned = [actual[cid] for cid in expected if cid in actual]
    independent = [
        actual[cid] for cid, case in expected.items()
        if case.get("split") == "independent" and cid in actual
    ]
    oos = [
        actual[cid] for cid, case in expected.items()
        if case.get("split") == "oos" and cid in actual
    ]

    exact_source_hits = sum(bool(row.get("source_doc_match")) for row in independent)
    promoted_independent = sum(bool(row.get("promoted_to_arguments")) for row in independent)
    oos_rejected = sum(
        row.get("verdict") == "PASS" and not row.get("promoted_to_arguments")
        for row in oos
    )

    by_domain: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_hint: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for cid, case in expected.items():
        if case.get("split") != "independent" or cid not in actual:
            continue
        by_domain[str(case.get("benchmark_domain"))].append(actual[cid])
        by_hint[str(case.get("hint_mode"))].append(actual[cid])

    return {
        "suite": suite.get("name"),
        "suite_sha256": suite.get("suite_sha256"),
        "result_total": len(result_rows),
        "matched_total": len(aligned),
        "missing_case_ids": missing,
        "extra_case_ids": extra,
        "overall": _rates(aligned),
        "independent": {
            **_rates(independent),
            "promoted": promoted_independent,
            "exact_source_hits": exact_source_hits,
            "exact_source_hit_rate": (exact_source_hits / len(independent)) if independent else 0.0,
        },
        "oos": {
            **_rates(oos),
            "rejected": oos_rejected,
            "rejection_rate": (oos_rejected / len(oos)) if oos else 0.0,
        },
        "domains": {key: _rates(rows) for key, rows in sorted(by_domain.items())},
        "hint_modes": {key: _rates(rows) for key, rows in sorted(by_hint.items())},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("result", type=Path)
    parser.add_argument("--suite", type=Path, default=Path("benchmarks/benchmark_v3_independent_100.json"))
    parser.add_argument("--json-out", type=Path, default=None)
    args = parser.parse_args()

    suite = json.loads(args.suite.read_text(encoding="utf-8"))
    result = json.loads(args.result.read_text(encoding="utf-8"))
    rows = result.get("rows") if isinstance(result, dict) else result
    if not isinstance(rows, list):
        raise SystemExit("result must contain a rows list")

    report = build_report(suite, rows)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.json_out:
        args.json_out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 1 if report["missing_case_ids"] or report["extra_case_ids"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
