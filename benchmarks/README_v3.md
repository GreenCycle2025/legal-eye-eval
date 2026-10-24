# Legal Eye Benchmark v3

`benchmark_v3_independent_100.json` is an **independent-doctrine benchmark**. It is designed to answer the question that benchmark v2 cannot: does retrieval generalize beyond the 50 canonical topics that guided earlier tuning?

## Composition

- 80 in-scope Israeli-law cases
- 8 legal groups, 10 cases each
- 80 unique primary-law source documents
- 20 out-of-scope controls
- 100 total cases

The 80 legal source documents were frozen before evaluation using a deterministic stratified hash selection. The selection excluded every document that appeared as either the final quote document or in the top-10 fused retrieval set of the 50 canonical benchmark-v2 cases in the reference seed0 run.

The groups are:

- contracts
- torts
- labor
- family
- corporate
- evidence/procedure
- health/social security
- consumer/privacy/banking

## Harder pass criterion

For an in-scope v3 case, promotion alone is not enough. PASS requires the final evidence document to match the frozen `expect_source_doc_id` exactly. A plausible answer supported by the wrong authority is a FAIL.

Out-of-scope cases PASS only when the graph does not promote.

## Prompt construction

Each legal case uses the section topic but never exposes the section number. Ambiguous short titles may include the statute name; more distinctive titles use only a legal-domain hint.

The frozen source manifest is `benchmark_v3_sources.json`. It contains provenance and source-text hashes, not the full legal text.

## Validate

```bash
python3 benchmark_v3.py --check benchmarks/benchmark_v3_independent_100.json
python3 -m unittest -v test_benchmark_v3.py
```

## Run

```bash
python3 eval_graph_arguments.py \
  --suite benchmarks/benchmark_v3_independent_100.json \
  --base-url https://legal-i-legal-eye.hf.space \
  --via hgraph \
  --json /tmp/legal-eye-benchmark-v3.json
```

## Report

```bash
python3 benchmark_v3_report.py /tmp/legal-eye-benchmark-v3.json \
  --suite benchmarks/benchmark_v3_independent_100.json \
  --json-out /tmp/legal-eye-benchmark-v3-summary.json
```

## Interpretation

This benchmark measures unseen **doctrine/section coverage** and exact primary-source selection. It is not yet a full temporal-law benchmark. Historical-version questions, conflicting-authority cases, and sources intentionally withheld from the retrieval corpus should be added as separate future suites rather than being claimed by this one.
