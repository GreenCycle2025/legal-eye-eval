#!/usr/bin/env python3
"""eval_rescore.py — apply alternative verdict ladders to an existing
eval_graph_arguments JSON output, without re-running the queries.

Useful for tuning the production gate criterion: re-score the same
50 questions under different MIN_PROMOTE_SCORE / coverage / haystack
rules and see where 85% PASS lands.

Usage:
    python -m tau_rag.scripts.eval_rescore /tmp/eval_*.json
    python -m tau_rag.scripts.eval_rescore /tmp/eval_*.json --gate 0.7
"""
from __future__ import annotations
import argparse, json, sys
from typing import Dict, List, Any


def rescore(rows: List[Dict[str, Any]], gate_pct: float) -> Dict[str, int]:
    n_pass = sum(1 for r in rows if r.get("verdict") == "PASS")
    n_fail = sum(1 for r in rows if r.get("verdict") == "FAIL")
    n_weak = sum(1 for r in rows if r.get("verdict") == "WEAK")
    n_err  = sum(1 for r in rows if not r.get("ok"))
    pct    = (n_pass / len(rows)) * 100 if rows else 0.0
    gate   = "✓ MEETS" if pct >= gate_pct else "✗ BELOW"
    return {
        "n_total": len(rows),
        "n_pass":  n_pass,
        "n_fail":  n_fail,
        "n_weak":  n_weak,
        "n_err":   n_err,
        "pct":     pct,
        "gate":    gate,
        "gate_pct": gate_pct,
    }


def domain_breakdown(rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, int]]:
    """Bucket questions by topic prefix so we can see which area
    drags the average down."""
    domains: Dict[str, Dict[str, int]] = {}
    for r in rows:
        q = r.get("question", "")
        if   "חוזה"   in q or "אפרופים" in q or "אכיפ" in q: dom = "חוזים"
        elif "נזיק"   in q or "רשלנ"    in q or "מטרד" in q or "פרטיות" in q: dom = "נזיקין"
        elif "פיטור"  in q or "עובד"    in q or "הסכם קיבוצי" in q or "מינימום" in q or "התפט" in q or "הטרד" in q: dom = "עבודה"
        elif "ביטוח"  in q or "חולה"    in q or "רפואי" in q or "בריאות" in q: dom = "בריאות"
        elif "טראפיק" in q or "עוגת"    in q or "איקאה" in q or "בגרות" in q or "לימון" in q: dom = "out-of-scope"
        else: dom = "אחר"
        domains.setdefault(dom, {"PASS":0, "FAIL":0, "WEAK":0, "ERR":0})
        v = r.get("verdict") if r.get("ok") else "ERR"
        domains[dom][v or "ERR"] = domains[dom].get(v or "ERR", 0) + 1
    return domains


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("json_file")
    ap.add_argument("--gate", type=float, default=85.0,
                    help="required PASS percentage to meet gate (default 85)")
    args = ap.parse_args()

    with open(args.json_file, "r", encoding="utf-8") as f:
        rows = json.load(f)

    s = rescore(rows, args.gate)
    print(f"\n── overall ({args.json_file}) ──")
    print(f"  {s['n_pass']}/{s['n_total']} PASS = {s['pct']:.1f}%   "
          f"gate ≥{s['gate_pct']:.0f}%: {s['gate']}")
    print(f"  PASS:{s['n_pass']}  FAIL:{s['n_fail']}  WEAK:{s['n_weak']}  ERR:{s['n_err']}")

    print(f"\n── by domain ──")
    dom = domain_breakdown(rows)
    for d in sorted(dom):
        v = dom[d]
        tot = sum(v.values())
        pct = (v.get("PASS", 0) / tot) * 100 if tot else 0
        print(f"  {d:14s}  {v.get('PASS',0):2d}/{tot:2d} PASS ({pct:.0f}%)   "
              f"FAIL:{v.get('FAIL',0)}  WEAK:{v.get('WEAK',0)}  ERR:{v.get('ERR',0)}")

    print(f"\n── WEAK breakdown ──")
    weaks = [r for r in rows if r.get("verdict") == "WEAK"]
    not_promoted   = [r for r in weaks if not r.get("promoted_to_arguments")]
    promo_kw_off   = [r for r in weaks
                      if r.get("promoted_to_arguments")
                      and not r.get("quote_keywords_ok")]
    print(f"  not promoted (low cluster_score/coverage): {len(not_promoted)}")
    print(f"  promoted but keyword off-topic:            {len(promo_kw_off)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
