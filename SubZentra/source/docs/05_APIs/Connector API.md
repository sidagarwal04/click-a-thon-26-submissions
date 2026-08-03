---
id: api-connector
title: Connector API
type: api
status: active
owner: unassigned
source: repository
created: 2026-08-01
updated: 2026-08-01
reviewed: 2026-08-01
confidence: verified
implementation: current
priority: critical
tags: [api, connector, relations, upload]
related: ["[[APIs MOC]]", "[[Connector Domain]]", "[[Source Catalog]]"]
depends_on: ["[[Authenticated Tenant Resolution]]"]
repo_path: apps/api/src/zentra_api/connector_routes.py
code_refs:
  - apps/api/src/zentra_api/connector_routes.py
  - apps/api/src/zentra_api/connector_schemas.py
  - apps/api/tests/test_connector_contract.py
  - apps/api/tests/test_connector_schemas.py
  - docs/05_APIs/connector-openapi.json
---

# Connector API

Machine-readable contract: `docs/05_APIs/connector-openapi.json`. It is
committed, and `apps/api/tests/test_connector_contract.py` asserts full equality
between it and the specification the application generates — so a frontend built
against the file cannot be building against a lie.

Regenerate after any route change:

```
uv run python tools/scripts/export_connector_openapi.py
```

## Data Sources

| Method | Path | Purpose | Authorization |
| --- | --- | --- | --- |
| POST | `/v1/connector/sources` | Register a source, verified before it is saved | owner/admin |
| GET | `/v1/connector/sources` | List this Tenant's sources | all roles |
| GET | `/v1/connector/sources/{id}` | Read one source | all roles |
| PUT | `/v1/connector/sources/{id}/credentials` | Rotate the secret | owner/admin |
| POST | `/v1/connector/sources/{id}/test-connection` | Re-verify reachability | all roles |
| DELETE | `/v1/connector/sources/{id}` | Remove, dropping an uploaded table | owner/admin |

**Credentials are write-only.** They are accepted on create and rotate and
returned by nothing. Reads carry a `connection_hint` of host and database only —
never username, never anything derived from the password. A contract test asserts
no response schema in the document has a credential field.

Registration tests the connection **before** persisting. An unreachable source is
never saved, so a typo surfaces immediately rather than at the next harvest.
Failures are typed as `unreachable`, `authentication_failed`, or
`database_not_found`, which tells an admin which field to fix without echoing the
source's own error text back.

[[Forensic Observatory]] consumes these six endpoints from
`pages/connections`. Because registration verifies first, its create form has one
button rather than a "Test" beside a "Save"; `test-connection` appears there only
as a re-check on an already-registered source, which is the only thing it can be.

### What is wired, and what is not

The contract test asserts this document matches the generated specification. It
does not call a handler, so a route being *documented* here has never implied it
*runs* — a distinction worth stating, because for a while none of them did.

Data Source persistence landed in migration `0014_data_sources`:
`PostgresDataSourceRepository` backs register, list, read, re-test and delete,
with RLS making a source belong to exactly one Tenant. Credentials are sealed
with AES-GCM under `CONNECTOR_CREDENTIAL_KEY`; with that variable unset the
Connector Service is not constructed and every route answers `503` naming it,
rather than accepting a password it cannot seal.

**Harvest, catalog and relation persistence do not exist.** Those repositories
are `Unwired*` stand-ins that raise on first call, so `/harvests`,
`/catalog-versions` and `/relations` fail loudly instead of returning an empty
catalog — which would read as "this source has no tables" rather than "nobody
built this".

## Harvests

| Method | Path | Purpose | Authorization |
| --- | --- | --- | --- |
| POST | `/v1/connector/sources/{id}/harvests` | Start discovery — returns `202` | owner/admin/member |
| GET | `/v1/connector/harvests/{id}` | Poll phase, counts, budget | all roles |
| POST | `/v1/connector/harvests/{id}/cancel` | Request a stop | owner/admin/member |
| GET | `/v1/connector/sources/{id}/harvests` | Run history | all roles |

