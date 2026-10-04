# Legal Eye Benchmark v2

`benchmark_v2_500.json` is a **500-case robustness suite**, not a claim of 500 independent legal doctrines.

## Composition

- 50 canonical legal/OOS cases from `eval_graph_arguments.py`
- 10 deterministic variants per canonical case
- 500 total cases
- 50 canonical cases
- 450 holdout robustness cases

Each derived case carries:

- `case_id`
- `base_case_id`
- `variant_kind`
- `split`
- `source_question`
- `source_question_sha256`
- the unchanged canonical `expect_*` assertions

The nine holdout transformations test wording robustness without changing the intended legal question: concise wording, formal Israeli-law framing, evidence-only requests, anti-hallucination instructions, harmless context noise, punctuation/spacing noise, current-law framing, source-coercion resistance, and a facts/question wrapper.

## Rebuild and verify

```bash
python3 benchmark_v2.py --out benchmarks/benchmark_v2_500.json
python3 benchmark_v2.py --check benchmarks/benchmark_v2_500.json
python3 -m unittest -v test_benchmark_v2.py
```

The checked-in suite is deterministic and includes its own `suite_sha256`.

## Run all 500 cases

```bash
python3 eval_graph_arguments.py \
  --suite benchmarks/benchmark_v2_500.json \
  --base-url https://legal-i-legal-eye.hf.space \
  --via hgraph \
  --json /tmp/legal-eye-benchmark-v2.json
```

For parallel execution, use ten stable shards. With `--shard-count 10`, shard 0 is the canonical 50 and shards 1–9 each contain one holdout transformation across all 50 base cases:

```bash
for i in $(seq 0 9); do
  python3 eval_graph_arguments.py \
    --suite benchmarks/benchmark_v2_500.json \
    --shard-count 10 \
    --shard-index "$i" \
    --base-url https://legal-i-legal-eye.hf.space \
    --via hgraph \
    --json "/tmp/legal-eye-benchmark-v2-shard-${i}.json" &
done
wait
```

## Interpretation

This suite is meant to detect **overfitting and prompt-surface fragility** after tuning on the canonical 50. It does not replace a future independent-doctrine benchmark built from additional legal topics and time/version-specific source material.

## Report a completed 500-case run

```bash
python3 benchmark_v2_report.py /tmp/legal-eye-benchmark-v2.json \
  --suite benchmarks/benchmark_v2_500.json \
  --json-out /tmp/legal-eye-benchmark-v2-summary.json
```

The reporter keeps canonical and holdout rates separate, reports each transformation independently, and derives OOS rejection from the suite metadata rather than from string matching.
