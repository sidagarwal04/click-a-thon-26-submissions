# Sequence

Sequence owns the versioned graph of typed transform steps that turns a Tenant's raw table into a final, model-ready table, and the two Agents — Data Steward and Semantic Modeler — that build and hand off that graph.

## Language

**Sequence**:
A Dataset Workspace-owned, reusable graph of Sequence Steps that starts from one Raw Table and produces one or more Final Tables. Many Investigation Threads may reference the same Sequence's Final Tables.
_Avoid_: Pipeline, workflow, ETL job

**Raw Table**:
The unmodified input to a Sequence — either a Connector Source Table or a Data Source Dataset Table Version. A Sequence never mutates its Raw Table.
_Avoid_: Source, input file

**Sequence Step**:
One node in a Sequence's graph: a single typed operation from the transform catalog (e.g. drop_nulls, cast_type, dedupe, filter_rows, rename_column) applied to its parent step's output, producing a new immutable Prepared Table.
_Avoid_: Transform, node, task

**Prepared Table**:
The immutable, versioned tabular output of one Sequence Step. Every Sequence Step produces exactly one Prepared Table; nothing overwrites a Prepared Table once produced.
_Avoid_: Cleaned data, intermediate table

**Final Table**:
A Prepared Table explicitly marked as a Sequence's terminal output — the only Prepared Table the Semantic Modeler Agent may model. A Sequence may have more than one Final Table.
_Avoid_: Output table, result

**Sequence Run**:
One execution of a single Sequence Step against chDB, recorded as an Agent Execution with its Outcome Signal, input Prepared Table (or Raw Table), and resulting Prepared Table.
_Avoid_: Job run, execution log

**Data Steward Agent**:
A registered Agent that builds a Sequence incrementally: proposes and executes one Sequence Step at a time from a typed operation catalog, in response to conversation in the Sequence's Investigation Thread, never accepting agent-authored SQL or code as a transform.
_Avoid_: ETL agent, cleaning bot, prep agent

**Semantic Modeler Agent**:
A registered Agent that proposes measures, dimensions, and joins over a Sequence's Final Table as a Metric Draft, gated by Human Approval before entering the approved Semantic Model.
_Avoid_: Modeling agent, schema agent

## Relationship to other contexts

A Sequence's Raw Table comes from [Connector](../connector/CONTEXT.md) (a Source Table) or [Data Source](../data-source/CONTEXT.md) (a Dataset Table Version) — Sequence does not define a third way to land data.

The Data Steward Agent and Semantic Modeler Agent are [Agent Execution](../agent-execution/CONTEXT.md) Agents; each Sequence Step the Data Steward runs is one Agent Execution, but the Sequence graph itself outlives any single execution.

A Final Table is the only thing the Semantic Modeler Agent may turn into a [Semantic Metric](../CONTEXT.md); it never models a Raw Table or an intermediate Prepared Table directly. The resulting Metric Draft follows the same Human Approval path as any other Semantic Model change — Sequence adds no second approval mechanism.

The chat that builds a Sequence is an ordinary [Investigation Thread](../investigation/CONTEXT.md) scoped to that Sequence rather than to a governed question; a Sequence started automatically mid-Investigation is the same object as one started from the Sequence page, not a separate draft kind.
