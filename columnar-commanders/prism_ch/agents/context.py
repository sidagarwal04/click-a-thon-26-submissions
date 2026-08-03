"""Context Agent: maintains the living context layer, orchestrated by LangGraph.

The agent is a state-machine with four nodes:

1. **bootstrap** — parse the base context document into structured entries, or
   load entries from the previous version
2. **introspect** — read the live ClickHouse schema and reconcile it against
   what the context claims
3. **detect** — surface contradictions and gaps (structural + LLM semantic)
4. **publish** — write an immutable new version, with a diff against the last

The graph routes conditionally: when a base context document is supplied,
bootstrap parses it fresh; otherwise it carries forward entries from the
previous version. Detection runs both a deterministic structural pass and an
optional LLM semantic pass when credentials are available.

On detection: the brief says the base context is imperfect *on purpose*, so
finding its flaws is a deliverable rather than error handling.
"""

from __future__ import annotations

import logging
import pathlib
import re
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, StateGraph

from ..config import Settings
from ..tracing import agent_step, current_dimensions, pipeline_run
from . import llm
from .context_store import ContextStore, context_dialect, diff_snapshots
from .types import (
    ContextDiff,
    ContextEntry,
    ContextIssue,
    ContextSnapshot,
    InsightReport,
    MaterializedViewSpec,
    TableSpec,
)

log = logging.getLogger(__name__)

PROMPT = (pathlib.Path(__file__).parent / "prompts" / "context.md").read_text()

# The bundled starting point. Whichever agent touches the context layer first
# against a brand new database - Instrumentation, Analytics, or a direct
# ContextAgent.run() with nothing supplied - seeds from this, once, so none of
# them can proceed against an empty context layer. Single source of truth:
# every entry point that can seed a fresh database points here.
DEFAULT_BASE_CONTEXT = pathlib.Path(__file__).resolve().parent.parent / "base_context.md"

# These identifiers are part of this project's event contract. Other repeated
# ``*_id`` fields may be flags, source-system artefacts, or unrelated IDs and
# must not be promoted to joins solely because their names match.
BUSINESS_JOIN_KEYS = frozenset({"user_id", "application_id", "app_session_id", "group_id"})
APP_INTERNAL_TABLES = frozenset({"ui_schema_changes", "ui_agent_insights"})

# Section heading keywords -> entry kind.
SECTION_KINDS: tuple[tuple[str, str], ...] = (
    ("known issue", "known_issue"),
    ("known-issue", "known_issue"),
    ("quirk", "known_issue"),
    ("metric", "metric"),
    ("entity", "entity"),
    ("relationship", "relationship"),
    ("join", "relationship"),
    ("table", "table"),
    ("definition", "definition"),
)

# Numbered items count: the known-issues log is "1. **K1 — ...**", not a dash.
BULLET = re.compile(r"^\s*(?:[-*]|\d+\.)\s+(.*)$")
# "**name** — description", "`name`: description", "**metric** = formula".
LABELLED = re.compile(r"^\s*(?:\*\*|`)?([A-Za-z0-9_ ./()-]{2,60}?)(?:\*\*|`)?\s*[—:=–-]\s+(.+)$")
TABLE_RULE = re.compile(r"^\s*\|[\s:|-]+\|\s*$")
TABLE_ROW = re.compile(r"^\s*\|(.+)\|\s*$")


def classify_section(heading: str) -> str:
    lowered = heading.lower()
    for needle, kind in SECTION_KINDS:
        if needle in lowered:
            return kind
    return "definition"


