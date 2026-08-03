# Submission artifacts

Generated evidence for the Atlys track. Everything here was produced by
pipeline runs against ClickHouse Cloud database `atlys` on 2 August 2026 and
exported unmodified from the warehouse — no hand-written substitutes.

Source of truth in ClickHouse: `generated_artifacts`, `context_versions`, and
`agent_runs`.

## Layout

```text
submission_artifacts/
├── all_generated_ddl.sql              Every generated CREATE TABLE, in one file
├── 01_express_checkout/
├── 02_group_family/
├── 03_status_sharing/
├── 04_abandoned_checkout_recovery/
├── 05_instant_forex/
│   └── schema.sql                     Generated DDL (with run/trace header)
├── 06_promo_coupon_checkout/          SEALED SIXTH SPEC
│   ├── schema.sql                     Generated DDL
│   ├── insight-summary.md             Product-facing insight summary
│   ├── insights.json                  Full findings with evidence and caveats
│   └── trace.json                     Mandatory sixth-spec trace reference
└── context/
    ├── before.json                    v1 — base context over the 8 existing tables
    ├── after.json                     v7 — after all six features landed
    ├── v1.json … v7.json              Every version, complete
    └── changelog.md                   Before/after freshness proof
```

Each run's remaining artifacts — event profile, instrumentation and
materialization plans, proposed and validated analysis plans, aggregate query
results, insights, and context diff — stay in the ClickHouse
`generated_artifacts` table and are reachable through the API
(`GET /api/v1/runs/{run_id}/...`).

## Feature runs

| # | Feature | Generated table | Rows | Context | Langfuse trace |
|---|---|---|---|---|---|
| 1 | `express_checkout_f1` | `express_checkout_events` | 5,507 | v2 | `afe6fc2f03c251785404f325e06ad0e3` |
| 2 | `group_family_f2` | `group_application_events` | 5,453 | v3 | `adb389ca213bd869be811ad0d2d0305b` |
| 3 | `status_sharing_f3` | `visa_status_sharing_events` | 6,503 | v4 | `089db6c8c215922bc2cac20d2b5817b1` |
| 4 | `abandoned_checkout_recovery_f4` | `abandoned_checkout_recovery_events` | 5,919 | v5 | `209fbbbae9d7bdfa4ba539f658083ba3` |
| 5 | `instant_forex_f5` | `instant_forex_addon_events` | 6,237 | v6 | `97e9e1246e32c240e5ce500011f49f6a` |
| **6** | **`unseen_f6` (sealed)** | **`promo_coupon_checkout_events`** | **5,363** | **v7** | **`e18e58f7f9d834c17e9b52f42f2aa851`** |

## Context freshness

[`context/changelog.md`](./context/changelog.md) documents the proof: the
context layer grew from 5 relationships / 7 metrics (v1, base) to 11
relationships / 34 metrics (v7) as each feature table landed, with the 27 new
metric names listed and the conflicts the Context Agent detected rather than
silently resolved.

The v6 → v7 step is the strongest evidence: it absorbed the **sealed sixth
spec**, a table unseen when v6 was written, adding `coupon_apply_rate`,
`coupon_rejection_rate`, `checkout_with_coupon_rate`, and
`total_discount_amount` with no code change.

## Still to be added

- `standard_probes/` — the four mandatory probe outputs and their traces
- Shared or exported Langfuse traces to accompany the trace IDs above

## Reproducing any bundle

```bash
uv run --project backend atlys-pipeline --feature <feature>
```
