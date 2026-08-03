"""Data contracts shared by the three agents.

These are the Track A / Track B interface from PLAN.md. Change them in Phase 0
if you must; after Phase 2 they are frozen.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


@dataclass
class EventGroup:
    """One user action declared in the spec, with the rows correlated to it.

    Each group becomes one table - the same shape as the eight existing Atlys
    source tables, which are one-table-per-event joined on `user_id` /
    `application_id`. The action name *is* the table name.

    A declared action with no matching rows still produces a group, an empty
    one: a table the spec promises and the data never delivers is a finding
    worth surfacing, not something to drop silently.
    """

    action: str
    # The ~15% sample of this group, for profiling and schema design.
    events: list[dict[str, Any]] = field(default_factory=list)
    # Every row of this group, for the real INSERT.
    load_events: list[dict[str, Any]] = field(default_factory=list)
    # Rows in this group before sampling.
    total: int = 0

    @property
    def sampled(self) -> bool:
        return self.total > len(self.events)


@dataclass
class SpecInput:
    """A feature spec as handed to us: prose plus raw event samples."""

    name: str
    brief: str
    events: list[dict[str, Any]] = field(default_factory=list)
    # Records seen in the source file before sampling. None means `events` is
    # already the full set - a hand-pasted example list, not a sampled file.
    events_total: int | None = None
    sample_fraction: float | None = None
    # The full file, when `events` is a sample of it. Profiling and schema
    # design use the sample - that is what keeps LLM cost flat. Loading real
    # data into the table is a ClickHouse INSERT, not an LLM call, so it has
    # no reason to skip 85% of the real events; the load step uses this if
    # present, and falls back to `events` when there is nothing to sample from
    # (a hand-pasted list, where `events` already is everything there is).
    load_events: list[dict[str, Any]] | None = None
    # One per user action declared in spec.md. When present this drives the
    # design - one table per group - and `events` is only the flat union kept
    # for callers that predate the split.
    groups: list[EventGroup] = field(default_factory=list)
    # Event values found in the data that the spec never declared.
    undeclared_actions: dict[str, int] = field(default_factory=dict)
    # How the user actions were found: "heading" (the spec's "User actions"
    # section), "mentioned" (named in the spec but no heading to parse), or
    # "none" (no spec text - one table for the whole feature). Surfaced so a
    # single-table result is never silently mistaken for a split one.
    action_source: str = "none"

    @property
    def event_count(self) -> int:
        return len(self.events)

    @property
    def sampled(self) -> bool:
        return self.events_total is not None and self.events_total > len(self.events)

    @property
    def empty_groups(self) -> list[str]:
        """Declared actions the data never delivered."""
        return [g.action for g in self.groups if not g.load_events]


@dataclass
class FieldProfile:
    """Deterministic statistics for one field across the event samples.

    This is the evidence the LLM reasons from - it never sees raw events, which
    keeps the token cost flat regardless of sample size and makes the same
    input produce the same profile every run.
    """

    name: str
    present: int
    total: int
    nulls: int
    distinct: int
    python_types: list[str]
    samples: list[Any]
    numeric_min: float | None = None
    numeric_max: float | None = None
    max_length: int | None = None
    looks_like: str = "unknown"

    @property
    def null_rate(self) -> float:
        """Fraction of events where the field is absent *or* explicitly null.

        `present` already excludes explicit nulls, so `total - present` covers
        both cases - adding `nulls` again would double-count them.
        """
        return 0.0 if self.total == 0 else (self.total - self.present) / self.total

    @property
    def cardinality_ratio(self) -> float:
        return 0.0 if self.present == 0 else self.distinct / self.present

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "present": self.present,
            "total": self.total,
            "null_rate": round(self.null_rate, 4),
            "distinct": self.distinct,
            "cardinality_ratio": round(self.cardinality_ratio, 4),
            "python_types": self.python_types,
            "samples": self.samples,
            "numeric_min": self.numeric_min,
            "numeric_max": self.numeric_max,
            "max_length": self.max_length,
            "looks_like": self.looks_like,
        }


@dataclass
class ColumnSpec:
    name: str
    type: str
    codec: str | None = None
    source_field: str | None = None
    comment: str | None = None
    # Per `schema-types-avoid-nullable`: a DEFAULT replaces a Nullable wrapper
    # wherever absence does not carry its own meaning.
    default: str | None = None
    # For derived columns, e.g. MATERIALIZED toDate(timestamp). A derived column
    # without this is constant, which is fatal if it sits in the ordering key.
    materialized: str | None = None

    def sql(self) -> str:
        """Render one column definition.

        Clause order is fixed by ClickHouse's grammar:
        ``name type [DEFAULT expr] [COMMENT 'x'] [CODEC(...)] [TTL expr]``.
        Emitting CODEC before COMMENT is a syntax error - the parser has already
        left the state where a comment is legal and reports it against the
        COMMENT token, which points at the wrong culprit.
        """
        parts = [f"`{self.name}`", self.type]
        if self.materialized:
            parts.append(f"MATERIALIZED {self.materialized}")
        elif self.default:
            parts.append(f"DEFAULT {self.default}")
        if self.comment:
            parts.append(f"COMMENT {quote_literal(self.comment)}")
        if self.codec:
            parts.append(f"CODEC({self.codec})")
        return " ".join(parts)


@dataclass
class TableSpec:
    name: str
    columns: list[ColumnSpec]
    order_by: list[str]
    partition_by: str | None = None
    ttl: str | None = None
    comment: str | None = None
    # MergeTree family engine, without the Replicated prefix - the dialect adds
    # that for the local cluster target. An MV target needs
    # AggregatingMergeTree or SummingMergeTree, not the plain default.
    engine: str | None = None


@dataclass
class MaterializedViewSpec:
    """An MV must justify itself - `why` lands in the trace and in review."""

    name: str
    target_table: str
    select: str
    why: str


@dataclass
class SchemaProposal:
    tables: list[TableSpec] = field(default_factory=list)
    materialized_views: list[MaterializedViewSpec] = field(default_factory=list)
    event_mapping: dict[str, str] = field(default_factory=dict)
    notes: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "tables": [
                {
                    "name": t.name,
                    "columns": [
                        {"name": c.name, "type": c.type, "codec": c.codec} for c in t.columns
                    ],
                    "order_by": t.order_by,
                    "partition_by": t.partition_by,
                    "ttl": t.ttl,
                    "engine": t.engine,
                }
                for t in self.tables
            ],
            "materialized_views": [
                {"name": m.name, "target": m.target_table, "why": m.why}
                for m in self.materialized_views
            ],
            "event_mapping": self.event_mapping,
        }


# --- context layer ------------------------------------------------------------

# `rollup` preserves the business rationale for an Instrumentation Agent MV.
ENTRY_KINDS = (
    "definition",
    "metric",
    "entity",
    "relationship",
    "known_issue",
    "table",
    "column",
    "rollup",
)


@dataclass
class ContextEntry:
    """One fact in the context layer."""

    kind: str
    key: str
    value: str
    source: str = "unknown"
    detail: str = ""

    @property
    def identity(self) -> tuple[str, str]:
        return (self.kind, self.key)


@dataclass
class ContextIssue:
    """A contradiction or gap the Context Agent found.

    The base context is imperfect on purpose, so these are a deliverable in
    their own right - not error handling.
    """

    kind: str  # "contradiction" | "gap"
    severity: str  # "high" | "medium" | "low"
    subject: str
    detail: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "severity": self.severity,
            "subject": self.subject,
            "detail": self.detail,
        }


@dataclass
class ContextSnapshot:
    """An immutable version of the context layer.

    This is the Track A / Track B contract from PLAN.md. `version` is what the
    Analytics Agent echoes into its trace so a judge can tell which context a
    conclusion rests on.
    """

    version: int
    created_at: str
    source: str
    entries: list[ContextEntry] = field(default_factory=list)
    issues: list[ContextIssue] = field(default_factory=list)

    def of_kind(self, kind: str) -> list[ContextEntry]:
        return [e for e in self.entries if e.kind == kind]

    @property
    def tables(self) -> list[ContextEntry]:
        return self.of_kind("table")

    @property
    def metrics(self) -> list[ContextEntry]:
        return self.of_kind("metric")

    @property
    def entities(self) -> list[ContextEntry]:
        return self.of_kind("entity")

    @property
    def known_issues(self) -> list[ContextEntry]:
        return self.of_kind("known_issue")

    def index(self) -> dict[tuple[str, str], ContextEntry]:
        return {e.identity: e for e in self.entries}

    def as_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "created_at": self.created_at,
            "source": self.source,
            "counts": {k: len(self.of_kind(k)) for k in ENTRY_KINDS if self.of_kind(k)},
            "issues": [i.as_dict() for i in self.issues],
        }


@dataclass
class ContextDiff:
    """What changed between two versions - the C9 changelog, computed not stored."""

    from_version: int
    to_version: int
    added: list[ContextEntry] = field(default_factory=list)
    removed: list[ContextEntry] = field(default_factory=list)
    changed: list[tuple[ContextEntry, ContextEntry]] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not (self.added or self.removed or self.changed)

    def as_dict(self) -> dict[str, Any]:
        return {
            "from_version": self.from_version,
            "to_version": self.to_version,
            "added": [{"kind": e.kind, "key": e.key} for e in self.added],
            "removed": [{"kind": e.kind, "key": e.key} for e in self.removed],
            "changed": [
                {"kind": new.kind, "key": new.key, "before": old.value, "after": new.value}
                for old, new in self.changed
            ],
        }


# --- analytics ----------------------------------------------------------------


@dataclass
class AnalysisQuestion:
    """One thing to ask the data, and the SQL that answers it."""

    question: str
    sql: str
    cut: str = "overall"  # device | geo | funnel | segment | trend | anomaly
    why: str = ""


@dataclass
class QueryResult:
    """An executed question. `rows` are aggregates - never raw event rows."""

    question: AnalysisQuestion
    columns: list[str] = field(default_factory=list)
    rows: list[list[Any]] = field(default_factory=list)
    error: str = ""
    elapsed_ms: int = 0

    @property
    def ok(self) -> bool:
        return not self.error

    def as_dict(self) -> dict[str, Any]:
        return {
            "question": self.question.question,
            "sql": self.question.sql,
            "cut": self.question.cut,
            "columns": self.columns,
            "rows": self.rows,
            "row_count": len(self.rows),
            "error": self.error,
        }


@dataclass
class Insight:
    """A finding written for a product audience.

    `why` is the causal hypothesis - a number with no `why` is a chart, not an
    insight, and scores nothing. `evidence` cites the figures behind it.
    """

    headline: str
    detail: str
    why: str
    confidence: float
    cut: str = "overall"
    evidence: dict[str, Any] = field(default_factory=dict)
    context_refs: list[str] = field(default_factory=list)
    recommendation: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "headline": self.headline,
            "detail": self.detail,
            "why": self.why,
            "confidence": self.confidence,
            "cut": self.cut,
            "evidence": self.evidence,
            "context_refs": self.context_refs,
            "recommendation": self.recommendation,
        }


@dataclass
class InsightReport:
    context_version: int
    insights: list[Insight] = field(default_factory=list)
    summary: str = ""
    queries_run: int = 0
    # Every query actually sent to ClickHouse for this report - the UI matches
    # these to insight cards by `cut` so a PM can see the exact SQL behind a
    # claim, not just take the LLM's word for it.
    queries: list[QueryResult] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "context_version": self.context_version,
            "queries_run": self.queries_run,
            "summary": self.summary,
            "insights": [i.as_dict() for i in self.insights],
            "queries": [q.as_dict() for q in self.queries],
        }


def parse_questions(payload: dict[str, Any]) -> list[AnalysisQuestion]:
    return [
        AnalysisQuestion(
            question=q.get("question", ""),
            sql=q.get("sql", ""),
            cut=q.get("cut", "overall"),
            why=q.get("why", ""),
        )
        for q in payload.get("questions", [])
        if q.get("sql")
    ]


def parse_insights(payload: dict[str, Any]) -> list[Insight]:
    out: list[Insight] = []
    for i in payload.get("insights", []):
        if not i.get("headline") or not i.get("why"):
            continue  # a finding without a why is not an insight
        out.append(
            Insight(
                headline=i["headline"],
                detail=i.get("detail", ""),
                why=i["why"],
                confidence=float(i.get("confidence", 0.5)),
                cut=i.get("cut", "overall"),
                evidence=i.get("evidence", {}),
                context_refs=i.get("context_refs", []),
                recommendation=i.get("recommendation", ""),
            )
        )
    return out


def quote_literal(value: str) -> str:
    """Single-quote a SQL string literal. Shared with dialect.py's table COMMENT."""
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"


