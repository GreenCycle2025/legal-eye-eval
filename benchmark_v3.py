#!/usr/bin/env python3
"""Build and validate Legal Eye Benchmark v3: independent doctrines.

Unlike benchmark v2, v3 does not create prompt variants of the canonical 50.
It evaluates 80 frozen primary-law sections that were excluded from the
canonical v2 quote/top-10 retrieval set, plus 20 out-of-scope controls.

For in-scope cases PASS requires promotion AND the exact frozen source document.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 3
SUITE_NAME = "legal-eye-benchmark-v3-independent-100"
SOURCES_PATH = Path(__file__).resolve().parent / "benchmarks" / "benchmark_v3_sources.json"

OOS_CASES: list[tuple[str, str]] = [
    ("nonlegal_recipe", "איך מכינים מרק עגבניות סמיך בלי שמנת?"),
    ("nonlegal_furniture", "איך מרכיבים ארון מאיקאה בלי ההוראות המקוריות?"),
    ("nonlegal_weather", "מה מזג האוויר הצפוי מחר בפריז?"),
    ("nonlegal_sports", "מי ניצח במשחק הכדורגל האחרון של ברצלונה?"),
    ("nonlegal_code", "איך ממיינים מערך של אובייקטים ב-JavaScript לפי תאריך?"),
    ("nonlegal_translation", "תרגם לצרפתית: אני מגיע מחר בבוקר"),
    ("nonlegal_biology", "מה תפקיד המיטוכונדריה בתא?"),
    ("nonlegal_market", "מה מחיר הביטקוין עכשיו?"),
    ("nonlegal_travel", "מצא מלון זול ליד תחנת הרכבת ברומא"),
    ("nonlegal_math", "פתור את האינטגרל של x בריבוע"),
    ("foreign_oklahoma", "לפי הדין באוקלהומה, מה המהירות המותרת בכביש בין-עירוני?"),
    ("foreign_delaware", "מה חובת הדיווח של דירקטור בחברה לפי דיני דלאוור?"),
    ("foreign_california", "מה תקופת ההמתנה לגירושין לפי חוק קליפורניה?"),
    ("foreign_england", "מה תקופת ההודעה לשוכר לפי הדין באנגליה?"),
    ("foreign_germany", "כמה ימי חופשה מינימליים מגיעים לעובד לפי הדין בגרמניה?"),
    ("foreign_eu", "מהו הקנס המרבי לפי GDPR של האיחוד האירופי?"),
    ("foreign_us_patent", "כמה שנים נמשכת הגנת פטנט לפי הדין הפדרלי בארצות הברית?"),
    ("foreign_france", "מהו גיל הפרישה הקבוע כיום בדין הצרפתי?"),
    ("foreign_australia", "מה הכללים לפיטורים לא הוגנים לפי הדין האוסטרלי?"),
    ("foreign_canada", "מה שיעור מס החברות הפדרלי בקנדה?"),
]


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_sources(path: Path = SOURCES_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_suite(source_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    source_payload = source_payload or load_sources()
    cases: list[dict[str, Any]] = []

    for index, source in enumerate(source_payload["sources"], start=1):
        cases.append({
            "case_id": f"v3-legal-{index:03d}",
            "split": "independent",
            "source_type": "primary_law",
            "benchmark_domain": source["benchmark_domain"],
            "hint_mode": source["hint_mode"],
            "question": source["question"],
            "expect_anchor_substring": None,
            "expect_source_doc_id": source["source_doc_id"],
            "expect_no_promotion": False,
            "source_law": source["law"],
            "source_section": source["section"],
            "source_title": source["title"],
            "source_url": source.get("source_url"),
            "source_text_sha256": source["source_text_sha256"],
            "selection_hash": source["selection_hash"],
        })

    for index, (kind, question) in enumerate(OOS_CASES, start=1):
        cases.append({
            "case_id": f"v3-oos-{index:03d}",
            "split": "oos",
            "source_type": "out_of_scope",
            "oos_kind": kind,
            "question": question,
            "expect_anchor_substring": None,
            "expect_no_promotion": True,
        })

    group_counts: dict[str, int] = {}
    hint_counts: dict[str, int] = {}
    for case in cases:
        if case["split"] != "independent":
            continue
        group = str(case["benchmark_domain"])
        hint = str(case["hint_mode"])
        group_counts[group] = group_counts.get(group, 0) + 1
        hint_counts[hint] = hint_counts.get(hint, 0) + 1

    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "name": SUITE_NAME,
        "methodology": (
            "80 frozen primary-law sections from 8 stratified legal groups, "
            "excluded from benchmark-v2 canonical quote/top-10 retrieval; "
            "plus 20 out-of-scope controls"
        ),
        "source_manifest_sha256": source_payload["manifest_sha256"],
        "selection_seed": source_payload["selection_seed"],
        "excluded_v2_canonical_docs": source_payload["excluded_v2_canonical_docs"],
        "total": len(cases),
        "independent_total": sum(c["split"] == "independent" for c in cases),
        "oos_total": sum(c["split"] == "oos" for c in cases),
        "group_counts": group_counts,
        "hint_counts": hint_counts,
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
    if payload.get("name") != SUITE_NAME:
        errors.append(f"name must be {SUITE_NAME}")
    if len(cases) != 100:
        errors.append(f"expected 100 cases, got {len(cases)}")

    ids = [str(c.get("case_id") or "") for c in cases]
    if len(set(ids)) != len(ids) or any(not cid for cid in ids):
        errors.append("case_id values must be non-empty and unique")

    legal = [c for c in cases if c.get("split") == "independent"]
    oos = [c for c in cases if c.get("split") == "oos"]
    if len(legal) != 80 or len(oos) != 20:
        errors.append(f"expected 80 independent + 20 OOS, got {len(legal)} + {len(oos)}")

    doc_ids = [str(c.get("expect_source_doc_id") or "") for c in legal]
    if len(set(doc_ids)) != 80 or any(not doc_id for doc_id in doc_ids):
        errors.append("independent cases must reference 80 unique non-empty source doc ids")

    group_counts: dict[str, int] = {}
    hint_counts: dict[str, int] = {}
    for case in legal:
        group = str(case.get("benchmark_domain") or "")
        hint = str(case.get("hint_mode") or "")
        group_counts[group] = group_counts.get(group, 0) + 1
        hint_counts[hint] = hint_counts.get(hint, 0) + 1
        if case.get("expect_no_promotion"):
            errors.append(f"{case.get('case_id')}: independent case cannot expect no promotion")
        if not case.get("source_text_sha256"):
            errors.append(f"{case.get('case_id')}: missing source_text_sha256")
        if not str(case.get("question") or "").strip():
            errors.append(f"{case.get('case_id')}: empty question")

    if sorted(group_counts.values()) != [10] * 8:
        errors.append(f"expected eight legal groups of 10, got {group_counts}")
    if hint_counts != payload.get("hint_counts"):
        errors.append("hint_counts mismatch")
    if group_counts != payload.get("group_counts"):
        errors.append("group_counts mismatch")

    for case in oos:
        if not case.get("expect_no_promotion"):
            errors.append(f"{case.get('case_id')}: OOS case must expect no promotion")
        if case.get("expect_source_doc_id"):
            errors.append(f"{case.get('case_id')}: OOS case cannot require source doc")

    clone = dict(payload)
    expected_sha = clone.pop("suite_sha256", None)
    canonical = json.dumps(clone, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    actual_sha = _sha(canonical)
    if expected_sha != actual_sha:
        errors.append("suite_sha256 mismatch")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=Path("benchmarks/benchmark_v3_independent_100.json"))
    parser.add_argument("--check", type=Path, default=None)
    args = parser.parse_args()

    if args.check:
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
        f"independent={payload['independent_total']} oos={payload['oos_total']} "
        f"sha256={payload['suite_sha256']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