`202` and a run to poll, because relation inference issues a query per candidate
pair and will not complete inside a request. Progress is counts — tables found,
fields described, fields profiled, relations proposed — plus budget consumption.

A second concurrent run on one source is refused with `409`: two runs interleaving
would produce a Catalog Version that never existed at any moment in the source.

## Catalog

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/v1/connector/sources/{id}/catalog` | Latest Catalog Version |
| GET | `/v1/connector/catalog-versions/{id}` | One version, with tables, fields, profiles |
| GET | `/v1/connector/catalog-versions/{id}/search?q=` | Find a field across tables |
| GET | `/v1/connector/catalog-versions/{id}/diff?against=` | What changed between versions |

Row counts are named `estimated_rows` because that is what ClickHouse stores.
Every Field Profile carries `sampled_rows`, so no statistic is presented without
the size of the evidence behind it.

## Agent access

| Method | Path | Purpose | Authorization |
| --- | --- | --- | --- |
| PATCH | `/v1/connector/sources/{id}/tables/{table}/agent-access` | Hide or reveal a whole table from agents | owner/admin |
| PATCH | `/v1/connector/sources/{id}/tables/{table}/fields/{field}/agent-access` | Hide or reveal one field | owner/admin |

Every table and field defaults to `agent_visible: true`; these endpoints only
ever record a departure from that default, keyed by table/field name so it
survives a re-harvest. A repeat toggle on the same target upserts rather than
accumulating rows. `GET /sources/{id}/catalog` and
`GET /catalog-versions/{id}` fold the current overrides into each
`TableResponse`/`FieldResponse` as `agent_visible`. See [[Connector Domain]]
for the visibility semantics (table hide beats a stale field override).

## Relations

| Method | Path | Purpose | Authorization |
| --- | --- | --- | --- |
| GET | `/v1/connector/catalog-versions/{id}/relations` | List, filterable by state | all roles |
| POST | `/v1/connector/relations/{id}/decision` | Confirm or reject | owner/admin |
| POST | `/v1/connector/relations/{id}/revoke` | Withdraw a confirmation | owner/admin |
| POST | `/v1/connector/catalog-versions/{id}/relations` | Declare one manually | owner/admin |
| GET | `/v1/connector/catalog-versions/{id}/join-graph` | Confirmed Relations only | all roles |

Every proposal carries its evidence — which signals fired, the measured overlap
fraction, the sample size, both cardinalities — plus `binding_ceiling` naming
which bound held its confidence down. A proposal a reviewer could not argue with
would be an instruction rather than a judgement.

Decisions are idempotent when repeated identically and `409` when contradictory,
so a double-clicked button cannot corrupt state. A rejection must state a reason
(`422` without one): the reason is what suppresses re-proposal, so defaulting it
would silently pick one on the reviewer's behalf.

A manually declared Relation is still validated against real data. The reviewer's
typo can produce a wrong Finding as easily as the system's guess.

The join-graph response also lists `isolated_fields` — the fields nothing
connects to, which is the difference between "your data connects" and "half of it
is unreachable and nobody said so".

## Uploads

| Method | Path | Purpose | Authorization |
| --- | --- | --- | --- |
| POST | `/v1/connector/uploads` | Stream a file, get a preview | owner/admin/member |
| POST | `/v1/connector/uploads/{id}/commit` | Land it as a Data Source | owner/admin/member |

Multipart, streamed in chunks so a large file need not fit in memory before being
rejected for size. The preview returns inferred columns and first rows; commit
accepts corrected column types. A malformed file fails `422` with the offending
row or column named. The limit is 100 MB and stated, so failure is predictable.

Commit creates an ordinary Data Source of kind `uploaded`, which is then
harvested, profiled and relation-inferred by exactly the same path as a connected
warehouse.

## Error behavior

`403` permission denied, `404` not found (never distinguishing "wrong tenant"
from "does not exist"), `409` lifecycle conflict, `422` malformed input or
upload, `502` source unreachable with the typed failure and nothing more. No
error body carries connection details or raw field values.

Parent: [[APIs MOC]]
