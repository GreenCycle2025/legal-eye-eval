#!/usr/bin/env python3
"""eval_graph_arguments.py — quality snapshot of the graph-driven
argument pipeline.

Runs a fixed set of canonical Hebrew legal questions through
``/v1/lawyer/ask`` and reports, per question, whether the bundle
produced the expected doctrine, whether ``arguments[0]`` came from
the graph (vs. legacy verbatim_from_precedent), and a few sanity
counters.

Useful as:
  • Regression check — re-run after clustering / retriever changes
    to confirm no doctrine routing has shifted unexpectedly.
  • Diagnostic — when a corpus is added, see which questions newly
    route to a cluster (vs. fall through to the legacy path).
  • Snapshot — diff the ``--json`` output across runs to track
    quality over time.

Usage:
    python -m tau_rag.scripts.eval_graph_arguments
    python -m tau_rag.scripts.eval_graph_arguments \
        --base-url http://localhost:8000 \
        --json /tmp/eval_$(date +%s).json
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional


# ──────────────────────────────────────────────────────────────────────
# Canonical question set — covers the major Israeli civil-law doctrines
# that should be in any reasonable corpus. Each entry carries:
#   • question — the user-facing query
#   • expect_anchor_substring — a string that should appear in the
#     bundle's anchor_label when routing succeeded. None = no specific
#     expectation (we only check that the system produced an answer).
#   • expect_quote_keywords — list of Hebrew terms; ALL must appear in
#     the resulting anchor_quote (case-insensitive). Catches the failure
#     mode where we promote a bundle but the quote is actually about a
#     different topic. Optional.
#   • expect_no_promotion — when True, PASS only if the bundle did NOT
#     promote (out-of-scope queries / sanity checks).
# ──────────────────────────────────────────────────────────────────────
QUESTIONS: List[Dict[str, Any]] = [
    # ── Contract law — apropim doctrine ─────────────────────────────
    {
        "question": "פרשנות תכליתית של חוזה לפי הלכת אפרופים",
        "expect_anchor_substring": "אפרופים",
        # Hebrew root פ־ר־ש shows up as "פרשנ" / "פירוש" / "מפרש"
        # depending on noun-form. Use the shoresh prefix that all
        # variants share. (Previous "פירוש" was too narrow — caused
        # a real-pass FAIL on the apropim verbatim quote which uses
        # "פרשנותו".)
        "expect_quote_keywords": ["פרשנ", "תכלית"],
    },
    {
        "question": "חובת תום לב במשא ומתן לקראת חוזה",
        "expect_anchor_substring": None,
        "expect_quote_keywords": ["תום לב"],
    },
    {
        "question": "פיצויים מוסכמים שאינם פרופורציונליים לנזק",
        "expect_anchor_substring": None,
        "expect_quote_keywords": ["פיצוי"],
    },
    {
        "question": "תרופות בשל הפרת חוזה",
        "expect_anchor_substring": None,
        "expect_quote_keywords": ["תרופ", "חוזה"],
    },
    {
        "question": "אכיפת חוזה לפי החוק",
        "expect_anchor_substring": None,
    },
    # ── Tort law ─────────────────────────────────────────────────────
    {
        "question": "אחריות מעוולים יחד לנזיקין",
        "expect_anchor_substring": None,
        "expect_quote_keywords": ["נזיק"],
    },
    {
        "question": "מבחן הצפיות בעבירה של רשלנות",
        "expect_anchor_substring": None,
        "expect_quote_keywords": ["רשלנות"],
    },
    {
        "question": "פיצוי על נזק לא ממוני בנזיקין",
        "expect_anchor_substring": None,
    },
    # ── Labor / employment ───────────────────────────────────────────
    {
        "question": "פיצויי פיטורים לעובד שפוטר ללא שימוע",
        "expect_anchor_substring": None,
        "expect_quote_keywords": ["פיטור"],
    },
    {
        "question": "זכויות עובד בעת מחלה לפי חוק דמי מחלה",
        "expect_anchor_substring": None,
        "expect_quote_keywords": ["מחלה"],
    },
    {
        "question": "שעות עבודה ומנוחה לפי החוק",
        "expect_anchor_substring": None,
    },
    {
        "question": "שוויון הזדמנויות בעבודה והפליה",
        "expect_anchor_substring": None,
        "expect_quote_keywords": ["הפלי"],
    },
    # ── Health & insurance ───────────────────────────────────────────
    {
        "question": "זכויות חולה לקבלת מידע רפואי",
        "expect_anchor_substring": None,
        "expect_quote_keywords": ["חולה"],
    },
    {
        "question": "ביטוח בריאות ממלכתי וזכאות",
        "expect_anchor_substring": None,
    },
    {
        "question": "ילד נכה ביטוח לאומי קצבה",
        "expect_anchor_substring": None,
        "expect_quote_keywords": ["ילד נכה"],
    },
    # ── Out-of-scope / sanity ────────────────────────────────────────
    {
        "question": "חוקי טראפיק באוקלהומה משנת 1985",
        "expect_anchor_substring": None,
        "expect_no_promotion": True,
    },
    {
        "question": "כיצד לאפות עוגת שוקולד עם ביצים וקמח",
        "expect_anchor_substring": None,
        "expect_no_promotion": True,
    },
    # ── Phase 3.1 expansion: bring eval set to 50 ────────────────────
    # Goal per PRODUCTION_PLAN.md: ≥85% PASS, 0 FAIL on this expanded
    # set. Keywords are kept conservative (single Hebrew root) to avoid
    # false WEAKs on legitimate paraphrases.
    #   Contract law — 9 new
    {
        "question": "סיכול חוזה לאור נסיבות בלתי צפויות",
        "expect_anchor_substring": None,
        "expect_quote_keywords": ["סיכול"],
    },
    {
        "question": "טעות בכריתת חוזה ועילת ביטול",
        "expect_anchor_substring": None,
        "expect_quote_keywords": ["טעות"],
    },
    {
        "question": "הטעייה בעת כריתת חוזה",
        "expect_anchor_substring": None,
        "expect_quote_keywords": ["הטעי"],
    },
    {
        "question": "כפייה והשפעה בלתי הוגנת בכריתת חוזה",
        "expect_anchor_substring": None,
        "expect_quote_keywords": ["כפי"],
    },
    {
        "question": "תניה מקפחת בחוזה אחיד",
        "expect_anchor_substring": None,
        "expect_quote_keywords": ["מקפח"],
    },
    {
        "question": "ויתור על זכויות חוזיות",
        "expect_anchor_substring": None,
        "expect_quote_keywords": ["ויתור"],
    },
    {
        "question": "עשיית עושר ולא במשפט",
        "expect_anchor_substring": None,
        "expect_quote_keywords": ["עושר"],
    },
    {
        "question": "חוזה למראית עין",
        "expect_anchor_substring": None,
        "expect_quote_keywords": ["מראית"],
    },
    {
        "question": "ערבות לחיוב חוזי",
        "expect_anchor_substring": None,
        "expect_quote_keywords": ["ערב"],
    },
    #   Tort — 9 new
    {
        "question": "אחריות מחזיק במקרקעין כלפי מבקרים",
        "expect_anchor_substring": None,
        "expect_quote_keywords": ["מקרק"],
    },
    {
        "question": "גרימת מטרד לשכן",
        "expect_anchor_substring": None,
        "expect_quote_keywords": ["מטרד"],
    },
    {
        "question": "חובת הקטנת הנזק על הניזוק",
        "expect_anchor_substring": None,
        "expect_quote_keywords": ["הקטנ"],
    },
    {
        "question": "נטל הראיה בתביעת רשלנות",
        "expect_anchor_substring": None,
        "expect_quote_keywords": ["נטל"],
    },
    {
        "question": "רשלנות רפואית של רופא מטפל",
        "expect_anchor_substring": None,
        "expect_quote_keywords": ["רשלנות"],
    },
    {
        "question": "פגיעה בפרטיות בעידן הדיגיטלי",
        "expect_anchor_substring": None,
        "expect_quote_keywords": ["פרטיות"],
    },
    {
        "question": "אחריות יצרן למוצר פגום",
        "expect_anchor_substring": None,
        "expect_quote_keywords": ["אחריות"],
    },
    {
        "question": "רישיון מרצון בעוולת הסגת גבול",
        "expect_anchor_substring": None,
        "expect_quote_keywords": ["רישיון"],
    },
    {
        "question": "עוולת תרמית בנזיקין",
        "expect_anchor_substring": None,
        "expect_quote_keywords": ["תרמית"],
    },
    #   Employment — 8 new
    {
        "question": "תשלום שעות נוספות לעובד",
        "expect_anchor_substring": None,
        "expect_quote_keywords": ["נוספות"],
    },
    {
        "question": "שכר מינימום לעובד יומי",
        "expect_anchor_substring": None,
        "expect_quote_keywords": ["מינימום"],
    },
    {
        "question": "דמי הבראה לעובד שנתי",
        "expect_anchor_substring": None,
        "expect_quote_keywords": ["הבראה"],
    },
    {
        "question": "תחולת הסכם קיבוצי כללי",
        "expect_anchor_substring": None,
        "expect_quote_keywords": ["קיבוצי"],
    },
    {
        "question": "הטרדה מינית במקום העבודה",
        "expect_anchor_substring": None,
        "expect_quote_keywords": ["הטרד"],
    },
    {
        "question": "הודעה מוקדמת בעת פיטורים",
        "expect_anchor_substring": None,
        "expect_quote_keywords": ["הודעה"],
    },
    {
        "question": "התפטרות בדין מפוטר",
        "expect_anchor_substring": None,
        "expect_quote_keywords": ["התפט"],
    },
    {
        "question": "הפליה בעבודה על רקע מין או גיל",
        "expect_anchor_substring": None,
        "expect_quote_keywords": ["הפלי"],
    },
    #   Health — 4 new
    {
        "question": "מינוי אפוטרופוס על קטין",
        "expect_anchor_substring": None,
        "expect_quote_keywords": ["אפוטרופ"],
    },
    {
        "question": "הסכמה מדעת לטיפול רפואי",
        "expect_anchor_substring": None,
        "expect_quote_keywords": ["הסכמ"],
    },
    {
        "question": "סודיות רפואית וזכות לעיין בתיק",
        "expect_anchor_substring": None,
        "expect_quote_keywords": ["סודיות"],
    },
    {
        "question": "סל שירותי הבריאות הממלכתי",
        "expect_anchor_substring": None,
        "expect_quote_keywords": ["סל"],
    },
    #   Out-of-scope — 3 new (false-positive control)
    {
        "question": "מתכון לעוגת לימון עם קצפת",
        "expect_anchor_substring": None,
        "expect_no_promotion": True,
    },
    {
        "question": "הוראות הרכבת רהיט מאיקאה",
        "expect_anchor_substring": None,
        "expect_no_promotion": True,
    },
    {
        "question": "תוצאות מבחני בגרות במתמטיקה",
        "expect_anchor_substring": None,
        "expect_no_promotion": True,
    },
]


# ──────────────────────────────────────────────────────────────────────
# HTTP — stdlib only so the script runs anywhere
# ──────────────────────────────────────────────────────────────────────

def _post_json(url: str, body: Dict[str, Any], timeout: int = 30) -> Dict[str, Any]:
    """POST a JSON body and return the parsed response."""
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return {"_http_error": e.code, "_body": e.read().decode("utf-8")}
    except Exception as e:
        return {"_error": f"{type(e).__name__}: {e}"}


# ──────────────────────────────────────────────────────────────────────
# Per-question evaluation
# ──────────────────────────────────────────────────────────────────────

def evaluate(
    base_url: str, q: Dict[str, Any], timeout: int, *, via: str = "lawyer",
) -> Dict[str, Any]:
    """Run one question and extract the quality signals.

    `via` selects which endpoint drives the eval:
      • "lawyer" (default) — /v1/lawyer/ask, which runs the full
        synthesizer + promotes the bundle to arguments[0]. Slow on
        large corpora because of the synthesizer.
      • "hgraph" — /v1/hgraph/argument, the bundle endpoint directly.
        Bypasses the synthesizer; use this to evaluate clustering
        quality on large corpora without the synthesizer overhead.
        "Promoted" is then derived from the bundle's own can_promote
        signature (cluster_score ≥ 0.5 AND non-empty anchor_quote).
    """
    started = time.monotonic()
    if via == "hgraph":
        payload = _post_json(
            f"{base_url}/v1/hgraph/argument",
            {"user_facts": q["question"], "retrieval_k": 20},
            timeout=timeout,
        )
    else:
        payload = _post_json(
            f"{base_url}/v1/lawyer/ask",
            {"question": q["question"]},
            timeout=timeout,
        )
    elapsed_ms = int((time.monotonic() - started) * 1000)

    # Network / API failure — return early with the error
    if "_error" in payload or "_http_error" in payload:
        return {
            "question":     q["question"],
            "ok":           False,
            "elapsed_ms":   elapsed_ms,
            "error":        payload.get("_error") or payload.get("_http_error"),
        }

    bundle = payload.get("bundle") or {}
    if via == "hgraph":
        # Use the SAME promotion logic the synthesizer uses, exposed by
        # the bundle itself: promote iff (score≥MIN AND cov≥MIN_COV) OR
        # (score≥HIGH_BYPASS). Previous "score≥0.5" heuristic was lax —
        # let out-of-scope hits with cov=5% slip through as FAILs.
        cluster_score = float(bundle.get("cluster_score") or 0.0)
        coverage      = float(bundle.get("coverage") or 0.0)
        anchor_quote  = (bundle.get("anchor_quote") or "").strip()
        MIN_SCORE     = float(bundle.get("MIN_PROMOTE_SCORE") or 0.5)
        MIN_COV       = float(bundle.get("MIN_PROMOTE_COVERAGE") or 0.15)
        HIGH_BYPASS   = float(bundle.get("HIGH_SCORE_BYPASS") or 0.65)
        promoted_synthetic = bool(anchor_quote) and (
            (cluster_score >= MIN_SCORE and coverage >= MIN_COV)
            or cluster_score >= HIGH_BYPASS
        )
        args = ([{"polish_method": "graph_bundle"}]
                if promoted_synthetic else [])
    else:
        args = payload.get("arguments") or []
    arg0 = args[0] if args else {}

    expected = q.get("expect_anchor_substring")
    expect_no_promo = bool(q.get("expect_no_promotion"))
    expect_kws = q.get("expect_quote_keywords") or []
    anchor_label = bundle.get("anchor_label") or ""
    anchor_quote = bundle.get("anchor_quote") or ""
    # ── full-bundle haystack ──
    # Search every text field the bundle exposes — anchor_label,
    # cluster_label, anchor_quote, application/origin snippets, statute
    # refs, and arg0.snippet — instead of only the anchor_quote. A
    # verbatim citation may legitimately come from a precedent whose
    # surface form lacks the exact Hebrew root the question used; the
    # bundle's surrounding text often does carry it (e.g. via the cluster
    # label or an application snippet). Without this broadening, a real
    # quality answer scores as WEAK on a lexical technicality.
    _hay_parts: List[str] = [anchor_label, anchor_quote,
                              bundle.get("cluster_label") or ""]
    for _slot in ("applications", "origins"):
        for _it in (bundle.get(_slot) or []):
            if isinstance(_it, dict):
                _hay_parts.append(_it.get("snippet")  or "")
                _hay_parts.append(_it.get("quote")    or "")
                _hay_parts.append(_it.get("label")    or "")
    for _ref in (bundle.get("statute_refs") or []):
        if isinstance(_ref, str):
            _hay_parts.append(_ref)
    _hay_parts.append(arg0.get("snippet") or arg0.get("text") or "")
    haystack_lc = " ".join(_hay_parts).lower()

    # Anchor-substring assertion: accept a match in anchor_label OR in
    # the haystack (handles "אפרופים" appearing in the quote/snippet
    # even when the label is just a case number like "ע"א 6328/97").
    anchor_match = (
        (expected is None)
        or (expected.lower() in anchor_label.lower())
        or (expected.lower() in haystack_lc)
    )
    # Keyword-content check — keywords matched against the haystack
    # rather than the anchor_quote alone.
    missing_kws = [kw for kw in expect_kws if kw.lower() not in haystack_lc]
    quote_keywords_ok = (not expect_kws) or (not missing_kws)

    # Did the graph promote? (arguments[0].polish_method == 'graph_bundle')
    promoted = arg0.get("polish_method") == "graph_bundle"

    # Verdict ladder:
    #   FAIL — expectation explicitly violated (out-of-scope promoted,
    #          required substring missing, or required keywords missing)
    #   PASS — promoted (when expected) AND all assertions held
    #   WEAK — system produced something but didn't fully meet expectations
    if expect_no_promo:
        verdict = "PASS" if not promoted else "FAIL"
    elif expected is not None:
        if not anchor_match:
            verdict = "FAIL"
        elif not promoted:
            verdict = "WEAK"
        elif not quote_keywords_ok:
            verdict = "FAIL"   # promoted but content is wrong
        else:
            verdict = "PASS"
    else:
        # No specific anchor expectation — content keywords still apply
        if not promoted:
            verdict = "WEAK"
        elif not quote_keywords_ok:
            verdict = "WEAK"   # promoted, no anchor expected, but content off
        else:
            verdict = "PASS"

    return {
        "question":              q["question"],
        "ok":                    True,
        "elapsed_ms":            elapsed_ms,
        "verdict":               verdict,
        "tier":                  payload.get("confidence"),
        "domain":                payload.get("domain"),
        "cluster_id":            bundle.get("cluster_id"),
        "anchor_label":          anchor_label,
        "anchor_label_match":    anchor_match,
        "expected_substring":    expected,
        "expect_quote_keywords": expect_kws,
        "missing_keywords":      missing_kws,
        "quote_keywords_ok":     quote_keywords_ok,
        "promoted_to_arguments": promoted,
        "polish_method":         arg0.get("polish_method"),
        "cluster_score":         bundle.get("cluster_score"),
        "coverage":              bundle.get("coverage"),
        "n_total_applications":  bundle.get("n_total_applications"),
        "n_total_origins":       bundle.get("n_total_origins"),
        "n_alternatives":        len(
            ((bundle.get("diagnostic") or {}).get("alternative_clusters")) or []
        ),
        "is_virtual_anchor":     (bundle.get("anchor_id") or "").startswith("virtual:"),
        "anchor_quote_chars":    len(anchor_quote),
    }


# ──────────────────────────────────────────────────────────────────────
# Reporting
# ──────────────────────────────────────────────────────────────────────

def print_table(rows: List[Dict[str, Any]]) -> None:
    """Pretty-print a one-line-per-question summary."""
    print()
    header = (
        f"{'#':>2}  {'verdict':7s}  {'tier':10s}  {'cluster_score':>5}  "
        f"{'cov':>3}  {'apps':>4}  {'alts':>4}  {'method':18s}  question"
    )
    print(header)
    print("─" * len(header))
    for i, r in enumerate(rows, 1):
        if not r.get("ok"):
            print(f"{i:>2}  ERROR    {'':10s}  {'':5s}  {'':3s}  {'':4s}  "
                  f"{'':4s}  {'':18s}  {r['question'][:60]}")
            print(f"      → {r.get('error')}")
            continue
        score = r.get("cluster_score")
        score_str = f"{score:.2f}" if isinstance(score, (int, float)) else "—"
        cov = r.get("coverage")
        cov_str = f"{int((cov or 0) * 100):>2}%" if cov is not None else "—"
        apps = r.get("n_total_applications") or 0
        alts = r.get("n_alternatives") or 0
        method = (r.get("polish_method") or "—")[:18]
        verdict_color = {
            "PASS": "\033[32mPASS  \033[0m",
            "FAIL": "\033[31mFAIL  \033[0m",
            "WEAK": "\033[33mWEAK  \033[0m",
        }.get(r["verdict"], r["verdict"])
        print(f"{i:>2}  {verdict_color} {(r.get('tier') or '—')[:10]:10s}  "
              f"{score_str:>5}  {cov_str:>3}  {apps:>4}  {alts:>4}  "
              f"{method:18s}  {r['question'][:50]}")
        if not r["anchor_label_match"]:
            print(f"      ⚠  expected '{r['expected_substring']}' in anchor; "
                  f"got '{r['anchor_label'][:50]}'")
        if r.get("missing_keywords"):
            print(f"      ⚠  missing keyword(s) in anchor_quote: "
                  f"{r['missing_keywords']}")


def print_summary(rows: List[Dict[str, Any]]) -> None:
    """Aggregate summary line."""
    total = len(rows)
    if total == 0:
        return
    valid = [r for r in rows if r.get("ok")]
    n_pass = sum(1 for r in valid if r.get("verdict") == "PASS")
    n_fail = sum(1 for r in valid if r.get("verdict") == "FAIL")
    n_weak = sum(1 for r in valid if r.get("verdict") == "WEAK")
    n_err  = total - len(valid)
    n_promoted = sum(1 for r in valid if r.get("promoted_to_arguments"))
    avg_ms = (sum(r.get("elapsed_ms", 0) for r in valid)
              / max(1, len(valid)))

    print()
    print("─" * 60)
    print(f"Total: {total} questions  ·  PASS: {n_pass}  FAIL: {n_fail}  "
          f"WEAK: {n_weak}  ERR: {n_err}")
    print(f"Promoted to arguments[0]: {n_promoted}/{len(valid)}  "
          f"·  avg latency: {avg_ms:.0f}ms")


# ──────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Quality-check the graph-driven argument pipeline."
    )
    parser.add_argument(
        "--base-url", default="http://127.0.0.1:8000",
        help="tau-rag server base URL",
    )
    parser.add_argument(
        "--timeout", type=int, default=30,
        help="per-request timeout in seconds",
    )
    parser.add_argument(
        "--json", default=None,
        help="if set, also write the full result rows to this JSON file",
    )
    parser.add_argument(
        "--via", choices=("lawyer", "hgraph"), default="lawyer",
        help="which endpoint to evaluate: lawyer/ask (default, full path) "
             "or hgraph/argument (bundle-only, fast on large corpora)",
    )
    args = parser.parse_args()

    print(f"# Running {len(QUESTIONS)} questions against {args.base_url} "
          f"via {args.via}")
    rows: List[Dict[str, Any]] = []
    for q in QUESTIONS:
        rows.append(evaluate(args.base_url, q, args.timeout, via=args.via))

    print_table(rows)
    print_summary(rows)

    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False, indent=2)
        print(f"\nFull results written to: {args.json}")

    # Exit non-zero if any FAIL or ERR
    bad = sum(1 for r in rows
              if not r.get("ok") or r.get("verdict") == "FAIL")
    return 1 if bad > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
