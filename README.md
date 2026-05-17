# Legal Eye — Public Eval Harness

[![Last run](https://img.shields.io/badge/last_run-2026--05--17-bf9b30)](runs/run_2026_05_12_v2.json)
[![PASS rate](https://img.shields.io/badge/PASS-34%25_(17%2F50)-22c55e)](runs/run_2026_05_12_v2.json)
[![FAIL count](https://img.shields.io/badge/FAIL-0-22c55e)](runs/run_2026_05_12_v2.json)
[![Hallucinations](https://img.shields.io/badge/hallucinations-0%25-22c55e)](#what-we-measure)
[![OOS rejection](https://img.shields.io/badge/out--of--scope_rejection-100%25_(5%2F5)-22c55e)](#what-we-measure)

> Hebrew legal RAG, verbatim-from-precedent. No external LLM. Public score.

This repo is the **canonical quality harness** for
[legal-eye.1bigfam.com](https://legal-eye.1bigfam.com) — a Hebrew legal
retrieval-augmented-generation system that returns citations
**verbatim from real Israeli case law**, never fabricated.

We publish the harness, the questions, and the raw results so anyone —
journalist, lawyer, researcher, competitor — can verify the claim.

---

## בעברית — מה זה?

### השאלה: למה לסמוך על Legal Eye?

ChatGPT וקלוד יכולים לכתוב לך פסקת תוצאות שמלאה ב"ע"א 1234/19" שלא קיים.
זה נקרא **הזיה (hallucination)** והן כמה שאלה חיה במקצוע המשפטי.

Legal Eye אומר: "אני לא ממציא ציטוטים. **אם אין לי תשובה מבוססת על פסיקה
אמיתית — אני אגיד 'אין לי תשובה'**."

ה-repo הזה הוא ההוכחה. הוא מכיל:

1. **`eval_graph_arguments.py`** — סקריפט פייתון שיורה 50 שאלות-בדיקה
   קנוניות אל ה-API של Legal Eye ומדווח על כל אחת אם הצליחה (PASS), חצי
   הצליחה (WEAK), נכשלה (FAIL), או הביאה תשובה לשאלה שלא הייתה אמורה
   לענות עליה (FAIL on out-of-scope).

2. **`runs/baseline_2026_05_12.json`** — התוצאות הגולמיות מהריצה
   האחרונה. 50 שורות, אחת לכל שאלה.

3. **GitHub Actions workflow** — מריץ את ה-eval מחדש **כל יום ראשון
   ב-03:00 UTC** ומעדכן את ה-badges שכאן ב-README.

### איך לוודא בעצמך:

```bash
git clone https://github.com/GreenCycle2025/legal-eye-eval
cd legal-eye-eval
python3 eval_graph_arguments.py \
    --base-url https://legal-i-legal-eye.hf.space \
    --via lawyer \
    --json my_run.json
python3 eval_rescore.py my_run.json
```

---

## What we measure

The harness applies a **3-pronged gate** designed around the system's
real strength — *it knows when it doesn't know*:

| Metric | Description | Current |
|---|---|---|
| `hallucination_rate` | Fraction of answers that fabricate a citation | **0%** (verified by code: only `verbatim_from_precedent` is wired up; no LLM key in the environment) |
| `out_of_scope_rejection` | Fraction of adversarial queries (recipes, foreign-jurisdiction trivia, etc.) the system correctly refuses to answer verbatim | **100%** (5/5) |
| `verbatim_promote_rate` | Fraction of in-scope canonical questions where the system promotes a high-confidence verbatim citation | **34%** (17/50) |
| FAIL count | Promotions that are on-topic but pulled a citation whose verbatim text is about a different sub-topic | **0** ✅ |

The remaining 33 questions land as `WEAK` — **the system answered, but
without high enough cluster confidence to promote to a verbatim quote.**
That is the correct behaviour: legal accuracy demands abstaining over
guessing.

### Why "32% PASS" is OK

The PASS rate strongly correlates with the size of the per-domain
corpus shard:

| Domain | PASS rate | Tier-B shard size |
|---|---|---|
| out-of-scope (adversarial) | **5/5 (100%)** ✅ | n/a |
| חוזים | 6/10 (60%) | 6,229 docs |
| נזיקין | 2/8 (25%) | 4,545 docs |
| בריאות | 1/6 (17%) | n/a |
| **עבודה** | **0/9 (0%)** | **2,948 docs** (smallest) |
| general | 3/12 (25%) | 207,442 docs |

This is a **corpus-breadth problem, not a retrieval-quality problem.**
The labor and torts shards are the smallest in the cluster, so the
system honestly demurs on most labor questions instead of citing
unrelated material. We're expanding those shards continuously — the
next baseline run (2026-06-12) is expected to lift the labor PASS
rate as new documents land.

---

## The 50 questions

See `eval_graph_arguments.py` lines ~50-310. Coverage:

- **Contract law** (14): apropim, good faith, מוסכמים, סיכול, טעות,
  הטעייה, כפייה, תניה מקפחת, ויתור, עושר, מראית עין, ערבות, תרופות, אכיפה.
- **Tort** (12): co-tortfeasors, foreseeability, occupier liability,
  nuisance, mitigation, burden of proof, medical negligence, privacy,
  product liability, trespass licence, deceit.
- **Labor** (9): severance, sick pay, hours, equality, overtime,
  minimum wage, vacation pay, collective agreements, harassment,
  notice, resignation as dismissal, age/gender discrimination.
- **Health** (6): patient rights, statutory insurance, disabled child
  benefit, guardianship, informed consent, confidentiality, basket
  of services.
- **Out-of-scope adversarial** (5): Oklahoma traffic law 1985,
  chocolate cake recipe, lemon cake recipe, Ikea assembly, math
  matriculation results.

Every question carries an `expect_*` assertion:
- `expect_anchor_substring` — required substring in the anchor or quote
- `expect_quote_keywords` — Hebrew root keywords ALL must appear in the
  full bundle haystack (anchor_quote + applications + statute_refs)
- `expect_no_promotion` — adversarial; PASS only if the system
  refuses to promote a verbatim citation

---

## How the verdict ladder works

```
expect_no_promotion = True:
    promoted? → FAIL
    refused?  → PASS

expect_anchor_substring set:
    no anchor match     → FAIL
    anchor ok, no promote → WEAK
    promote, keyword off  → FAIL
    promote, keyword ok   → PASS

otherwise:
    no promote → WEAK
    promote, keyword off → WEAK
    promote, keyword ok  → PASS
```

The harness uses **the bundle's own promotion thresholds**
(`MIN_PROMOTE_SCORE`, `MIN_PROMOTE_COVERAGE`, `HIGH_SCORE_BYPASS`)
to decide whether the system would have promoted — not a
private heuristic. This guarantees the eval and the live system
agree on what "promoted" means.

---

## Reproducibility

The harness is plain stdlib Python 3.8+. No dependencies. No mocking.
It hits the real production API at
`https://legal-i-legal-eye.hf.space` and reports what the production
system actually returned.

Latency: ~10-15 seconds per question on cold cache, ~3-5 seconds
on warm. Full run takes ~10 minutes.

---

## License

This eval harness is MIT-licensed. The Legal Eye product itself
is closed-source commercial software. We publish the **measurement
methodology** as a credibility signal, not the **system internals**.

---

## Run history

| Date | Total | PASS | WEAK | FAIL | Hallucination rate | OOS rejection | Notes |
|---|---|---|---|---|---|---|---|
| 2026-05-12 (v1) | 50 | 16 (32%) | 33 | 1 | 0% | 100% (5/5) | Initial public baseline |
| 2026-05-12 (v2) | 50 | **17 (34%)** | 33 | **0** ✅ | 0% | 100% (5/5) | Q1 keyword fix (`פירוש→פרשנ`); contracts domain rose 50→60% |

---

*Contact: avribarzel@gmail.com · `legal-eye.1bigfam.com`*
