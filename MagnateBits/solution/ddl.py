"""Deterministic DDL rendering, linting and dry-running.

No LLM lives here. The Instrumentation Agent produces a `DDLProposal` (an intent);
this module is the only thing that turns intent into SQL text, and the only thing
that decides whether that intent is acceptable.

Why the split matters for judging: the model never emits raw SQL that we execute
verbatim. It emits a *structured* proposal, we render it with a fixed template, we
lint it against `house_rules.md` mechanically, and we prove it against a scratch
database before it touches `atlys`. A hallucinated engine or a missing PARTITION BY
is caught by `lint()` with a rule id, not by a reviewer's memory.

Public surface:
    render(proposal)        -> list[str]           statements in execution order
    lint(proposal)          -> list[str]           rule violations, "" when clean
    dry_run(proposal, ch)   -> (ok, clickhouse_error)
"""

from __future__ import annotations

import re
from typing import Any, Iterable

from contracts import ColumnSpec, DDLProposal, MVSpec

DRYRUN_DB = "atlys_dryrun"

# Names that are structurally identity keys in ANY feature: exact `id`, or a
# `*_id` suffix. Derived from the naming convention, not from any known spec.
_IDENT_RE = re.compile(r"(^id$)|(_id$)")
_BARE_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_IDENTIFIER_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")

# SQL keywords/functions that may legally appear inside an ORDER BY expression and
# must not be mistaken for column references by L6.
_SQL_WORDS = {
    "and", "or", "not", "asc", "desc", "toyyyymm", "todate", "todatetime",
    "tostartofday", "tostartofhour", "tostartofmonth", "tounixtimestamp",
    "cityhash64", "siphash64", "intdiv", "if", "multiif", "tuple",
    "lower", "upper", "coalesce", "ifnull", "assumenotnull", "tostring",
    "interval", "day", "month", "year", "hour", "minute", "second",
}


# --------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------


def is_identity_name(name: str) -> bool:
    """True for columns that behave as an entity/row identifier in any feature."""
    return bool(_IDENT_RE.search(name or ""))


def _q(name: str) -> str:
    return f"`{name}`"


def _lit(text: str) -> str:
    return "'" + str(text).replace("\\", "\\\\").replace("'", "''") + "'"


def _clean(sql: str) -> str:
    return (sql or "").strip().rstrip(";").strip()


def _strip_leading(clause: str, keyword: str) -> str:
    c = _clean(clause)
    if c.lower().startswith(keyword.lower()):
        c = c[len(keyword):].strip()
    return c


def column_comment(col: ColumnSpec) -> str:
    """Every column carries its provenance in the catalog, not in a README.

    `SELECT name, comment FROM system.columns` then answers "where did this come
    from" for a human or for the Context Agent, with no extra bookkeeping.
    """
    src = col.json_path.strip() if col.json_path else ""
    head = f"json_path={src}" if src else "json_path=(derived)"
    extra = (col.comment or "").strip()
    if extra and not extra.startswith("json_path="):
        return f"{head}; {extra}"
    return extra or head


def _identifiers(expr: str) -> list[str]:
    out = []
    for tok in _IDENTIFIER_TOKEN_RE.findall(expr or ""):
        if tok.lower() in _SQL_WORDS:
            continue
        out.append(tok)
    return out


def group_by_keys(select_sql: str) -> list[str]:
    """Extract the GROUP BY list of an MV SELECT.

    The rollup target's ORDER BY is derived from this, so the keys must be bare
    identifiers (ClickHouse allows GROUP BY on SELECT aliases). L11 enforces that.
    """
    sql = _clean(select_sql)
    m = None
    for m in re.finditer(r"\bGROUP\s+BY\b", sql, re.IGNORECASE):
        pass
    if m is None:
        return []
    tail = sql[m.end():]
    stop = re.search(
        r"\b(HAVING|ORDER\s+BY|LIMIT|SETTINGS|UNION|WINDOW|FORMAT)\b", tail, re.IGNORECASE
    )
    if stop:
        tail = tail[: stop.start()]
    return [p.strip() for p in tail.split(",") if p.strip()]


