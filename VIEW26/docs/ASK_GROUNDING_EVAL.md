# Ask FeatureLens grounding evaluation

This suite answers a stricter question than “did the endpoint return a plausible answer?”:

> Does the Ask response reproduce the truth in the retained ClickHouse feature table, answer the dimensions actually requested, and preserve the context-layer trust contract?

## Independent oracle

`validate-ask` fetches each completed feature run and calls the live `POST /api/questions` endpoint. It does **not** reuse the SQL returned by Ask. Expected values are independently recomputed from the run's retained-table NDJSON snapshot.

For `use_existing_data` replays, that snapshot was read from ClickHouse and the run can only complete after exact row-count and event-ID fingerprint verification. This makes it a stable, credential-free oracle over the same physical table contents while keeping the implementation independent from the analytics SQL planner.

## What is checked

| Risk | Test oracle / gate |
|---|---|
| Row counts look right but use the wrong grain | Recompute entrants and outcomes as distinct applications, users, groups, or shares rather than event-row counts. |
| A later event changes a dimension | Attribute segment membership at the governed entrant event and then carry the entity outcome forward. |
| Nulls create fake cohorts | Apply explicit null semantics and reject unexpected evidence rows. |
| Percentiles or rates drift | Reproduce ClickHouse exact-quantile selection and governed rounding; compare numbers with a tight tolerance. |
| The answer uses a different table | Extract every `FROM` / `JOIN` table from SQL and require it in `allowed_tables`. |
| Evidence exists but does not answer the question | Infer explicitly requested dimensions from the question and require both contract declaration and returned aggregate rows. |
| LLM prose changes the facts | Require every stated percentage to exist in structured evidence and require ranked answers to name their evidence-backed best/worst cohort. |
| Trace and answer diverge | Require a completed ClickHouse trace step whose SQL exactly matches the insight SQL. |
| Context/schema provenance drifts | Require contract and insight context/schema versions to agree. |
| Unsupported meaning is guessed | Probe an ungoverned residence-city question and require `not_answerable`, empty SQL, `not_executed`, and a skipped query step. |
| Scope/version controls are bypassed | Require unknown features and unconsented stale context versions to be rejected. |

The table oracle covers feature completion, group-size completion, group churn, document bottlenecks, segment completion, platform failure, latency, adoption, funnel diagnosis, trends, and all four recovery playbooks.

Cross-table Express-vs-standard conversion is intentionally marked `partial`: the feature cohort is independently verified, but a credential-free retained feature snapshot cannot reconstruct `atlys.pay_now_clicked` and `atlys.purchase_completed`. A CI environment with a separate read-only ClickHouse oracle should verify those control-cohort fields before this case is promoted to `full`.

## Run

Start FeatureLens with the five retained feature runs published, then run:

```bash
cd backend
go run ./cmd/validate-ask
```

Useful variants:

```bash
go run ./cmd/validate-ask -feature "Express Checkout"
go run ./cmd/validate-ask -json > ask-grounding-report.json
go run ./cmd/validate-ask -api-url http://localhost:8080
```

The command exits non-zero when any Ask answer or boundary gate fails. A partial but truthful control-cohort case is reported separately and does not fail solely because it is partial.

Unit tests deliberately inject duplicate events, altered rates, unauthorized tables, broken traces, omitted dimensions, invented prose percentages, and answer/evidence ranking conflicts:

```bash
cd backend
go test ./internal/eval
```

## Release policy

For credibility, use these gates:

1. No `table_truth`, allowlist, trace, provenance, prose, or answer-anchor failures.
2. No requested dimension may be absent from either the analysis contract or aggregate evidence.
3. Every unsupported semantic request must fail closed.
4. Partial cases must remain visibly partial; they cannot be counted as fully grounded.
5. Promote a release only after the full suite passes against the exact retained tables used by the deployed context version.
