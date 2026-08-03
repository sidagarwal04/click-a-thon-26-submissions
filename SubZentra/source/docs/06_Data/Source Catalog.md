---
id: data-source-catalog
title: Source Catalog
type: data-model
status: active
owner: unassigned
source: repository
created: 2026-08-01
updated: 2026-08-01
reviewed: 2026-08-01
confidence: verified
implementation: current
priority: high
tags: [data, connector, clickhouse, catalog]
related:
  - "[[Data MOC]]"
  - "[[Connector Domain]]"
  - "[[ClickHouse Audit Ledger]]"
  - "[[adr/0002-split-transactional-and-audit-storage]]"
repo_path: libs/adapters/clickhouse
code_refs:
  - libs/adapters/clickhouse/src/zentra_adapter_clickhouse/source_connector.py
  - libs/adapters/clickhouse/src/zentra_adapter_clickhouse/landing_zone.py
  - libs/adapters/clickhouse/src/zentra_adapter_clickhouse/cipher.py
---

# Source Catalog

## ClickHouse now plays three distinct roles

Naming them apart matters, because two of them hold raw customer data and one is
guaranteed never to.

| Role | Database | Contains | Owner |
| --- | --- | --- | --- |
| **Audit Ledger** | `zentra_audit` | Process metadata and `artifact://` refs, never raw values | ZentraOS |
| **Connected warehouse** | the customer's own | The customer's rows, read in place, never copied | Tenant |
| **Upload landing zone** | `zentra_uploads` | Raw customer data, by design | ZentraOS |

The landing zone is deliberately a **different database** from the audit ledger.
The ledger's guarantee under
[[adr/0006-metadata-only-audit-ledger]] is that it holds no raw customer values;
placing uploads beside it would make that guarantee a matter of which table you
happened to read rather than a property of where things live.

## What is read, and what is retained

**Declared schema** comes free from `system.tables` and `system.columns` — names,
types, engines, estimated rows and sizes. ClickHouse exposes no foreign keys, so
nothing about relationships is available here.

**Observed profiles** cost one query per field: null fraction, distinct count,
minimum, maximum, over a bounded `LIMIT` sample rather than a full scan. This is
someone's production warehouse; a full scan to learn a null fraction is not a
reasonable thing to do to them.

**Raw sample values are opt-in per Data Source and off by default.** Statistics
are aggregates and carry limited disclosure risk; retained values would place
customer data in ZentraOS storage, which is a materially different posture for a
system whose ledger is built to hold none. The default costs no functionality,
because relation inference runs on aggregate counts.

## Overlap measurement

Within one ClickHouse instance, overlap is a single aggregate query and **no row
leaves the source**.

Across two instances there is no such query. The smaller side's distinct key
values are read and probed against the other — a real disclosure, bounded by the
sample limit and confined to key columns. It is the price of discovering that an
uploaded file joins to a warehouse, and it is implemented as a separate method
rather than hidden behind a shared helper so the difference stays visible.

## Uploads

CSV is parsed by ClickHouse's own `CSVWithNames`, with types inferred
conservatively from the first 200 rows — a wrong `String` costs one correction in
the preview, a wrongly-guessed `Int64` costs a failed load. Parquet is read via
Arrow, and the same Arrow table is used for preview and for load, so what a user
approves is what lands.

Every inferred column is `Nullable`: a file is not a schema contract, and one
blank cell in row 40,000 must not fail a load the user already approved.

Landed tables use `ENGINE = MergeTree ORDER BY tuple()`. Inventing a sort key
from the first column would impose an ordering the data does not have.

## Credentials

Sealed with AES-GCM under a key from `CONNECTOR_CREDENTIAL_KEY`, stored as bytes.
Authenticated, so a tampered ciphertext fails to open rather than decrypting to
something the connector would then try to connect with. Associated data binds the
ciphertext to its purpose, so a row moved elsewhere fails rather than silently
working.

`from_env` raises when the variable is missing rather than generating a key. A
generated key works perfectly until the process restarts, at which point every
stored credential becomes permanently unopenable — a failure that surfaces long
after the mistake causing it.

## Measured inference accuracy

`infra/clickhouse/init/002_tpch.sql` seeds a deterministic TPC-H subset into a
`tpch` database — eight tables, nine documented foreign keys, generated with
`numbers()` and never `rand()` so a fresh `docker compose up` reproduces it byte
for byte. `tools/evals/connector_accuracy.py` scores inference against those
nine and fails the run on regression (`nx run evals:connector-accuracy`).

Baseline, measured 2026-08-02 against local ClickHouse:

| | |
| --- | --- |
| Documented foreign keys recovered | **9 of 9** |
| Recall | 1.00 |
| Spurious proposals | 4 |
| Precision | 0.69 |
| Fields skipped as ineligible | 12 |

Two things this measurement settles that assertion could not.

The three dimension references — both `nationkey` joins and the `regionkey`
join — **are** recovered, against 25 and 5 distinct values. The cardinality
ceiling caps how much confidence such a relation may claim; it does not suppress
the proposal. A reviewer still sees the join, and still sees that the system is
not sure of it.

Three of the four spurious proposals are **transitive co-references**:
`lineitem.l_partkey` and `partsupp.ps_partkey` genuinely share values because
both reference `part.p_partkey`. They are not foreign keys to each other, and
deciding that is exactly what human confirmation is for. The fourth pairs two
account-balance columns occupying the same numeric range — the honest kind of
false positive, and the reason overlap alone is never sufficient.

## Verification status

The pure logic around the driver — identifier quoting, failure classification,
type inference, sealing — is covered by unit tests. **The SQL itself is not.**
Real dialect behaviour and `system.*` semantics require a live ClickHouse and are
unverified by the automated suite; a manual pass is required before the demo.

Persistence of Catalog Versions, Relations, and Harvest Runs to Postgres under
RLS is **not yet implemented**.

Parent: [[Data MOC]]
