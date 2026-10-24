# Legal Eye — Public Eval Harness

<!-- generated:badges -->
[![Last run](https://img.shields.io/badge/last_run-2026--10--18-bf9b30)](runs/latest.json)
[![PASS rate](https://img.shields.io/badge/PASS-28%25_(14%2F50)-22c55e)](runs/latest.json)
[![FAIL count](https://img.shields.io/badge/FAIL-0-22c55e)](runs/latest.json)
[![Hallucinations](https://img.shields.io/badge/hallucinations-0%25-22c55e)](#what-we-measure)
[![OOS rejection](https://img.shields.io/badge/out--of--scope_rejection-100%25_(5%2F5)-22c55e)](#what-we-measure)
<!-- /generated:badges -->

> Hebrew legal RAG, verbatim-from-precedent. No external LLM. Public score.


## What this demonstrates

This repository is a public proof-of-work artifact for a production AI system, not a demo notebook.

- **Grounded retrieval:** answers are tied to real Israeli case-law text.
- **Evaluation discipline:** canonical questions, adversarial out-of-scope cases, raw results and a repeatable scoring harness.
- **Fail-closed behavior:** the system prefers abstention over unsupported citation.
- **Production verification:** the harness calls the live API rather than mocked fixtures.
- **Automation:** GitHub Actions reruns the evaluation on a schedule and exposes regression signals publicly.

Current published safety results: **0% fabricated citations**, **100% out-of-scope rejection (5/5)** and **0 FAIL** on the latest canonical 50-question evaluation.

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

2. **`runs/run_YYYY_MM_DD.json`** — התוצאות הגולמיות של כל ריצה,
   50 שורות, אחת לכל שאלה; `runs/latest.json` מסכם את האחרונה.

3. **GitHub Actions workflow** — מריץ את ה-eval מחדש **כל יום ראשון
   ב-03:00 UTC** ומעדכן את ה-badges שכאן ב-README.

### איך לוודא בעצמך:

```bash
git clone https://github.com/GreenCycle2025/legal-eye-eval
cd legal-eye-eval
python3 eval_graph_arguments.py \
    --base-url https://legal-eye-api.1bigfam.com \
    --via lawyer --pace 2.5 --retries 1 --wait-ready 300 --timeout 90 \
    --json my_run.json
python3 eval_rescore.py my_run.json
```

---

## What we measure

The harness applies a **3-pronged gate** designed around the system's
real strength — *it knows when it doesn't know*:

| Metric | Description |
|---|---|
| `hallucination_rate` | Fraction of answers that fabricate a citation: 0% by construction (only `verbatim_from_precedent` is wired up; no LLM key in the environment) |
| `out_of_scope_rejection` | Fraction of adversarial queries (recipes, foreign-jurisdiction trivia, etc.) the system correctly refuses to answer verbatim |
| PASS | In-scope questions where the system promotes a verbatim citation that carries the expected case and keywords |
| WEAK | The system answered, but did not promote a verbatim quote that meets the bar; it abstains rather than guess |
| FAIL | A promotion that pulled a citation about a different sub-topic, or an out-of-scope question answered |
| No answer | The request failed (timeout, HTTP error); not a verdict on the answer |

These numbers are generated from the run files by `render_readme.py`; the
weekly workflow rewrites them, and a test fails when they are out of date.

<!-- generated:latest -->
**Latest run: 2026-10-18** ([raw rows](runs/run_2026_10_18.json), [summary](runs/latest.json))

| Questions | PASS | WEAK | FAIL | No answer (error) | Out-of-scope refused |
|---|---|---|---|---|---|
| 50 | 14 (28%) | 33 | 0 | 3 | 5/5 |

The launch gate is 85% PASS (43/50): not met. From the next run it counts the strict authority verdict.

By topic (keyword buckets of `eval_rescore.domain_breakdown`):

| Topic | Questions | PASS | WEAK | FAIL | No answer |
|---|---|---|---|---|---|
| out-of-scope | 5 | 5 | 0 | 0 | 0 |
| אחר | 12 | 2 | 9 | 0 | 1 |
| בריאות | 6 | 1 | 5 | 0 | 0 |
| חוזים | 10 | 4 | 4 | 0 | 2 |
| נזיקין | 8 | 2 | 6 | 0 | 0 |
| עבודה | 9 | 0 | 9 | 0 | 0 |
<!-- /generated:latest -->

### Where it is weak, and what the 50 questions do not show

- **Corpus scope.** The corpus is the Supreme Court of Israel only, a 2022
  snapshot (751,194 documents, most of them interim decisions). Labour-court
  rulings are not in it, which is why the labour questions stay WEAK, and
  nothing after 2022 is.
- **Tuned on these questions.** The answer engine was developed against
  these 50 questions, so their score is optimistic. On a frozen test set
  written after the method was final and never used for tuning (40
  questions, 30 of them legal), the same engine scored 28 PASS, 11 WEAK and
  1 FAIL, 19 of 30 on the legal questions, measured offline on 2026-10-23.
  That is the estimate to quote for questions it has not seen.

---

## Strict authority verdict

Since 2026-10-24 every question has two verdicts. `verdict` is the ladder
below, unchanged. `strict_verdict` applies the same ladder and adds one
condition: the answer must rest on the right authority.

An answer is a strict FAIL when it is promoted and one of these holds:

- it rests on another legal domain than the question's;
- it does not name the governing authority where one is unambiguous, for
  example the Sick Pay Law for sick pay or the Defective Products Liability
  Law for product liability (`authority_expectations_v2.py`);
- it comes from another source document than the one a suite requires
  (`expect_source_doc_id`, benchmark v3).

A plausible answer supported by an unrelated authority used to count as
PASS. It no longer counts.

**The launch gate counts the strict verdict:** 85% strict PASS on the 50
questions (43/50). The weekly run publishes both verdicts.

## Benchmark v2: 500-case robustness holdout

The 50 canonical questions remain the public production score. In addition, this repo now carries a separate **500-case robustness suite** at `benchmarks/benchmark_v2_500.json`. It is an official set for robustness, not a separate gate: a release must not score clearly lower on the 450 holdout variants than on the 50 canonical questions, since that gap is the sign of tuning to the wording.

This is intentionally described as **50 independent canonical cases × 10 deterministic wording/stress variants**, not as 500 independent legal doctrines. The extra 450 cases are holdout transformations used to detect prompt-surface overfitting after tuning on the canonical set.

The holdout covers concise/formal phrasing, evidence-only requests, anti-hallucination wording, harmless context noise, punctuation/spacing noise, current-law framing, source-coercion resistance, and a facts/question wrapper. Each row preserves the original `expect_*` assertions and contains provenance back to its source question.

```bash
python3 benchmark_v2.py --check benchmarks/benchmark_v2_500.json
python3 -m unittest -v test_benchmark_v2.py
python3 eval_graph_arguments.py \
  --suite benchmarks/benchmark_v2_500.json \
  --base-url https://legal-i-legal-eye.hf.space \
  --via hgraph \
  --json /tmp/legal-eye-benchmark-v2.json
python3 benchmark_v2_report.py /tmp/legal-eye-benchmark-v2.json
```

The v2 reporter keeps canonical and holdout scores separate and derives out-of-scope rejection from suite metadata. No v2 score is shown in the production badges until a complete run has actually been executed.

---

## Benchmark v3: independent doctrines

`benchmarks/benchmark_v3_independent_100.json` has 100 cases: 80 Israeli-law
questions on topics the engine was not tuned on, 10 in each of 8 groups, and
20 out-of-scope controls. An in-scope case passes only when the answer
comes from the frozen primary-law source, the statute section in
`expect_source_doc_id`. A plausible answer from the wrong source is a FAIL.
Details: `benchmarks/README_v3.md`.

Its sources are statute sections (`heb_law/...`). The production corpus
does not serve them yet: they come with the statutes extension of
legal-eye's authoritative-statutes work. Until that is live, v3 measures
something production cannot do, so it is not part of the gate yet. Once it
is live, v3 is run once against production and becomes a second gate,
X% PASS, set by the owner. X will be no lower than that first measurement,
and the target is 60%.

```bash
python3 benchmark_v3.py --check benchmarks/benchmark_v3_independent_100.json
python3 eval_graph_arguments.py --suite benchmarks/benchmark_v3_independent_100.json \
  --base-url https://legal-eye-api.1bigfam.com --pace 2.5 --json /tmp/legal-eye-v3.json
python3 benchmark_v3_report.py /tmp/legal-eye-v3.json --suite benchmarks/benchmark_v3_independent_100.json
```

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
It hits the real production API at its public address,
`https://legal-eye-api.1bigfam.com` (the same address the site calls), and
reports what the production system actually returned. The address allows
each client 0.5 questions per second with a burst of 20, so a run is paced
(`--pace 2.5`); it first waits for `/readyz` (`--wait-ready`) because a
sleeping server takes a while to start, and a question that got no answer
at all is asked once more (`--retries 1`). An answered question is never
asked again, whatever its verdict. A full run takes about 4 minutes.

### Uptime

`.github/workflows/uptime.yml` runs `monitor.py` every 15 minutes: the
public address must answer `/readyz` and `/v1/corpus/selftest`, and the
`x-proxied-replica` header tells whether the Hugging Face Space or the
standby server answered. A problem that survives three attempts a minute
apart opens an issue in this repository; its end closes the issue.

---

## License

This eval harness is MIT-licensed. The Legal Eye product itself
is closed-source commercial software. We publish the **measurement
methodology** as a credibility signal, not the **system internals**.

---

## Run history

Every run in `runs/`, generated by `render_readme.py` from the run files as
they are stored.

<!-- generated:history -->
| Run | Questions | PASS | WEAK | FAIL | No answer |
|---|---|---|---|---|---|
| [2026-05-12](runs/run_2026_05_12.json) | 50 | 17 (34%) | 33 | 0 | 0 |
| [2026-05-12 (v2)](runs/run_2026_05_12_v2.json) | 50 | 17 (34%) | 33 | 0 | 0 |
| [2026-05-17](runs/run_2026_05_17.json) | 50 | 17 (34%) | 32 | 0 | 1 |
| [2026-05-24](runs/run_2026_05_24.json) | 50 | 17 (34%) | 33 | 0 | 0 |
| [2026-05-31](runs/run_2026_05_31.json) | 50 | 17 (34%) | 33 | 0 | 0 |
| [2026-06-07](runs/run_2026_06_07.json) | 50 | 17 (34%) | 33 | 0 | 0 |
| [2026-06-14](runs/run_2026_06_14.json) | 50 | 17 (34%) | 33 | 0 | 0 |
| [2026-06-21](runs/run_2026_06_21.json) | 50 | 0 (0%) | 0 | 0 | 50 |
| [2026-06-28](runs/run_2026_06_28.json) | 50 | 17 (34%) | 33 | 0 | 0 |
| [2026-07-05](runs/run_2026_07_05.json) | 50 | 0 (0%) | 0 | 0 | 50 |
| [2026-07-12](runs/run_2026_07_12.json) | 50 | 12 (24%) | 33 | 0 | 5 |
| [2026-07-19](runs/run_2026_07_19.json) | 50 | 17 (34%) | 33 | 0 | 0 |
| [2026-07-26](runs/run_2026_07_26.json) | 50 | 17 (34%) | 33 | 0 | 0 |
| [2026-08-02](runs/run_2026_08_02.json) | 50 | 17 (34%) | 33 | 0 | 0 |
| [2026-08-09](runs/run_2026_08_09.json) | 50 | 17 (34%) | 33 | 0 | 0 |
| [2026-08-16](runs/run_2026_08_16.json) | 50 | 17 (34%) | 31 | 0 | 2 |
| [2026-08-23](runs/run_2026_08_23.json) | 50 | 17 (34%) | 33 | 0 | 0 |
| [2026-08-30](runs/run_2026_08_30.json) | 50 | 11 (22%) | 12 | 0 | 27 |
| [2026-09-06](runs/run_2026_09_06.json) | 50 | 17 (34%) | 32 | 0 | 1 |
| [2026-09-13](runs/run_2026_09_13.json) | 50 | 13 (26%) | 25 | 0 | 12 |
| [2026-09-20](runs/run_2026_09_20.json) | 50 | 13 (26%) | 33 | 0 | 4 |
| [2026-09-27](runs/run_2026_09_27.json) | 50 | 17 (34%) | 33 | 0 | 0 |
| [2026-10-04](runs/run_2026_10_04.json) | 50 | 17 (34%) | 33 | 0 | 0 |
| [2026-10-11](runs/run_2026_10_11.json) | 50 | 17 (34%) | 33 | 0 | 0 |
| [2026-10-18](runs/run_2026_10_18.json) | 50 | 14 (28%) | 33 | 0 | 3 |
<!-- /generated:history -->

---|---|---|---|---|---|---|---|
| 2026-05-12 (v1) | 50 | 16 (32%) | 33 | 1 | 0% | 100% (5/5) | Initial public baseline |
| 2026-05-12 (v2) | 50 | **17 (34%)** | 33 | **0** ✅ | 0% | 100% (5/5) | Q1 keyword fix (`פירוש→פרשנ`); contracts domain rose 50→60% |
| 2026-09-27 | 50 | **17 (34%)** | 33 | **0** ✅ | 0% | 100% (5/5) | Weekly run; no safety regression |
| 2026-10-04 | 50 | **17 (34%)** | 33 | **0** ✅ | 0% | 100% (5/5) | Scheduled public regression run; no safety regression |

---

*Contact: avri75154@gmail.com · `legal-eye.1bigfam.com`*
