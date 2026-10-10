#!/usr/bin/env python3
"""Build runs/latest.json from a raw canonical run.

The stable summary is the public contract consumed by Legal Eye surfaces and
release tooling. Raw per-question rows remain available in their dated file.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path

OOS_TERMS = ("טראפיק", "עוגת", "איקאה", "בגרות", "לימון")


def is_oos(row: dict) -> bool:
    q = str(row.get("question") or "")
    return any(term in q for term in OOS_TERMS)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("run", type=Path)
    ap.add_argument("--out", type=Path, default=Path("runs/latest.json"))
    args = ap.parse_args()
    rows = json.loads(args.run.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise SystemExit("run must be a JSON list")

    verdicts = Counter(str(r.get("verdict") or "UNKNOWN").upper() for r in rows)
    oos = [r for r in rows if is_oos(r)]
    oos_rejected = sum(
        1 for r in oos
        if str(r.get("verdict") or "").upper() == "PASS"
        and not bool(r.get("promoted_to_arguments"))
    )
    attribution = Counter()
    for row in rows:
        verdict = str(row.get("verdict") or "").upper()
        if verdict == "PASS":
            attribution["PASS"] += 1
        elif not bool(row.get("ok", True)):
            attribution["EVAL_ERROR"] += 1
        elif bool(row.get("promoted_to_arguments")) and row.get("quote_keywords_ok") is False:
            attribution["CITATION_MISS"] += 1
        elif not bool(row.get("promoted_to_arguments")):
            attribution["PROMOTION_THRESHOLD"] += 1
        else:
            attribution["UNKNOWN"] += 1

    total = len(rows)
    pass_count = verdicts.get("PASS", 0)
    weak_count = verdicts.get("WEAK", 0)
    fail_count = verdicts.get("FAIL", 0)
    date = args.run.stem.removeprefix("run_").replace("_", "-")
    payload = {
        "schema_version": 1,
        "date": date,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run_file": f"runs/{args.run.name}",
        "total": total,
        "pass": pass_count,
        "weak": weak_count,
        "fail": fail_count,
        "pass_rate": (pass_count / total if total else 0.0),
        "weak_rate": (weak_count / total if total else 0.0),
        "oos_total": len(oos),
        "oos_rejected": oos_rejected,
        "oos_rejection_rate": (oos_rejected / len(oos) if oos else 1.0),
        "attribution": dict(sorted(attribution.items())),
        "methodology": "canonical-50-live-production",
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