def parse_markdown(text: str, *, source: str = "base_context.md") -> list[ContextEntry]:
    """Split a context document into structured entries.

    Deliberately forgiving: an unrecognised line is kept verbatim rather than
    dropped, because silently losing a fact from the context layer is far worse
    than carrying an untidy one.
    """
    entries: list[ContextEntry] = []
    heading = "overview"
    kind = "definition"
    buffer: list[str] = []
    open_entry: ContextEntry | None = None
    in_table = False

    def flush() -> None:
        body = "\n".join(buffer).strip()
        if body:
            entries.append(
                ContextEntry(kind=kind, key=f"section:{heading}", value=body, source=source)
            )
        buffer.clear()

    def keep(key: str, value: str) -> ContextEntry:
        entry = ContextEntry(
            kind=kind,
            key=key.strip().strip("`*"),
            value=value.strip(),
            source=source,
            detail=heading,
        )
        entries.append(entry)
        return entry

    for line in text.splitlines():
        if line.startswith("#"):
            flush()
            heading = line.lstrip("#").strip() or "overview"
            kind = classify_section(heading)
            open_entry, in_table = None, False
            continue

        if TABLE_RULE.match(line):
            in_table = True
            open_entry = None
            continue
        row = TABLE_ROW.match(line)
        if row:
            cells = [c.strip() for c in row.group(1).split("|")]
            if in_table and cells and cells[0]:
                open_entry = keep(cells[0], " — ".join(c for c in cells[1:] if c))
            continue
        in_table = False

        stripped = line.strip()
        bullet = BULLET.match(line)
        content = bullet.group(1).strip() if bullet else stripped
        if content:
            labelled = LABELLED.match(content)
            if labelled:
                open_entry = keep(labelled.group(1), labelled.group(2))
                continue
            if open_entry is not None and not bullet:
                open_entry.value += " " + content
                continue
            if bullet:
                open_entry = None
        elif not stripped:
            open_entry = None

        buffer.append(line)

    flush()
    return entries


# ---------------------------------------------------------------------------
# LangGraph state
# ---------------------------------------------------------------------------


def _merge_entries(existing: list[ContextEntry], new: list[ContextEntry]) -> list[ContextEntry]:
    """Reducer: replace with the new value (last-write-wins)."""
    return new if new else existing


def _merge_issues(existing: list[ContextIssue], new: list[ContextIssue]) -> list[ContextIssue]:
    return new if new else existing


class ContextState(TypedDict, total=False):
    settings: Settings
    client: Any
    store: ContextStore
    base_context: str | None
    entries: Annotated[list[ContextEntry], _merge_entries]
    issues: Annotated[list[ContextIssue], _merge_issues]
    version: int
    diff: ContextDiff | None
    source: str


# ---------------------------------------------------------------------------
# Graph nodes
# ---------------------------------------------------------------------------


def bootstrap_node(state: ContextState) -> dict[str, Any]:
    """Parse base context document or carry forward previous entries.

    A refresh with no document supplied (`base_context` falsy - the CLI's
    `context` command with no `--base-context`, or the UI's "Initialize
    context" with an empty textarea) normally just carries forward whatever
    the previous version had. But if there is no previous version either
    (`latest_version() == 0` - a genuinely fresh database), "carry forward
    nothing" would publish a context with zero business content. Falling back
    to the bundled `base_context.md` here means every entry point that can
    reach this node - not just the Instrumentation Agent's own pre-seed step -
    self-heals a database with no context at all.
    """
    base_context = state.get("base_context")
    store: ContextStore = state["store"]

    if not base_context and store.latest_version() == 0 and DEFAULT_BASE_CONTEXT.exists():
        base_context = str(DEFAULT_BASE_CONTEXT)

    if base_context:
        with agent_step("context", "bootstrap", input={"path": base_context}) as step:
            text = pathlib.Path(base_context).read_text()
            entries = parse_markdown(text, source=pathlib.Path(base_context).name)
            counts: dict[str, int] = {}
            for entry in entries:
                counts[entry.kind] = counts.get(entry.kind, 0) + 1

            step.decision(
                what=f"parsed {len(entries)} entries from {pathlib.Path(base_context).name}",
                why=(
                    "unrecognised lines are kept verbatim rather than dropped - losing a "
                    "fact from the context layer is worse than carrying an untidy one"
                ),
                evidence={"by_kind": counts, "chars": len(text)},
            )
            step.output({"entries": len(entries)})
            return {"entries": entries, "source": "bootstrap"}

    previous = store.load()
    entries = [e for e in previous.entries if e.source != "clickhouse"]
    return {"entries": entries, "source": "refresh"}


