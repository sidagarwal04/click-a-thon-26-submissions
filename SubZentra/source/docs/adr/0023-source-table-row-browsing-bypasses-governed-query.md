---
id: adr-0023
title: Source Table row browsing bypasses governed query
type: adr
status: active
owner: unassigned
source: repository
created: 2026-08-02
updated: 2026-08-02
reviewed: 2026-08-02
confidence: verified
implementation: current
priority: medium
tags: [adr, cube, connector, semantic-model]
related:
  - "[[adr/0016-cube-is-the-single-tenant-scoped-analytical-gateway]]"
  - "[[Connector Domain]]"
repo_path: apps/api
code_refs:
  - apps/api/src/zentra_api/connector_rows_routes.py
  - apps/api/src/zentra_api/connector_rows.py
  - libs/adapters/cube/src/zentra_adapter_cube/semantic.py
---

# Source Table row browsing bypasses governed query

## Status

Accepted.

## Context

ADR-0016 made Cube the single tenant-scoped analytical gateway for both the
demo warehouse and live Connector data, and its "What stayed unchanged"
section names `SemanticCatalog.reject_ungoverned` as the enforcement point
that does not change: every query an agent runs must select from a governed
catalog of measures and dimensions, never an arbitrary raw table scan.

The dataset page needed a "Browse rows" action per Source Table — a
paginated, read-only view of a table's own rows, for a human reading the
page directly, not an agent. Cube's dynamically generated Connector cube
(`infra/cube/model/cubes/Connector.js`) turns every harvested field into a
dimension unconditionally, so a dimension-only query with no measures
already returns raw, ungrouped rows through the same governed gateway — no
new port, no raw SQL against ClickHouse. The obstacle was narrower: Cube's
own governed-catalog check, `reject_ungoverned`, exists to stop a caller
asking for a member outside a hand-curated catalog, and a row browse's whole
point is every confirmed field, which is not what that catalog enumerates
for a Connector cube (it enumerates the safe default `count`/`sum` measures,
per ADR-0016's consequences — not raw dimensions for row display).

## Decision

`browse_table_rows` (`apps/api/src/zentra_api/connector_rows_routes.py`)
builds its own Cube query directly from `CatalogVersion.tables[i].fields[j]`
— the same confirmed field list the catalog endpoints already expose — and
calls a new `CubeSemanticLayer.load_raw(query)` method
(`libs/adapters/cube/src/zentra_adapter_cube/semantic.py`) that forwards the
query to Cube's `/load` without running `reject_ungoverned` first.

This is safe specifically because every dimension in the query is
catalog-sourced, never caller-supplied: the route takes `table_name` and a
`page` number as input, looks up the table in the tenant's own latest
Catalog Version, and derives the dimension list from its fields. There is no
code path from request input to an arbitrary Cube member name, so there is
nothing for `reject_ungoverned` to usefully reject — the same shape of
argument ADR-0016 already made for why an unconfirmed Relation cannot reach
a compiled schema (it derives the schema from a checked source, not from
what a caller asks for).

`load_raw` is a method on `CubeSemanticLayer`, not a public accessor to its
private `_client`, so the one intentional bypass stays visible on the class
whose whole purpose is enforcing governance — its docstring now says "raw
tables are unreachable here, except through `load_raw`, for call sites
documented as bypassing governance on purpose," naming the one caller
rather than quietly widening what the class allows.

This does not touch `SemanticLayerPort`/ADR-003's no-raw-SQL boundary
(`libs/domain/agent-execution/src/zentra_domain_agent_execution/ports.py`):
the row browse still goes through Cube, which still compiles the query and
executes it against the real store. No new capability to reach ClickHouse
directly was added anywhere.

## Consequences

`CubeSemanticLayer` now has two ways to query Cube: `query()` (governed,
used by `SqlAnalystAgent`/`EvaluatorAgent`) and `load_raw()` (ungoverned,
used only by the row-browse route). A future call site reaching for
`load_raw()` to skip governance for convenience, rather than because its
query is provably catalog-sourced like this one, would be the wrong use of
this escape hatch — this ADR is the record of the one case actually
justified, not a precedent that any raw query is fine.

Cube's `total: true` query option is asserted to return a top-level `total`
integer sibling of `data`, per Cube's own documentation, but no fixture in
this repository exercises that response shape against a live Cube instance.
`connector_rows.py`'s parsing falls back to `len(rows)` if that key is
absent or not an integer, which degrades to under-reporting on the last
page rather than crashing, but should be verified against a live Cube
instance before being relied on in production.

A stale or mistyped `data_source_id`/`table_name` and a Cube instance that
is genuinely not ready yet both answer with the same "still syncing"
message to the frontend — a deliberate v1 simplification (see the route's
`_handle_rows`), not a claim that the two failures are the same thing.

## Verification

`libs/adapters/cube/tests/test_semantic.py`
(`test_load_raw_bypasses_governance_and_forwards_the_query_verbatim`);
`apps/api/tests/test_connector_rows.py` (query building and payload parsing,
pure unit tests); `apps/api/tests/test_connector_rows_api.py` (route-level:
success, pagination offset, never-harvested and unknown-table 404s with
Cube never queried, Cube-unreachable 503 with no leaked exception text,
cross-tenant 404, viewer parity with owner).

Parent: [[Decisions MOC]]
