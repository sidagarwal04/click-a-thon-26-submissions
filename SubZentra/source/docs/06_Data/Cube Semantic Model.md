---
id: data-cube-semantic-model
title: Cube Semantic Model
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
tags: [data, cube, semantic-model]
related: ["[[Data MOC]]", "[[Synthetic Warehouse]]", "[[Cube Adapter]]"]
repo_path: infra/cube/model/cubes/Commerce.js
code_refs:
  - infra/cube/model/cubes/Commerce.js
  - infra/cube/tests/eu-refund-spike.json
  - infra/cube/tests/na-channel-growth.json
  - libs/adapters/cube/src/zentra_adapter_cube/semantic.py
---

# Cube Semantic Model

The `Commerce` cube joins the synthetic warehouse into one governed analytical
surface. It exposes:

- gross revenue;
- net revenue;
- order count;
- average order value;
- refund amount;
- refund rate;
- active customers;
- repeat-purchase rate.

Dimensions include time, region, channel, category, country, and refund reason.
The model, not the Investigation, owns metric definitions and grain.

The catalog an agent receives carries the **values** each low-cardinality string
dimension holds, not only its name. They are discovered from the warehouse on
first load and cached, rather than declared, because a hand-written list drifts
from the data and a permitted value that is not there is worse than no list. A
member name alone told an agent that `Commerce.region` exists but not that it is
spelled `NA`, and a filter on a value that does not exist returns zero rows
rather than an error.

The scenarios query June–July 2026 EU monthly measures with July refund reasons,
and October–November 2026 NA revenue by channel, then check exact seed values. Raw Cube rows are not persisted to Postgres,
ClickHouse, or the browser response.

Parent: [[Data MOC]]