def _mv_engine(select_sql: str) -> str:
    """AggregatingMergeTree when the SELECT emits aggregate states, else Summing.

    Summing a `uniq()` across partitions is arithmetically wrong; the -State/-Merge
    pair is the only correct way to roll up distinct counts, so the presence of a
    `*State(` call decides the engine.
    """
    return "AggregatingMergeTree" if re.search(r"\w+State(If)?\s*\(", select_sql or "") \
        else "SummingMergeTree"


def _mv_partition_key(keys: Iterable[str]) -> str | None:
    for k in keys:
        if re.search(r"(^|_)(day|date|dt|bucket|week|month)$", k, re.IGNORECASE):
            return f"toYYYYMM({k})"
    return None


# --------------------------------------------------------------------------
# render
# --------------------------------------------------------------------------


def render_table(proposal: DDLProposal) -> str:
    lines: list[str] = []
    for col in proposal.columns:
        piece = f"    {_q(col.name)} {col.type.strip()}"
        if col.default:
            piece += f" DEFAULT {_strip_leading(col.default, 'DEFAULT')}"
        # ClickHouse column grammar is strict about this order:
        #   name type [DEFAULT expr] [COMMENT 'x'] [CODEC(...)] [TTL expr]
        piece += f" COMMENT {_lit(column_comment(col))}"
        if col.codec:
            codec = _strip_leading(col.codec, "CODEC").strip()
            if not codec.startswith("("):
                codec = f"({codec})"
            piece += f" CODEC{codec}"
        lines.append(piece)

    stmt = [
        f"CREATE TABLE IF NOT EXISTS {proposal.table_name}",
        "(",
        ",\n".join(lines),
        ")",
        f"ENGINE = {proposal.engine.strip() or 'MergeTree'}",
    ]
    if proposal.partition_by:
        stmt.append(f"PARTITION BY {_strip_leading(proposal.partition_by, 'PARTITION BY')}")
    stmt.append("ORDER BY (" + ", ".join(proposal.order_by) + ")")
    if proposal.ttl:
        stmt.append(f"TTL {_strip_leading(proposal.ttl, 'TTL')}")
    if proposal.settings:
        rendered = ", ".join(f"{k} = {v}" for k, v in proposal.settings.items())
        stmt.append(f"SETTINGS {rendered}")
    return "\n".join(stmt)


def render_mv_target(mv: MVSpec) -> str:
    """Create the rollup target with the exact column types the SELECT produces.

    `EMPTY AS <select>` lets ClickHouse infer `AggregateFunction(uniq, String)` and
    friends for us. Hand-writing those types is the single most common way a
    generated MV silently breaks on merge.
    """
    keys = group_by_keys(mv.select_sql)
    engine = _mv_engine(mv.select_sql)
    parts = [f"CREATE TABLE IF NOT EXISTS {mv.target_table}", f"ENGINE = {engine}"]
    pk = _mv_partition_key(keys)
    if pk:
        parts.append(f"PARTITION BY {pk}")
    parts.append("ORDER BY (" + ", ".join(keys) + ")")
    parts.append("EMPTY AS")
    parts.append(_clean(mv.select_sql))
    return "\n".join(parts)


def render_mv(mv: MVSpec) -> str:
    return (
        f"CREATE MATERIALIZED VIEW IF NOT EXISTS {mv.name}\n"
        f"TO {mv.target_table} AS\n{_clean(mv.select_sql)}"
    )


def render(proposal: DDLProposal) -> list[str]:
    """Raw table -> agg targets -> materialized views. Creation order is load-bearing."""
    stmts = [render_table(proposal)]
    for mv in proposal.materialized_views:
        stmts.append(render_mv_target(mv))
    for mv in proposal.materialized_views:
        stmts.append(render_mv(mv))
    return stmts


def drop_statements(proposal: DDLProposal) -> list[str]:
    """Teardown in reverse dependency order, for `rebuild=True`."""
    stmts = [f"DROP VIEW IF EXISTS {mv.name}" for mv in proposal.materialized_views]
    stmts += [f"DROP TABLE IF EXISTS {mv.target_table}" for mv in proposal.materialized_views]
    stmts.append(f"DROP TABLE IF EXISTS {proposal.table_name}")
    return stmts


# --------------------------------------------------------------------------
# lint
# --------------------------------------------------------------------------

_REQUIRED_RATIONALE = ("order_by", "partition_by", "types", "nullable", "ttl")
_REQUIRED_SETTING = "ratio_of_defaults_for_sparse_serialization"