def introspect_node(state: ContextState) -> dict[str, Any]:
    """Read the real table landscape from ClickHouse."""
    client = state["client"]
    settings: Settings = state["settings"]
    store: ContextStore = state["store"]

    with agent_step("context", "introspect_database") as step:
        internal = ", ".join(
            f"'{t}'" for t in sorted(set(store.internal_tables) | APP_INTERNAL_TABLES)
        )
        sql = (
            "SELECT table, name, type FROM system.columns "
            f"WHERE database = '{settings.database}' "
            f"AND table NOT IN ({internal}) "
            "ORDER BY table, position"
        )
        step.sql(sql, purpose="discover tables and columns")
        result = client.query(sql)
        rows = getattr(result, "result_rows", None) or []

        by_table: dict[str, list[tuple[str, str]]] = {}
        for table, column, ctype in rows:
            by_table.setdefault(str(table), []).append((str(column), str(ctype)))

        db_entries: list[ContextEntry] = []
        for table, columns in by_table.items():
            db_entries.append(
                ContextEntry(
                    kind="table",
                    key=table,
                    value=f"{len(columns)} columns",
                    source="clickhouse",
                    detail=", ".join(name for name, _ in columns),
                )
            )
            for name, ctype in columns:
                db_entries.append(
                    ContextEntry(
                        kind="column",
                        key=f"{table}.{name}",
                        value=ctype,
                        source="clickhouse",
                    )
                )

        tables_by_join_key: dict[str, list[str]] = {}
        for table, columns in by_table.items():
            for name, _ in columns:
                if name.lower() in BUSINESS_JOIN_KEYS:
                    tables_by_join_key.setdefault(name.lower(), []).append(table)
        for key, tables in sorted(tables_by_join_key.items()):
            unique_tables = sorted(set(tables))
            if len(unique_tables) < 2:
                continue
            qualified = [f"{table}.{key}" for table in unique_tables]
            db_entries.append(
                ContextEntry(
                    kind="relationship",
                    key=f"shared {key}",
                    value=" = ".join(qualified),
                    source="clickhouse",
                    detail="inferred from the event contract and verified against live columns",
                )
            )

        step.decision(
            what=f"discovered {len(by_table)} tables, {len(rows)} columns",
            why="context is derived from the live database, so a new table cannot go unnoticed",
            evidence={"tables": sorted(by_table)},
        )
        step.output({"tables": len(by_table)})

        combined = list(state.get("entries", [])) + db_entries
        return {"entries": combined}


def detect_node(state: ContextState) -> dict[str, Any]:
    """Surface contradictions and gaps — structural + semantic."""
    entries = state.get("entries", [])
    settings: Settings = state["settings"]
    snapshot = ContextSnapshot(0, "", "pending", entries)

    with agent_step("context", "detect_issues", context_version="pending") as step:
        issues = _structural_issues(snapshot)
        structural = len(issues)

        if settings.llm_enabled:
            issues.extend(_semantic_issues(settings, snapshot))

        step.decision(
            what=f"found {len(issues)} issue(s): {structural} structural, "
            f"{len(issues) - structural} semantic",
            why=(
                "the base context is imperfect by design, so surfacing its "
                "contradictions and gaps is a deliverable, not error handling"
            ),
            evidence={"subjects": [i.subject for i in issues][:10]},
        )
        step.output({"issues": len(issues)})
        return {"issues": issues}


def publish_node(state: ContextState) -> dict[str, Any]:
    """Write an immutable new version with a diff against the last."""
    store: ContextStore = state["store"]
    entries = state.get("entries", [])
    issues = state.get("issues", [])
    settings: Settings = state["settings"]
    source = state.get("source", "refresh")
    summary = f"{source} of {settings.database}"

    previous = store.load()

    with agent_step("context", "publish_version") as step:
        version = store.write(entries=entries, issues=issues, source=source, summary=summary)
        current = ContextSnapshot(version, "", source, entries, issues)
        delta = diff_snapshots(previous, current)

        _embed_version(settings, store, version, entries)

        step.decision(
            what=f"published context v{version}",
            why=(
                "versions are append-only and immutable, so the changelog is a query "
                "between two versions rather than a log we have to maintain"
            ),
            evidence=delta.as_dict(),
            confidence=1.0,
        )
        step.output({"version": version, "diff": delta.as_dict()})
        return {"version": version, "diff": delta}


