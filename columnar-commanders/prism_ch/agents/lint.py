"""Deterministic checks on a generated schema, run before ClickHouse sees it.

ClickHouse validates *syntax*. It will happily accept a schema that is legal and
wrong - an ordering-key column nothing ever populates, a UUID stored as String,
a table with no retention. Those are exactly the choices judged under "schema
quality", and they are also the ones an LLM drops silently between runs.

So the checks live here, in code: same input, same verdict, every time. A
failure feeds the repair loop just like a server rejection does, which means the
model gets told precisely what to fix rather than being trusted to remember.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .types import FieldProfile, SchemaProposal, TableSpec

# `toDate(timestamp)` and friends - an ordering term that is an expression
# rather than a bare column name.
EXPRESSION = re.compile(r"\w+\s*\(")


@dataclass
class LintIssue:
    table: str
    rule: str
    detail: str
    fix: str

    def __str__(self) -> str:
        return f"[{self.rule}] {self.table}: {self.detail} -> {self.fix}"


def lint_table(
    table: TableSpec,
    profiles: dict[str, FieldProfile],
    *,
    mv_target: bool = False,
) -> list[LintIssue]:
    """`mv_target` relaxes the checks that assume raw-event ingestion.

    An MV target's columns come from the view's SELECT, not from a mapped event
    field, so demanding a `source_field` or MATERIALIZED expression on its
    ordering key would reject every correct aggregating table.
    """
    columns = {c.name: c for c in table.columns}
    issues: list[LintIssue] = []

    # 1. Every bare ordering-key column must actually get a value. A derived
    #    column with no MATERIALIZED/DEFAULT expression and no source field is
    #    constant, and a constant in the key prunes nothing.
    for term in table.order_by:
        if EXPRESSION.search(term):
            continue
        column = columns.get(term)
        if column is None:
            issues.append(
                LintIssue(
                    table.name,
                    "orderby-column-missing",
                    f"ordering key references {term!r}, which is not a column",
                    "add the column or drop it from ORDER BY",
                )
            )
            continue
        derived = column.materialized or column.default
        if not mv_target and not column.source_field and not derived:
            issues.append(
                LintIssue(
                    table.name,
                    "orderby-column-unpopulated",
                    f"{term!r} leads no raw field and has no MATERIALIZED/DEFAULT "
                    "expression, so every row gets the type's zero value",
                    f"set MATERIALIZED (e.g. toDate(<timestamp column>)) on {term!r}, "
                    "map it to a raw field, or remove it from ORDER BY",
                )
            )

    # 2. Native types over String (`schema-types-native-types`).
    for name, column in columns.items():
        profile = profiles.get(column.source_field or name)
        if profile is None:
            continue
        if profile.looks_like == "uuid" and "UUID" not in column.type:
            issues.append(
                LintIssue(
                    table.name,
                    "schema-types-native-types",
                    f"{name!r} holds UUIDs but is typed {column.type!r} "
                    "(16 bytes as UUID vs 36 as String)",
                    f"type {name!r} as UUID",
                )
            )
        if profile.looks_like == "timestamp" and not column.type.startswith(
            ("DateTime", "Nullable(DateTime")
        ):
            issues.append(
                LintIssue(
                    table.name,
                    "schema-types-native-types",
                    f"{name!r} holds timestamps but is typed {column.type!r}",
                    f"type {name!r} as DateTime64(3, 'UTC')",
                )
            )

    # 3. Retention has to be a decision, not an omission.
    if not table.ttl:
        issues.append(
            LintIssue(
                table.name,
                "schema-partition-lifecycle",
                "no TTL - retention is unbounded",
                "set a TTL, or state in `notes` why this table is kept forever",
            )
        )

    # 4. A leading high-cardinality key is the anti-pattern the whole prompt
    #    exists to prevent; catch it even if the model narrates otherwise.
    if table.order_by:
        first = table.order_by[0]
        if not EXPRESSION.search(first):
            column = columns.get(first)
            profile = profiles.get((column.source_field if column else None) or first)
            # 0.9, not 0.5: the target is a UUID-like key (ratio ~1.0). A
            # tighter bound misfires on small samples, where a genuine 3-value
            # enum over 6 events already shows 0.5.
            if profile and profile.cardinality_ratio > 0.9:
                issues.append(
                    LintIssue(
                        table.name,
                        "schema-pk-cardinality-order",
                        f"{first!r} leads the ordering key but is near-unique "
                        f"(ratio {profile.cardinality_ratio:.3f}), which destroys "
                        "granule pruning",
                        "lead with a low-cardinality filter column instead",
                    )
                )

    return issues


def lint_materialized_views(proposal: SchemaProposal) -> list[LintIssue]:
    """An MV writes `TO <target>`; if that table is not created in the same
    proposal, the MV statement fails at execute time - after the base tables
    have already been created, leaving the schema half-applied."""
    table_names = {t.name for t in proposal.tables}
    issues: list[LintIssue] = []

    for view in proposal.materialized_views:
        if not view.target_table:
            issues.append(
                LintIssue(
                    view.name,
                    "mv-target-missing",
                    "materialized view names no target table",
                    "set target_table, and define that table in `tables`",
                )
            )
        elif view.target_table not in table_names:
            issues.append(
                LintIssue(
                    view.name,
                    "mv-target-missing",
                    f"writes TO {view.target_table!r}, which is not defined in this "
                    "proposal - the MV would fail at execute time",
                    f"add {view.target_table!r} to `tables` with an aggregating "
                    'engine (e.g. "engine": "AggregatingMergeTree") whose columns '
                    "match the MV's SELECT",
                )
            )
        if not view.select:
            issues.append(
                LintIssue(
                    view.name,
                    "mv-select-missing",
                    "materialized view has no SELECT",
                    "provide the SELECT that populates the target table",
                )
            )

    return issues


_FROM_TABLE = re.compile(r"\bFROM\s+(?:[\w.]+\.)?`?(\w+)`?", re.IGNORECASE)


def lint_mv_coverage(proposal: SchemaProposal) -> list[LintIssue]:
    """Every table earns a rollup - the brief's 'define any materialized views
    or aggregations needed' is a requirement, not a per-table judgment call
    (`query-mv-incremental`). A table that is itself an MV's target is exempt:
    it is already an aggregate, and rolling up a rollup is not the ask.
    """
    mv_targets = {v.target_table for v in proposal.materialized_views if v.target_table}
    covered = {
        match.group(1)
        for view in proposal.materialized_views
        for match in [_FROM_TABLE.search(view.select)]
        if match
    }

    def is_covered(name: str) -> bool:
        # `render()` rewrites a SELECT's table references from logical to
        # physical (prefixed) names in place before validation - lint can run
        # again afterward (a repair loop re-lints the same proposal), so an
        # exact-name match alone would stop recognising its own coverage the
        # moment the prefix is applied. A physical name always *extends* the
        # logical one (`table_prefix + name`), so endswith is prefix-agnostic
        # without lint needing to know the configured prefix.
        return any(covered_name == name or covered_name.endswith(name) for covered_name in covered)

    issues: list[LintIssue] = []
    for table in proposal.tables:
        if table.name in mv_targets or is_covered(table.name):
            continue
        issues.append(
            LintIssue(
                table.name,
                "mv-coverage-missing",
                "no materialized view aggregates this table - every table "
                "needs a rollup, not just the ones with an obvious hot query",
                "add a materialized_views entry whose SELECT reads FROM "
                f"{table.name!r}, GROUP BY every dimension column (never "
                "user_id/application_id/event id), with -State aggregates for "
                "count/uniq/sum, writing to a new AggregatingMergeTree target",
            )
        )
    return issues


_SELECT_CLAUSE = re.compile(r"^\s*SELECT\s+(.*?)\s+FROM\s", re.IGNORECASE | re.DOTALL)
_TRAILING_ALIAS = re.compile(r"\bAS\s+`?(\w+)`?\s*$", re.IGNORECASE)
_BARE_IDENTIFIER = re.compile(r"^`?(\w+)`?$")


def _split_top_level(body: str) -> list[str]:
    """Split a SELECT clause's output list on its top-level commas - not ones
    nested inside a function call's parentheses (`countState()`, `if(a, b, c)`).
    """
    parts, depth, current = [], 0, ""
    for ch in body:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append(current)
            current = ""
        else:
            current += ch
    parts.append(current)
    return parts


def _select_output_names(select: str) -> list[str] | None:
    """The column name each output of a SELECT clause binds - the `AS` alias
    if given, otherwise the bare column name. `None` when the SELECT can't be
    read this confidently (`SELECT *`, no `FROM` found) - callers should skip
    rather than false-flag on those.
    """
    match = _SELECT_CLAUSE.match(select.strip())
    if not match:
        return None
    body = match.group(1).strip()
    if body == "*":
        return None
    names = []
    for part in _split_top_level(body):
        part = part.strip()
        if not part:
            continue
        alias = _TRAILING_ALIAS.search(part)
        if alias:
            names.append(alias.group(1))
            continue
        bare = _BARE_IDENTIFIER.match(part)
        names.append(bare.group(1) if bare else part)
    return names


def lint_mv_column_match(proposal: SchemaProposal) -> list[LintIssue]:
    """A materialized view's SELECT output columns must be named exactly like
    the target table's columns - ClickHouse matches an MV's insert-select to
    its `TO` target by column name, not position, and only enforces this once
    a row actually flows through on INSERT into the source table, not at
    CREATE time. A mismatch here passes DDL validation clean (the CREATE
    MATERIALIZED VIEW statement itself succeeds) and then fails for real the
    first time an event lands - THERE_IS_NO_COLUMN, the exact failure this
    check exists to catch before ClickHouse ever sees it.
    """
    tables = {t.name: t for t in proposal.tables}
    issues: list[LintIssue] = []
    for view in proposal.materialized_views:
        target = tables.get(view.target_table) if view.target_table else None
        if target is None:
            continue  # lint_materialized_views already flags a missing target
        names = _select_output_names(view.select)
        if names is None:
            continue
        target_columns = {c.name for c in target.columns}
        unmatched = [n for n in names if n not in target_columns]
        if unmatched:
            issues.append(
                LintIssue(
                    view.name,
                    "mv-column-mismatch",
                    f"SELECT outputs {unmatched!r}, which "
                    f"{'is' if len(unmatched) == 1 else 'are'} not a column on "
                    f"target table {target.name!r} (target has "
                    f"{sorted(target_columns)!r})",
                    "add `AS <exact target column name>` to each mismatched "
                    "output, or add the missing column(s) to the target table - "
                    "ClickHouse matches an MV's output to its target by column "
                    "name, not position",
                )
            )
    return issues


def lint_proposal(
    proposal: SchemaProposal,
    profiles: list[FieldProfile],
    *,
    per_table: dict[str, dict[str, FieldProfile]] | None = None,
) -> list[LintIssue]:
    """`per_table` maps a table name to the profiles of its own event group.

    With one table per user action, a field name can appear in several groups
    with different characteristics - `os` is 93% present everywhere, but an
    action-specific field need not be. Judging each table against its own
    group's profiles avoids a merge deciding which version wins; the flat
    `profiles` list stays as the fallback for tables not in the map.
    """
    by_name = {p.name: p for p in profiles}
    targets = {v.target_table for v in proposal.materialized_views if v.target_table}
    issues = [
        i
        for t in proposal.tables
        for i in lint_table(
            t, (per_table or {}).get(t.name, by_name), mv_target=t.name in targets
        )
    ]
    return (
        issues
        + lint_materialized_views(proposal)
        + lint_mv_coverage(proposal)
        + lint_mv_column_match(proposal)
    )
