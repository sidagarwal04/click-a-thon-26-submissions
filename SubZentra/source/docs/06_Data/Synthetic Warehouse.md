---
id: data-synthetic-warehouse
title: Synthetic Warehouse
type: data-model
status: active
owner: unassigned
source: repository
created: 2026-07-29
updated: 2026-07-29
reviewed: 2026-07-29
confidence: verified
implementation: current
priority: high
tags: [data, warehouse, synthetic]
related: ["[[Data MOC]]", "[[Cube Semantic Model]]", "[[Semantic Modeling]]"]
repo_path: infra/warehouse/init/001_ecommerce_seed.sql
code_refs:
  - infra/warehouse/init/001_ecommerce_seed.sql
  - infra/cube/tests/eu-refund-spike.json
---

# Synthetic Warehouse

The separate warehouse Postgres database contains deterministic e-commerce
fixtures for customers, products, orders, order items, payments, refunds,
shipments, geography, and refund reasons.

It is development/test infrastructure, not the ZentraOS transactional control
plane and not a production customer-data store.

The seed guarantees two scenarios, chosen so that one cannot clear the
confidence threshold and the other can.

`eu_refund_spike` — `001_ecommerce_seed.sql`:

| Month | EU orders | Refund amount | Refund rate |
| --- | ---: | ---: | ---: |
| June 2026 | 4 | $20 | 25% |
| July 2026 | 4 | $260 | 75% |

July's increase is associated with shipping-delay refunds — an association the
data shows and a cause it cannot establish. Eight orders sits in the under-30
band, so confidence is capped at 0.65 against a 0.7 threshold and the
investigation always gates.

`na_channel_growth` — `002_na_channel_growth.sql`:

| Month | web | partner | orders | revenue |
| --- | ---: | ---: | ---: | ---: |
| October 2026 | 100 × $100 | 20 × $150 | 120 | $13,000 |
| November 2026 | 100 × $100 | 80 × $150 | 180 | $22,000 |

Web is identical across both months, so the entire $9,000 increase is partner.
Three hundred orders clears the 100-record band, so nothing caps a confident
answer and the investigation can publish without review.

The second seed is **disjoint** from the first on both axes the EU scenario
filters — region `NA`, and dates from October where the first seed ends on
2026-07-28. The recorded cassettes key on prompt text containing the query
result, so one extra row in the EU June–July slice would invalidate every
recording. `nx run evals:replay` is the contamination check.

Both seeds keep one `order_items` row per order. `commerce_facts` inner-joins
it, so a second item would duplicate the order and make every sum measure
double-count it.

Parent: [[Data MOC]]