def _embed_version(
    settings: Settings,
    store: ContextStore,
    version: int,
    entries: list[ContextEntry],
) -> None:
    """Compute and store embeddings for non-column entries. Best-effort."""
    embeddable = [e for e in entries if e.kind != "column" and not e.key.startswith("section:")]
    if not embeddable:
        return
    try:
        texts = [f"{e.kind}: {e.key} — {e.value}" for e in embeddable]
        batch_size = 96
        all_vectors: list[list[float]] = []
        for i in range(0, len(texts), batch_size):
            all_vectors.extend(llm.embed(settings, texts[i : i + batch_size]))
        rows = [
            (e.kind, e.key, texts[i], vec)
            for i, (e, vec) in enumerate(zip(embeddable, all_vectors, strict=False))
        ]
        store.write_embeddings(version, rows)
    except Exception:
        log.warning("embedding generation skipped — no embedding provider available", exc_info=True)


# ---------------------------------------------------------------------------
# Detection helpers (pure functions, used by nodes and direct calls)
# ---------------------------------------------------------------------------


def _structural_issues(snapshot: ContextSnapshot) -> list[ContextIssue]:
    """Checks that need no LLM: duplicates, orphans, undocumented tables."""
    issues: list[ContextIssue] = []

    by_term: dict[str, ContextEntry] = {}
    for entry in snapshot.entries:
        if entry.kind in ("table", "column") or entry.key.startswith("section:"):
            continue
        term = " ".join(entry.key.lower().split())
        prior = by_term.get(term)
        if prior is None:
            by_term[term] = entry
        elif prior.value.strip() != entry.value.strip():
            issues.append(
                ContextIssue(
                    kind="contradiction",
                    severity="high",
                    subject=f"{prior.kind}:{prior.key}",
                    detail=(
                        f"defined twice with different values - "
                        f"as {prior.kind} ({prior.detail or prior.source}): "
                        f"{prior.value[:120]!r}; "
                        f"as {entry.kind} ({entry.detail or entry.source}): "
                        f"{entry.value[:120]!r}"
                    ),
                )
            )

    documented = {
        e.key.lower()
        for e in snapshot.tables
        if e.source != "clickhouse" and not e.key.startswith("section:")
    }
    live = {e.key.lower() for e in snapshot.tables if e.source == "clickhouse"}
    known_columns = {e.key.lower() for e in snapshot.of_kind("column")}

    for table in sorted(live - documented):
        if documented:
            issues.append(
                ContextIssue(
                    kind="gap",
                    severity="medium",
                    subject=f"table:{table}",
                    detail="exists in ClickHouse but is not described in the context document",
                )
            )

    for table in sorted(documented - live):
        issues.append(
            ContextIssue(
                kind="contradiction",
                severity="high",
                subject=f"table:{table}",
                detail="described in the context document but absent from ClickHouse",
            )
        )

    for metric in snapshot.metrics:
        formula = metric.value.lower()
        if not re.search(r"(?:/|÷|\bper\b|\brate\b|\bcount\s*\(|\bsum\s*\(|\bavg\s*\()", formula):
            issues.append(
                ContextIssue(
                    kind="gap",
                    severity="high",
                    subject=f"metric:{metric.key}",
                    detail="metric is named but has no executable formula or denominator",
                )
            )
        for reference in re.findall(
            r"\b([a-z_][a-z0-9_]*\.[a-z_][a-z0-9_]*)\b", metric.value.lower()
        ):
            if known_columns and reference not in known_columns:
                issues.append(
                    ContextIssue(
                        kind="gap",
                        severity="medium",
                        subject=f"metric:{metric.key}",
                        detail=f"references {reference!r}, which is not a known column",
                    )
                )

    relationships = snapshot.of_kind("relationship")
    for relationship in relationships:
        text = f"{relationship.key} {relationship.value}".lower()
        references = set(re.findall(r"\b([a-z_][a-z0-9_]*\.[a-z_][a-z0-9_]*)\b", text))
        if not references:
            issues.append(
                ContextIssue(
                    kind="gap",
                    severity="high",
                    subject=f"relationship:{relationship.key}",
                    detail="relationship does not state a qualified join key (table.column)",
                )
            )
            continue
        missing = sorted(ref for ref in references if known_columns and ref not in known_columns)
        if missing:
            issues.append(
                ContextIssue(
                    kind="contradiction",
                    severity="high",
                    subject=f"relationship:{relationship.key}",
                    detail=f"join references columns absent from ClickHouse: {', '.join(missing)}",
                )
            )

    # Shared identifiers make a join possible, but without an explicit relationship
    # the Analytics Agent cannot know whether that join is semantically valid.
    documented_relationships = " ".join(
        f"{entry.key} {entry.value}".lower() for entry in relationships
    )
    join_columns: dict[str, set[str]] = {}
    for qualified in known_columns:
        table, column = qualified.split(".", 1)
        if column in BUSINESS_JOIN_KEYS:
            join_columns.setdefault(column, set()).add(table)
    for column, tables in sorted(join_columns.items()):
        if len(tables) > 1 and column not in documented_relationships:
            issues.append(
                ContextIssue(
                    kind="gap",
                    severity="medium",
                    subject=f"relationship:{column}",
                    detail=(
                        f"{column} exists in {', '.join(sorted(tables))}, but no context "
                        "relationship confirms whether those tables may be joined on it"
                    ),
                )
            )

    return issues


