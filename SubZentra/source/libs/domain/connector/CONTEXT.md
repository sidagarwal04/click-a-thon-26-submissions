# Connector

The Connector context owns how ZentraOS learns what is in a Tenant's data and how that data connects.

## Data Sources

**Data Source**:
A tenant-owned origin of queryable data ZentraOS has been granted access to. Either `connected` — a warehouse ZentraOS reads in place — or `uploaded` — a file ZentraOS landed. Two kinds of one concept, not two concepts.
_Avoid_: Connector, integration, connection, database

**Connection Check**:
The outcome of trying to reach a Data Source, stated as reachable or as one of three reasons it was not.
_Avoid_: Ping, health, status

## Catalog

**Catalog Version**:
The immutable record of what one Harvest Run observed in a Data Source. Re-harvesting adds a version; it never edits one.
_Avoid_: Schema, snapshot, metadata dump

**Source Table**:
One harvested table within a Catalog Version.
_Avoid_: Dataset, entity

**Source Field**:
One harvested column within a Source Table. Raw surface area, never a governed business measure.
_Avoid_: Column, attribute, metric

**Row Browse**:
A paginated, unfiltered read of a Source Table's own rows, straight through Cube as raw dimensions — never a governed query, and never persisted or cached beyond the page requested.
_Avoid_: Preview, sample, query

**Field Identity**:
What makes a Source Field the same field across Catalog Versions — its name, its type, and its parent table together.
_Avoid_: Field id, key

**Field Profile**:
Statistics observed for a Source Field over a stated sample. Distinct from declared schema, which is read rather than measured.
_Avoid_: Stats, metadata, sample

**Harvest Run**:
One execution of discovery against a Data Source, bounded by a budget and producing a Catalog Version.
_Avoid_: Sync, scan, job, crawl

## Relations

**Relation**:
A proposed or confirmed join between two Source Fields, carrying the evidence and confidence behind it. Inferred rather than read, because ClickHouse declares no foreign keys.
_Avoid_: Foreign key, link, edge, association

**Binding Ceiling**:
Which bound held a Relation's confidence below its raw signal score — the size of the sample, the coarseness of the fields, or neither.
_Avoid_: Cap, limit, penalty

**Join Graph**:
The confirmed Relations of one Catalog Version. The only joins an analytical agent may use.
_Avoid_: Schema graph, ERD, model

## Relationship to other contexts

A Source Field is not a [Semantic Metric](../CONTEXT.md). Discovery produces raw surface area; a governed business measure with an agreed definition and grain remains a separate, deliberate act.

Confirming a Relation is a governance decision in the same family as a Human Approval: it grants agents permission to act on something that could otherwise be wrong.
