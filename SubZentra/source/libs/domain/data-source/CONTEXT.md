# Data Source

Data Source owns the Tenant-authorized analytical inputs an Investigation may bind without coupling Agents to files, credentials, or providers.

## Language

**Data Source**:
A Tenant-owned analytical input represented by either a Workspace Snapshot or a Data Connection.
_Avoid_: Dataset, database, connector

**Data Source Binding**:
The immutable selection of one Data Source, Semantic Model version, Query Governance Policy version, authorization provenance, and safe fingerprints for an Investigation.
_Avoid_: Data context, connection selection, source config

**Query Governance Policy**:
An immutable Tenant-approved version of source scopes, read-only restrictions, execution budgets, and result limits.
_Avoid_: Query config, timeout settings, safety rules

## Uploaded data

**Dataset Workspace**:
A Tenant-owned collection of related uploaded Dataset Tables that may be modeled and queried together.
_Avoid_: Dataset, folder, database

**Dataset Table**:
A named tabular concept inside a Dataset Workspace whose contents are supplied through immutable versions.
_Avoid_: Relation, file, sheet, table — "Relation" is reserved by [Connector](../connector/CONTEXT.md) for an inferred join

**Dataset Table Version**:
One immutable uploaded representation of a Dataset Table with its integrity hash and inferred schema.
_Avoid_: Relation Version, replacement file, current table

**Workspace Snapshot**:
The immutable set of Dataset Table Versions selected from one Dataset Workspace for an Investigation.
_Avoid_: Dataset version, workspace copy

**Column Classification Draft**:
A proposed sensitivity classification for every column that has not entered an approved Semantic Model version.
_Avoid_: PII scan result, automatic classification

**Relationship Draft**:
A proposed join with keys, type, cardinality, confidence, and rationale that has not entered an approved Semantic Model version.
_Avoid_: Join guess, inferred foreign key

**Data Quality Observation**:
Typed evidence that source shape or values may affect an Investigation without rewriting the source.
_Avoid_: Cleaned data, validation error

## Live data

**Connector Type**:
A versioned provider integration implementing the Connector Port for one class of external data system.
_Avoid_: Connector instance, integration account

**Data Connection**:
One Tenant-authorized instance of a Connector Type with governed scope, credential reference, lifecycle, availability, and health.
_Avoid_: Connector, database credential, data source

**Connection Eligibility**:
The derived determination that a Data Connection may start new Investigations under its lifecycle, availability, health, grant, model, validation, and policy state.
_Avoid_: Connected, active flag