def lint(proposal: DDLProposal) -> list[str]:
    """Deterministic house-rule checks. Empty list == acceptable.

    Each violation is prefixed with its rule id so the repair prompt can be fed back
    verbatim and the model knows exactly which line to change.
    """
    v: list[str] = []
    cols = {c.name: c for c in proposal.columns}
    order_by = [o.strip() for o in proposal.order_by if o and o.strip()]
    sem = proposal.semantics

    # L1 -- never lead the sorting key with an identifier column.
    if not order_by:
        v.append("L1: ORDER BY is empty; expected (event, timestamp, <entity_key>)")
    elif is_identity_name(order_by[0].split("(")[0].strip("` ")) or is_identity_name(order_by[0]):
        v.append(
            f"L1: ORDER BY starts with identity column '{order_by[0]}'. The primary index "
            "would be useless because queries filter by event/time/segment, never by id. "
            "Lead with the event discriminator, then timestamp, then the entity key."
        )

    # L2 -- Nullable is banned on sorting-key columns and segment dimensions.
    hot = {i for o in order_by for i in _identifiers(o)} | set(sem.segment_dims or [])
    for name in sorted(hot):
        c = cols.get(name)
        if c and "Nullable(" in c.type:
            v.append(
                f"L2: column '{name}' is {c.type} but is used in ORDER BY or as a segment "
                "dimension. Use DEFAULT '' / DEFAULT 0 instead of Nullable on hot columns."
            )

    # L3 -- LowCardinality on an identity key destroys the dictionary.
    for c in proposal.columns:
        if is_identity_name(c.name) and "LowCardinality" in c.type:
            v.append(
                f"L3: identity column '{c.name}' is {c.type}. LowCardinality on a "
                "high-cardinality id builds a dictionary as large as the data. Use String."
            )

    # L4 / L5 -- partitioning and retention.
    if not (proposal.partition_by or "").strip():
        v.append("L4: PARTITION BY is missing; expected toYYYYMM(timestamp).")
    if not (proposal.ttl or "").strip():
        v.append(
            "L5: TTL is missing on the raw table. Raw events expire; the rollup MV is what "
            "survives, and that pairing is how the MV earns its keep."
        )

    # L6 -- ORDER BY must reference real columns.
    for expr in order_by:
        for ident in _identifiers(expr):
            if ident not in cols:
                v.append(f"L6: ORDER BY references '{ident}', which is not a declared column.")

    # L7 -- MVs must be explicit and re-runnable.
    for mv in proposal.materialized_views:
        if not (mv.target_table or "").strip():
            v.append(f"L7: materialized view '{mv.name}' has no explicit target table.")
        if re.search(r"\bPOPULATE\b", mv.select_sql or "", re.IGNORECASE):
            v.append(
                f"L7: materialized view '{mv.name}' uses POPULATE, which races with "
                "concurrent inserts and silently loses rows. Backfill with INSERT SELECT."
            )

    # L8 -- every choice carries a rationale.
    for key in _REQUIRED_RATIONALE:
        if not (proposal.rationale.get(key) or "").strip():
            v.append(f"L8: rationale['{key}'] is missing or empty.")
    if proposal.materialized_views and not (proposal.rationale.get("mvs") or "").strip():
        v.append("L8: rationale['mvs'] is required when materialized views are proposed.")

    # L9 -- namespacing, so an unseen spec cannot shadow an existing production table.
    slug = (sem.feature_slug or "").strip()
    expected = f"f_{slug}_events" if slug else None
    if expected and proposal.table_name != expected:
        v.append(
            f"L9: table_name must be '{expected}' (f_<feature_slug>_events); got "
            f"'{proposal.table_name}'."
        )
    elif not expected and not re.match(r"^f_[a-z0-9_]+_events$", proposal.table_name or ""):
        v.append(f"L9: table_name '{proposal.table_name}' is not f_<feature_slug>_events.")

    # L10 -- sparse serialization must be switched on explicitly.
    setting_keys = {k.lower() for k in proposal.settings}
    if _REQUIRED_SETTING not in setting_keys:
        v.append(
            f"L10: SETTINGS must include {_REQUIRED_SETTING}. With E event types an "
            "event-scoped column is ~(1 - 1/E) defaults, just under the 0.9375 default "
            "threshold, so it would NOT go sparse. Set min(0.9, 1 - 1/(E+1))."
        )

    # ---- structural checks beyond the numbered rules -----------------------
    if not proposal.columns:
        v.append("L11: no columns declared.")
    seen: set[str] = set()
    for c in proposal.columns:
        if not _BARE_IDENT_RE.match(c.name or ""):
            v.append(f"L11: column name '{c.name}' is not a plain identifier.")
        if c.name in seen:
            v.append(f"L11: duplicate column '{c.name}'.")
        seen.add(c.name)
        if not (c.type or "").strip():
            v.append(f"L11: column '{c.name}' has no type.")

    for mv in proposal.materialized_views:
        keys = group_by_keys(mv.select_sql)
        if not keys:
            v.append(
                f"L12: materialized view '{mv.name}' has no GROUP BY. A view that does not "
                "aggregate is a copy of the raw table and cannot earn its keep."
            )
        for k in keys:
            if not _BARE_IDENT_RE.match(k):
                v.append(
                    f"L12: materialized view '{mv.name}' groups by expression '{k}'. Alias it "
                    "in the SELECT list and GROUP BY the alias, so the target table's ORDER BY "
                    "can be derived deterministically."
                )
        if not re.search(rf"\bFROM\s+(\w+\.)?{re.escape(proposal.table_name)}\b",
                         mv.select_sql or "", re.IGNORECASE):
            v.append(
                f"L13: materialized view '{mv.name}' does not select FROM "
                f"{proposal.table_name}; an MV only fires on inserts into its source table."
            )
        if not (mv.name or "").startswith("mv_"):
            v.append(f"L14: materialized view name '{mv.name}' must be prefixed mv_.")
        if mv.target_table and not mv.target_table.startswith("agg_"):
            v.append(f"L14: MV target '{mv.target_table}' must be prefixed agg_.")

    # The seam Analytics reads must point at the table we actually create.
    if sem.table_fqn and not sem.table_fqn.endswith(proposal.table_name):
        v.append(
            f"L15: semantics.table_fqn '{sem.table_fqn}' does not refer to "
            f"'{proposal.table_name}'."
        )
    if sem.entity_key and sem.entity_key not in cols:
        v.append(f"L15: semantics.entity_key '{sem.entity_key}' is not a declared column.")
    for dim in sem.segment_dims or []:
        if dim not in cols:
            v.append(f"L15: semantics.segment_dims references undeclared column '{dim}'.")

    # de-duplicate, preserve order
    out: list[str] = []
    for item in v:
        if item not in out:
            out.append(item)
    return out