def parse_proposal(payload: dict[str, Any]) -> SchemaProposal:
    """Build a SchemaProposal from the LLM's JSON, tolerating missing optionals."""
    tables = []
    for raw in payload.get("tables", []):
        columns = [
            ColumnSpec(
                name=c["name"],
                type=c["type"],
                codec=c.get("codec"),
                source_field=c.get("source_field"),
                comment=c.get("comment"),
                default=c.get("default"),
                materialized=c.get("materialized"),
            )
            for c in raw.get("columns", [])
        ]
        tables.append(
            TableSpec(
                name=raw["name"],
                columns=columns,
                order_by=raw.get("order_by", []),
                partition_by=raw.get("partition_by"),
                ttl=raw.get("ttl"),
                comment=raw.get("comment"),
                engine=raw.get("engine"),
            )
        )

    views = [
        MaterializedViewSpec(
            name=m["name"],
            target_table=m.get("target_table", ""),
            select=m.get("select", ""),
            why=m.get("why", ""),
        )
        for m in payload.get("materialized_views", [])
    ]

    return SchemaProposal(
        tables=tables,
        materialized_views=views,
        event_mapping=payload.get("event_mapping", {}),
        notes=payload.get("notes", ""),
    )


def parse_events_text(text: str) -> list[dict[str, Any]]:
    """Parse NDJSON or a JSON array. Unparseable lines are skipped, not fatal."""
    text = text.strip()
    if not text:
        return []
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return [e for e in parsed if isinstance(e, dict)]
        if isinstance(parsed, dict):
            return [parsed]
    except json.JSONDecodeError:
        pass

    events: list[dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip().rstrip(",")
        if not line:
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            events.append(item)
    return events


def load_spec(
    path: str | None = None,
    *,
    brief: str | None = None,
    events_path: str | None = None,
    name: str | None = None,
    sample_fraction: float | None = 0.15,
) -> SpecInput:
    """Build a SpecInput from whatever the caller has.

    Three shapes, because a spec arrives differently depending on where you are:
    a handed-out directory (spec.md + events.ndjson), a lone markdown file, or
    text and events supplied directly.

    `sample_fraction` applies only to a *file* read here (events.ndjson or
    `events_path`) - the agent samples the file, not the other way around. Pass
    `None` (or 1.0) to read the file in full.
    """
    import pathlib

    resolved_name = name
    text = brief or ""
    raw_events = ""

    if path:
        p = pathlib.Path(path)
        if p.is_dir():
            resolved_name = resolved_name or p.name
            spec_md = p / "spec.md"
            if spec_md.exists():
                text = text or spec_md.read_text()
            for candidate in ("events.ndjson", "events.json", "events.jsonl"):
                f = p / candidate
                if f.exists():
                    raw_events = f.read_text()
                    break
        elif p.exists():
            resolved_name = resolved_name or p.stem
            text = text or p.read_text()

    if events_path:
        raw_events = pathlib.Path(events_path).read_text()

    return build_spec(
        name=resolved_name or "spec",
        brief=text,
        raw_events=raw_events,
        sample_fraction=sample_fraction,
    )


def build_spec(
    *,
    name: str,
    brief: str,
    raw_events: str,
    sample_fraction: float | None = 0.15,
) -> SpecInput:
    """Spec text + raw events -> one EventGroup per declared user action.

    The single place the split happens, so the CLI and the browser cannot
    drift apart on which tables a spec produces.
    """
    from .sampling import sample_events
    from .spec_split import (
        detect_action_field,
        flatten_event,
        infer_actions_from_data,
        parse_user_actions,
        split_by_action,
    )

    # Flatten first: a nested object is one column per leaf, and every later
    # step - split, profile, INSERT - has to agree on that shape or the load
    # fails on a field the table never got.
    parsed = [flatten_event(e) for e in parse_events_text(raw_events)]
    fraction = sample_fraction if sample_fraction is not None else 1.0
    take_all = fraction >= 1.0

    actions = parse_user_actions(brief)
    source = "heading" if actions else "none"
    if not actions and parsed:
        # No heading to parse. Let the data propose candidates and the spec
        # confirm them, so a brief pasted without its heading still splits.
        actions = infer_actions_from_data(
            brief, parsed, field=detect_action_field(parsed, [])
        )
        source = "mentioned" if actions else "none"

    groups: list[EventGroup] = []
    undeclared: dict[str, int] = {}

    if actions and parsed:
        field_name = detect_action_field(parsed, actions)
        split, undeclared = split_by_action(parsed, actions, field=field_name)
        for action, rows in split.items():
            groups.append(
                EventGroup(
                    action=action,
                    events=rows if take_all else sample_events(rows, fraction=fraction),
                    load_events=rows,
                    total=len(rows),
                )
            )
    elif actions:
        # Spec declares actions but no events file was supplied - still carry
        # the tables so a brief-only run designs the right shape.
        groups = [EventGroup(action=a) for a in actions]

    return SpecInput(
        name=name,
        brief=brief,
        events=parsed if take_all else sample_events(parsed, fraction=fraction),
        events_total=None if take_all else (len(parsed) or None),
        sample_fraction=sample_fraction,
        # None, not [], when there is nothing to load: the flat `events` list
        # is already everything there is.
        load_events=None if (take_all or not parsed) else parsed,
        groups=groups,
        undeclared_actions=undeclared,
        action_source=source,
    )