def _semantic_issues(settings: Settings, snapshot: ContextSnapshot) -> list[ContextIssue]:
    """LLM pass for contradictions structure cannot see."""
    payload = [
        {
            "kind": e.kind,
            "key": e.key,
            "value": e.value[:600] + (" [...truncated for review]" if len(e.value) > 600 else ""),
        }
        for e in snapshot.entries
        if e.kind in ("definition", "metric", "entity", "relationship", "known_issue")
        and not e.key.startswith("section:")
    ]
    if not payload:
        return []

    import json

    try:
        response = llm.complete(
            settings,
            name="detect_context_issues",
            system=PROMPT,
            prompt=(
                "# Context layer entries\n\n"
                f"```json\n{json.dumps(payload, indent=2)}\n```\n\n"
                "Find contradictions and gaps. Return only the JSON object."
            ),
            as_json=True,
        )
    except llm.LLMError as exc:
        log.warning("semantic issue detection unavailable: %s", exc)
        return []

    return [
        ContextIssue(
            kind=item.get("kind", "contradiction"),
            severity=item.get("severity", "medium"),
            subject=item.get("subject", ""),
            detail=item.get("detail", ""),
        )
        for item in response.get("issues", [])  # type: ignore[union-attr]
        if item.get("detail")
    ]


# ---------------------------------------------------------------------------
# Build the LangGraph
# ---------------------------------------------------------------------------


def _build_graph() -> StateGraph:
    graph = StateGraph(ContextState)

    graph.add_node("bootstrap", bootstrap_node)
    graph.add_node("introspect", introspect_node)
    graph.add_node("detect", detect_node)
    graph.add_node("publish", publish_node)

    graph.set_entry_point("bootstrap")
    graph.add_edge("bootstrap", "introspect")
    graph.add_edge("introspect", "detect")
    graph.add_edge("detect", "publish")
    graph.add_edge("publish", END)

    return graph


_compiled_graph = _build_graph().compile()


# ---------------------------------------------------------------------------
# Agent class — preserves the public API for tests and callers
# ---------------------------------------------------------------------------