# --------------------------------------------------------------------------
# dry run
# --------------------------------------------------------------------------


def _qualify(sql: str, names: Iterable[str], db: str) -> str:
    """Point every object reference in a statement at the scratch database."""
    out = sql
    for name in sorted(set(names), key=len, reverse=True):
        if not name:
            continue
        out = re.sub(rf"\b(?:[A-Za-z_][A-Za-z0-9_]*\.)?{re.escape(name)}\b", f"{db}.{name}", out)
    return out


def object_names(proposal: DDLProposal) -> list[str]:
    names = [proposal.table_name]
    for mv in proposal.materialized_views:
        names += [mv.target_table, mv.name]
    return [n for n in names if n]


def dry_run(proposal: DDLProposal, ch: Any, db: str = DRYRUN_DB) -> tuple[bool, str]:
    """Execute the rendered DDL in a scratch database, then drop it.

    This is the difference between "the model wrote plausible SQL" and "ClickHouse
    accepted this exact SQL". The verbatim server error is the repair signal.
    """
    names = object_names(proposal)
    stmts = [_qualify(s, names, db) for s in render(proposal)]
    error = ""
    try:
        ch.execute_ddl(f"CREATE DATABASE IF NOT EXISTS {db}")
        for stmt in stmts:
            try:
                ch.execute_ddl(stmt)
            except Exception as exc:  # noqa: BLE001 - the message IS the product
                error = f"{type(exc).__name__}: {exc}\n--- while executing ---\n{stmt}"
                break
    except Exception as exc:  # noqa: BLE001
        error = f"{type(exc).__name__}: {exc}"
    finally:
        try:
            ch.execute_ddl(f"DROP DATABASE IF EXISTS {db}")
        except Exception:  # noqa: BLE001 - scratch cleanup must never mask the real error
            pass
    return (error == ""), error
