#!/usr/bin/env python3
"""Build and validate the 500-case Legal Eye robustness benchmark.

This suite intentionally does NOT claim 500 independent legal doctrines.
It contains the 50 canonical cases plus nine deterministic stress variants
per case. Each derived case preserves the original expectation and carries
provenance back to its canonical source.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Callable

from eval_graph_arguments import QUESTIONS

SCHEMA_VERSION = 2
SUITE_NAME = "legal-eye-benchmark-v2-500"


def _identity(q: str) -> str:
    return q


def _concise(q: str) -> str:
    return f"בקצרה: {q}"


def _formal(q: str) -> str:
    return f"מה הדין בישראל לגבי {q}?"


def _evidence_only(q: str) -> str:
    return f"נא להשיב רק על בסיס מקור משפטי מאומת: {q}"


def _anti_hallucination(q: str) -> str:
    return f"אם אין מקור אמיתי ומאומת, אל תנחש ואל תמציא. השאלה: {q}"


def _context_noise(q: str) -> str:
    return f"לצורכי בדיקת מערכת בלבד, בלי עצה אישית: {q}"


def _punctuation_noise(q: str) -> str:
    return f"שאלה:   {q}   ?"


def _current_law(q: str) -> str:
    return f"לפי הדין הישראלי החל כיום, מה הדין לגבי {q}?"


def _authority_coercion(q: str) -> str:
    return f"נאמר לי שבוודאות יש מקור שתומך בזה. הצג אותו רק אם הוא אכן קיים: {q}"


def _facts_wrapper(q: str) -> str:
    return f"עובדות/סוגיה: {q}. מה המקור המשפטי הרלוונטי?"


TRANSFORMS: list[tuple[str, str, Callable[[str], str]]] = [
    ("canonical", "canonical", _identity),
    ("concise", "holdout", _concise),
    ("formal_israel", "holdout", _formal),
    ("evidence_only", "holdout", _evidence_only),
    ("anti_hallucination", "holdout", _anti_hallucination),
    ("context_noise", "holdout", _context_noise),
    ("punctuation_noise", "holdout", _punctuation_noise),
    ("current_law", "holdout", _current_law),
    ("authority_coercion", "holdout", _authority_coercion),
    ("facts_wrapper", "holdout", _facts_wrapper),
]

EXPECTATION_KEYS = (
    "expect_anchor_substring",
    "expect_quote_keywords",
    "expect_no_promotion",
)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_suite() -> dict[str, Any]:
    cases: list[dict[str, Any]] = []
    for base_index, base in enumerate(QUESTIONS, start=1):
        source_q = str(base["question"])
        base_case_id = f"base-{base_index:03d}"
        source_sha = _sha(source_q)
        for variant_index, (kind, split, transform) in enumerate(TRANSFORMS):
            row: dict[str, Any] = {
                "case_id": f"{base_case_id}-v{variant_index:02d}",
                "base_case_id": base_case_id,
                "base_index": base_index,
                "variant_index": variant_index,
                "variant_kind": kind,
                "split": split,
                "question": transform(source_q),
                "source_question": source_q,
                "source_question_sha256": source_sha,
            }
            for key in EXPECTATION_KEYS:
                if key in base:
                    row[key] = base[key]
            cases.append(row)

    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "name": SUITE_NAME,
        "methodology": "50 canonical cases x 10 deterministic robustness variants",
        "independent_doctrine_count": len(QUESTIONS),
        "variant_count_per_doctrine": len(TRANSFORMS),
        "total": len(cases),
        "canonical_total": sum(c["split"] == "canonical" for c in cases),
        "holdout_total": sum(c["split"] == "holdout" for c in cases),
        "variant_kinds": [kind for kind, _split, _fn in TRANSFORMS],
        "cases": cases,
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    payload["suite_sha256"] = _sha(canonical)
    return payload


def validate_suite(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    cases = payload.get("cases")
    if not isinstance(cases, list):
        return ["cases must be a list"]
    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}")
    if len(cases) != 500:
        errors.append(f"expected 500 cases, got {len(cases)}")
    ids = [str(c.get("case_id") or "") for c in cases]
    if len(set(ids)) != len(ids) or any(not cid for cid in ids):
        errors.append("case_id values must be non-empty and unique")
    canonical = [c for c in cases if c.get("split") == "canonical"]
    holdout = [c for c in cases if c.get("split") == "holdout"]
    if len(canonical) != 50 or len(holdout) != 450:
        errors.append(f"expected split 50/450, got {len(canonical)}/{len(holdout)}")

    by_base: dict[str, list[dict[str, Any]]] = {}
    for case in cases:
        by_base.setdefault(str(case.get("base_case_id") or ""), []).append(case)
    if len(by_base) != 50:
        errors.append(f"expected 50 base cases, got {len(by_base)}")
    for base_id, rows in by_base.items():
        if len(rows) != 10:
            errors.append(f"{base_id}: expected 10 variants, got {len(rows)}")
            continue
        kinds = [r.get("variant_kind") for r in rows]
        if kinds != [kind for kind, _split, _fn in TRANSFORMS]:
            errors.append(f"{base_id}: variant order/kinds drifted")
        expectation_snapshots = [
            tuple(json.dumps(r.get(k, None), ensure_ascii=False, sort_keys=True) for k in EXPECTATION_KEYS)
            for r in rows
        ]
        if len(set(expectation_snapshots)) != 1:
            errors.append(f"{base_id}: expectations changed across variants")
        source_q = str(rows[0].get("source_question") or "")
        if not source_q or rows[0].get("source_question_sha256") != _sha(source_q):
            errors.append(f"{base_id}: source question provenance mismatch")
        if len({str(r.get("question") or "") for r in rows}) != 10:
            errors.append(f"{base_id}: duplicate transformed questions")

    expected_sha = payload.get("suite_sha256")
    clone = dict(payload)
    clone.pop("suite_sha256", None)
    canonical_json = json.dumps(clone, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    actual_sha = _sha(canonical_json)
    if expected_sha != actual_sha:
        errors.append("suite_sha256 mismatch")
    return errors


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path("benchmarks/benchmark_v2_500.json"))
    ap.add_argument("--check", type=Path, default=None)
    args = ap.parse_args()

    if args.check is not None:
        payload = json.loads(args.check.read_text(encoding="utf-8"))
    else:
        payload = build_suite()
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {args.out}")

    errors = validate_suite(payload)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(
        f"PASS {payload['name']}: total={payload['total']} "
        f"canonical={payload['canonical_total']} holdout={payload['holdout_total']} "
        f"sha256={payload['suite_sha256']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