class ContextAgent:
    def __init__(self, settings: Settings, client: Any) -> None:
        self.settings = settings
        self.client = client
        self.dialect = context_dialect(settings)
        self.store = ContextStore(client, self.dialect)
        self.graph = _compiled_graph
        self.last_insight_report = InsightReport(context_version=0)
        self.last_analytics_run_id: str | None = None
        self.last_analytics_trace_id: str | None = None

    def bootstrap_if_empty(self, *, run_analytics: bool = False) -> int | None:
        """Seed the context layer from the bundled base_context.md, once.

        Both the Instrumentation Agent and the Analytics Agent can be the
        first thing anyone runs against a brand-new database, and either
        would otherwise read context v0 (empty) - no metrics, no known
        issues, no entity definitions. This is the one place both rely on
        instead of each duplicating the "is this database brand new" check.
        A later call always finds `latest_version() != 0` and returns None
        straight away.
        """
        self.store.ensure_schema()
        if self.store.latest_version() != 0 or not DEFAULT_BASE_CONTEXT.exists():
            return None
        with agent_step(
            "context",
            "bootstrap_default_context",
            input={"path": str(DEFAULT_BASE_CONTEXT)},
        ) as step:
            version, _delta, _report = self.run(
                str(DEFAULT_BASE_CONTEXT), run_analytics=run_analytics
            )
            step.decision(
                what=f"seeded context v{version} from the bundled base_context.md",
                why=(
                    "no context version existed yet for this database - without "
                    "seeding it once, business context (metrics, known issues, "
                    "entities) would be empty for whichever agent ran first"
                ),
                confidence=1.0,
            )
            step.output({"version": version})
            return version

    # --- direct method access (used by tests and InstrumentationAgent) --------

    def bootstrap(self, path: str) -> list[ContextEntry]:
        result = bootstrap_node(
            {
                "base_context": path,
                "store": self.store,
                "settings": self.settings,
                "client": self.client,
            }
        )
        return result["entries"]

    def introspect(self) -> list[ContextEntry]:
        result = introspect_node(
            {
                "entries": [],
                "settings": self.settings,
                "client": self.client,
                "store": self.store,
            }
        )
        return result["entries"]

    def detect(self, snapshot: ContextSnapshot) -> list[ContextIssue]:
        with agent_step("context", "detect_issues", context_version=str(snapshot.version)) as step:
            issues = _structural_issues(snapshot)
            structural = len(issues)

            if self.settings.llm_enabled:
                issues.extend(_semantic_issues(self.settings, snapshot))

            step.decision(
                what=f"found {len(issues)} issue(s): {structural} structural, "
                f"{len(issues) - structural} semantic",
                why=(
                    "the base context is imperfect by design, so surfacing its "
                    "contradictions and gaps is a deliverable, not error handling"
                ),
                evidence={"subjects": [i.subject for i in issues][:10]},
            )
            step.output({"issues": len(issues)})
            return issues

    def record_new_table(self, table: TableSpec) -> None:
        """Called by the Instrumentation Agent after it creates a table (C5)."""
        self.refresh_after_schema_change([table.name])

    def refresh_after_schema_change(
        self,
        tables: list[str],
        views: list[MaterializedViewSpec] | None = None,
    ) -> tuple[int, ContextDiff]:
        """Publish one schema-synchronised version after an instrumentation run.

        Human-authored table descriptions are preserved; only entries whose source is
        ClickHouse are replaced. This also captures columns added to existing tables.
        """
        names = sorted(set(tables))
        with agent_step("context", "refresh_schema", input={"tables": names}) as step:
            previous = self.store.load()
            entries = [e for e in previous.entries if e.source != "clickhouse"]
            entries.extend(self.introspect())
            entries = self._with_rollups(entries, views or [])
            issues = self.detect(ContextSnapshot(0, "", "pending", entries))
            version = self.store.write(
                entries=entries,
                issues=issues,
                source="instrumentation",
                summary=f"schema refresh: {', '.join(names)}",
            )
            current = ContextSnapshot(version, "", "instrumentation", entries, issues)
            delta = diff_snapshots(previous, current)
            _embed_version(self.settings, self.store, version, entries)
            step.decision(
                what=f"context advanced once to v{version}",
                why=(
                    "all schema changes from the instrumentation run are published as one "
                    "snapshot, and Analytics reads the newest completed version"
                ),
                evidence=delta.as_dict(),
                confidence=1.0,
            )
            step.output({"version": version, "diff": delta.as_dict()})

        # ARCHITECTURE.md: ContextAgent -> AnalyticsAgent. A schema change is
        # exactly the moment analysis goes stale, so this is the other half of
        # the same trigger `run()` already applies on a manual refresh - reusing
        # the same helper keeps both paths' failure isolation identical.
        self._run_analytics(version)
        return version, delta

    @staticmethod
    def _with_rollups(
        entries: list[ContextEntry], views: list[MaterializedViewSpec]
    ) -> list[ContextEntry]:
        """Upsert MV rationale without duplicating a prior rollup entry."""
        if not views:
            return entries
        targets = {view.target_table for view in views}
        combined = [
            entry
            for entry in entries
            if not (entry.kind == "rollup" and entry.key in targets)
        ]
        combined.extend(
            ContextEntry(
                kind="rollup",
                key=view.target_table,
                value=view.why,
                source="instrumentation",
                detail=view.select[:800],
            )
            for view in views
        )
        return combined

    def record_rollups(self, views: list[MaterializedViewSpec]) -> None:
        """Compatibility API for recording MV business rationale."""
        if not views:
            return
        with agent_step(
            "context", "record_rollups", input={"tables": [v.target_table for v in views]}
        ) as step:
            previous = self.store.load()
            entries = self._with_rollups(list(previous.entries), views)
            issues = self.detect(ContextSnapshot(0, "", "pending", entries))
            version = self.store.write(
                entries=entries,
                issues=issues,
                source="instrumentation",
                summary=f"{len(views)} rollup(s) registered",
            )
            _embed_version(self.settings, self.store, version, entries)
            step.output({"version": version, "tables": [v.target_table for v in views]})

    def publish(
        self, entries: list[ContextEntry], *, source: str, summary: str = ""
    ) -> tuple[int, ContextDiff]:
        previous = self.store.load()
        issues = self.detect(ContextSnapshot(0, "", "pending", entries))

        with agent_step("context", "publish_version") as step:
            version = self.store.write(
                entries=entries, issues=issues, source=source, summary=summary
            )
            current = ContextSnapshot(version, "", source, entries, issues)
            delta = diff_snapshots(previous, current)

            step.decision(
                what=f"published context v{version}",
                why=(
                    "versions are append-only and immutable, so the changelog is a query "
                    "between two versions rather than a log we have to maintain"
                ),
                evidence=delta.as_dict(),
                confidence=1.0,
            )
            step.output({"version": version, "diff": delta.as_dict()})
            return version, delta

    # --- kept for test compatibility ------------------------------------------

    def _structural_issues(self, snapshot: ContextSnapshot) -> list[ContextIssue]:
        return _structural_issues(snapshot)

    def _semantic_issues(self, snapshot: ContextSnapshot) -> list[ContextIssue]:
        return _semantic_issues(self.settings, snapshot)

    # --- LangGraph orchestration ----------------------------------------------

    def run(
        self, base_context: str | None = None, *, run_analytics: bool = True
    ) -> tuple[int, ContextDiff, InsightReport]:
        """Publish context, then automatically analyze the completed version."""
        self.store.ensure_schema()

        initial_state: ContextState = {
            "settings": self.settings,
            "client": self.client,
            "store": self.store,
            "base_context": base_context,
            "entries": [],
            "issues": [],
            "version": 0,
            "diff": None,
            "source": "refresh",
        }

        result = self.graph.invoke(initial_state)
        version, delta = result["version"], result["diff"]
        self.last_insight_report = InsightReport(context_version=version)
        self.last_analytics_run_id = None
        self.last_analytics_trace_id = None
        if run_analytics:
            self._run_analytics(version)
        return version, delta, self.last_insight_report

    def _run_analytics(self, context_version: int) -> None:
        """Run Analytics in its own trace without risking the context publish."""
        from .analytics import AnalyticsAgent

        surface = current_dimensions().get("surface") or current_dimensions().get("via") or "agent"
        try:
            with pipeline_run("analyze", spec_name="analytics", surface=surface) as run:
                report = AnalyticsAgent(self.settings, self.client).run()
                confidences = [insight.confidence for insight in report.insights]
                run.metric("analysis.insights", len(report.insights))
                run.metric("analysis.queries", report.queries_run)
                run.metric("analysis.context_version", report.context_version)
                if confidences:
                    run.metric(
                        "analysis.confidence_avg",
                        round(sum(confidences) / len(confidences), 3),
                    )
                run.output(report.as_dict())
                self.last_insight_report = report
                self.last_analytics_run_id = run.run_id
                self.last_analytics_trace_id = run.trace_id
        except Exception:
            log.warning(
                "post-refresh analytics failed; context v%d remains published",
                context_version,
                exc_info=True,
            )
