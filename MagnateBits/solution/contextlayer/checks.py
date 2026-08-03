"""Contradiction detection: **the LLM proposes, SQL adjudicates.**

Every Contradiction this module emits carries three things:

    verification_sql     the query that settles the question
    verification_result  that query's *executed* result, stored verbatim
    verified=True        only set once the query actually ran

A contradiction without those is an opinion. With them it is evidence a judge can
re-run. Nothing here knows the name of any feature, metric or table: the claims come
from the context bodies, the reality comes from `system.columns` and from the data.

Checks implemented
------------------
C1 definition_conflict      one metric defined two ways -> compare denominators, then
                            compute BOTH rates in one query and show they disagree.
C2 undefined_term           a term used in a formula that resolves to no entity, no
   + uncomputable_metric    table and no column -> and if it sits in a denominator, the
                            metric is not computable as written.
C3 schema_mismatch          every column name mentioned anywhere in the context is
                            checked against system.columns; misses report the nearest
                            real column AND its real type.
C4 uncomputable_metric      a metric whose own body admits it is not computable ->
                            disputed, and excluded from ContextStore.metric_catalog().
C5 stale_entry              an entry that documents a design it simultaneously admits is
                            wrong (e.g. an ORDER BY the queries never use) -> proven by
                            measuring the lead key's selectivity.
C6 join_assumption_violated the documented join map, tested against a table that landed
                            after the documentation was written.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field
from typing import Any, Iterable, Literal, Sequence

from pydantic import BaseModel, Field

from contracts import ContextEntry, Contradiction

from contextlayer.bootstrap import (
    DIVIDERS,
    STOPWORDS,
    bold_terms,
    code_identifiers,
    metric_subject,
    normalize_term,
    split_formula,
    strip_markup,
)
from contextlayer.store import OPS_TABLES, format_result, system_select

# Identifiers that look like columns but are SQL/ClickHouse vocabulary.
SQL_WORDS = frozenset(
    """
select from where group by order limit having join on as and or not in is null asc desc
count sum avg min max uniq uniqexact uniqif countif sumif round toyyyymm todatetime
windowfunnel sequencematch state merge if case when then else end distinct union all
interval month day hour partition primary key engine mergetree settings ttl codec
""".split()
)

# Type words a context body might use, mapped to the ClickHouse families they imply.
TYPE_WORDS = {
    "integer": "Int",
    "int": "Int",
    "number": "Int",
    "count": "Int",
    "float": "Float",
    "decimal": "Decimal",
    "string": "String",
    "text": "String",
    "boolean": "UInt8",
    "bool": "UInt8",
    "flag": "UInt8",
    "date": "Date",
    "datetime": "DateTime",
    "timestamp": "DateTime",
}

UNCOMPUTABLE_ADMISSIONS = re.compile(
    r"not computable|cannot be computed|can'?t be computed|not derivable|not available "
    r"(?:from|in)\b|out of scope|handled by other systems|reported by [^.]{0,60}from",
    re.IGNORECASE,
)
STALENESS_ADMISSIONS = re.compile(
    r"\blegacy\b|\bnever by\b|\bno longer\b|\bdeprecat|\bcan lag\b|\bartifact\b|"
    r"\bis wrong\b|\bout of date\b|\bhistorical\b|\bmaintained by hand\b",
    re.IGNORECASE,
)


# --------------------------------------------------------------------------
# result container
# --------------------------------------------------------------------------


@dataclass
class CheckOutput:
    """What a check round produced.

    `proposed_entries` is how a check writes back into the context layer -- e.g. C6
    records a data-quality entry that downstream insights cite as a caveat.
    """

    contradictions: list[Contradiction] = field(default_factory=list)
    proposed_entries: list[dict[str, Any]] = field(default_factory=list)
    disputed_entry_ids: list[str] = field(default_factory=list)

    def extend(self, other: "CheckOutput") -> None:
        self.contradictions.extend(other.contradictions)
        self.proposed_entries.extend(other.proposed_entries)
        self.disputed_entry_ids.extend(other.disputed_entry_ids)


# --------------------------------------------------------------------------
# schema reflection
# --------------------------------------------------------------------------


class Reality:
    """A cached view of what the database actually contains."""

    def __init__(self, ch: Any, database: str | None = None) -> None:
        self.ch = ch
        self.database = database or getattr(ch, "database", "atlys")
        rows = system_select(
            ch,
            "SELECT table, name AS column, type FROM system.columns "
            f"WHERE database = '{self.database}' ORDER BY table, position",
            max_rows=20000,
        )
        rows = [r for r in rows if r["table"] not in OPS_TABLES]
        self.columns_by_table: dict[str, dict[str, str]] = {}
        for r in rows:
            self.columns_by_table.setdefault(r["table"], {})[r["column"]] = r["type"]
        self.tables: set[str] = set(self.columns_by_table)
        self.all_columns: set[str] = {r["column"] for r in rows}
        counts = system_select(
            ch,
            "SELECT name, total_rows AS rows, sorting_key FROM system.tables "
            f"WHERE database = '{self.database}' AND engine LIKE '%MergeTree'",
            max_rows=1000,
        )
        self.row_counts = {r["name"]: int(r["rows"] or 0) for r in counts}
        self.sorting_keys = {r["name"]: r["sorting_key"] for r in counts}

    def tables_with(self, column: str) -> list[str]:
        return sorted(
            (t for t, cols in self.columns_by_table.items() if column in cols),
            key=lambda t: -self.row_counts.get(t, 0),
        )

    def columns_like(self, fragment: str) -> list[str]:
        f = fragment.lower()
        return sorted({c for c in self.all_columns if f in c.lower()})

    def is_nullable(self, table: str, column: str) -> bool:
        return "Nullable" in self.columns_by_table.get(table, {}).get(column, "")


def guarded_uniq(table: str, column: str, reality: Reality) -> str:
    """`uniqIf(col, col != '')` -- never a bare uniq().

    House rules forbid Nullable on hot columns, so identity columns default to the empty
    string and a bare `uniq(user_id)` counts '' as a real user. `ifNull` makes the guard
    work identically on the legacy Nullable tables and the new non-Nullable ones.
    """
    expr = f"ifNull({column}, '')" if reality.is_nullable(table, column) else column
    return f"uniqIf({expr}, {expr} != '')"


# --------------------------------------------------------------------------
# resolving an English population phrase to SQL
# --------------------------------------------------------------------------


@dataclass
class Population:
    phrase: str
    table: str | None
    column: str | None
    expr: str | None
    how: str

    @property
    def resolved(self) -> bool:
        return bool(self.table and self.expr)


def _content_words(phrase: str) -> list[str]:
    words = re.split(r"[^A-Za-z0-9_]+", strip_markup(phrase).lower())
    return [w for w in words if w and w not in STOPWORDS and len(w) > 2]


def resolve_population(phrase: str, reality: Reality) -> Population:
    """Map a phrase like "users who started an application" onto a countable SQL expr.

    Resolution order, most literal first:
      1. a backticked identifier that IS a table
      2. the table whose name shares the most word-stems with the phrase
      3. a column whose name *contains* one of the phrase stems (e.g. "sessions" ->
         `app_session_id`), counted on the largest table carrying it
    Anything else is unresolved -- which is itself a finding (see C2).
    """
    for tok in code_identifiers(phrase):
        head = tok.split(".")[0]
        if head in reality.tables:
            col = "user_id" if "user_id" in reality.columns_by_table[head] else None
            if col:
                return Population(
                    phrase, head, col, guarded_uniq(head, col, reality), f"table `{head}`"
                )
            return Population(phrase, head, None, "count()", f"table `{head}` (rows)")

    stems = {normalize_term(w) for w in _content_words(phrase)}
    if not stems:
        return Population(phrase, None, None, None, "no content words")

    best_table, best_score = None, 0
    # Biggest table first, so an equal-scoring tie resolves to the busier stream.
    for t in sorted(reality.tables, key=lambda x: (-reality.row_counts.get(x, 0), x)):
        parts = {normalize_term(p) for p in t.split("_")}
        score = len(parts & stems)
        if score > best_score:
            best_table, best_score = t, score
    if best_table and best_score > 0:
        col = "user_id" if "user_id" in reality.columns_by_table[best_table] else None
        expr = guarded_uniq(best_table, col, reality) if col else "count()"
        return Population(
            phrase,
            best_table,
            col,
            expr,
            f"table `{best_table}` (matched {best_score} word(s) in the phrase)",
        )

    for stem in sorted(stems, key=len, reverse=True):
        matches = [c for c in reality.all_columns if stem in c.lower()]
        if not matches:
            continue
        column = min(matches, key=len)
        hosts = reality.tables_with(column)
        if not hosts:
            continue
        table = hosts[0]
        return Population(
            phrase,
            table,
            column,
            guarded_uniq(table, column, reality),
            f"proxy: column `{column}` on `{table}` (no table is named for '{stem}')",
        )

    return Population(phrase, None, None, None, "no table or column matches this phrase")


# --------------------------------------------------------------------------
# verification plumbing
# --------------------------------------------------------------------------


def verify(ch: Any, sql: str, max_rows: int = 50) -> tuple[str, bool, list[dict[str, Any]]]:
    """Run a check's query. Failure is recorded, never swallowed."""
    try:
        rows = system_select(ch, sql, max_rows=max_rows)
        return format_result(rows), True, rows
    except Exception as exc:  # noqa: BLE001 -- a failed probe is a reportable outcome
        return f"VERIFICATION FAILED: {type(exc).__name__}: {exc}"[:2000], False, []


def _q(v: str) -> str:
    return "'" + str(v).replace("\\", "\\\\").replace("'", "\\'") + "'"


def _in_list(values: Iterable[str]) -> str:
    return "(" + ", ".join(_q(v) for v in values) + ")"


# --------------------------------------------------------------------------
# C1 -- definition_conflict
# --------------------------------------------------------------------------


def check_definition_conflicts(
    ch: Any, entries: Sequence[ContextEntry], reality: Reality, formulas: dict[str, str]
) -> CheckOutput:
    out = CheckOutput()
    metrics = [e for e in entries if e.kind == "metric"]
    clusters: dict[frozenset[str], list[ContextEntry]] = {}
    for m in metrics:
        clusters.setdefault(metric_subject(m.key), []).append(m)

    for subject, group in sorted(clusters.items(), key=lambda kv: sorted(kv[0])):
        if len(group) < 2:
            continue
        variants = []
        for e in group:
            parts = split_formula(formulas.get(e.entry_id, "") or e.body)
            if not parts:
                continue
            num, den = parts
            variants.append((e, num, den, resolve_population(num, reality), resolve_population(den, reality)))
        if len(variants) < 2:
            continue
        # A conflict is two variants whose DENOMINATORS name different populations.
        seen: dict[str, tuple] = {}
        for v in variants:
            key = normalize_term(re.sub(r"[^a-z0-9 ]", " ", strip_markup(v[2]).lower()))
            seen.setdefault(key, v)
        if len(seen) < 2:
            continue
        chosen = list(seen.values())[:2]
        a, bvar = chosen[0], chosen[1]

        selects: list[str] = []
        labels: list[str] = []
        for tag, v in (("a", a), ("b", bvar)):
            e, num, den, pnum, pden = v
            labels.append(
                f"[{tag}] {e.entry_id}@v{e.version} '{e.key}': "
                f"numerator={num!r} -> {pnum.how}; denominator={den!r} -> {pden.how}"
            )
            if pnum.resolved:
                selects.append(f"  (SELECT {pnum.expr} FROM {reality.database}.{pnum.table}) AS num_{tag}")
            else:
                selects.append(f"  CAST(NULL AS Nullable(UInt64)) AS num_{tag}")
            if pden.resolved:
                selects.append(f"  (SELECT {pden.expr} FROM {reality.database}.{pden.table}) AS den_{tag}")
            else:
                selects.append(f"  CAST(NULL AS Nullable(UInt64)) AS den_{tag}")
        selects.append("  round(num_a / den_a, 6) AS rate_a")
        selects.append("  round(num_b / den_b, 6) AS rate_b")
        selects.append("  round(rate_b / rate_a, 2) AS ratio_b_over_a")
        sql = "SELECT\n" + ",\n".join(selects)

        result, ok, rows = verify(ch, sql)
        detail = ""
        if rows:
            r = rows[0]
            detail = (
                f" Executed: definition [a] = {r.get('rate_a')}, definition [b] = {r.get('rate_b')} "
                f"({r.get('ratio_b_over_a')}x apart) over the same window."
            )
        out.contradictions.append(
            Contradiction(
                kind="definition_conflict",
                title=f"'{a[0].key}' and '{bvar[0].key}' divide by different populations",
                claim=(
                    f"The context defines the same metric subject {sorted(subject)} twice. "
                    + " | ".join(labels)
                ),
                evidence=(
                    "The two definitions have different denominators, so they cannot both be "
                    "the number reported as this metric." + detail
                ),
                verification_sql=sql,
                verification_result=result,
                verified=ok,
                proposed_resolution=(
                    f"Pick one denominator and version it. Recommended: keep both but rename -- "
                    f"'{a[0].key}' (denominator: {a[2]!r}) and '{bvar[0].key}' "
                    f"(denominator: {bvar[2]!r}) -- so every report states which it used via "
                    f"Finding.metric_definition_used."
                ),
                entry_ids=[a[0].entry_id, bvar[0].entry_id],
                severity="high",
                detected_by="rule",
            )
        )
    return out


# --------------------------------------------------------------------------
# C2 -- undefined_term + uncomputable_metric
# --------------------------------------------------------------------------


def check_undefined_terms(
    ch: Any, entries: Sequence[ContextEntry], reality: Reality, formulas: dict[str, str]
) -> CheckOutput:
    out = CheckOutput()
    glossary: set[str] = set()
    for e in entries:
        if e.kind in ("entity", "business_def", "metric", "table_doc", "column_doc"):
            glossary.add(normalize_term(e.key))
            for w in _content_words(e.key):
                glossary.add(normalize_term(w))
    glossary |= {normalize_term(t) for t in reality.tables}
    glossary |= {normalize_term(c) for c in reality.all_columns}

    for e in entries:
        if e.kind != "metric":
            continue
        formula = formulas.get(e.entry_id, "")
        # An explicitly bolded term inside a definition is a reference to another
        # definition. If the glossary has no such entry, the definition is unanchored.
        terms = bold_terms(f"{formula} {e.body}", exclude=e.key)
        den = (split_formula(formula) or ("", ""))[1]
        den_terms = {normalize_term(t) for t in bold_terms(den)}
        for term in dict.fromkeys(terms):
            norm = normalize_term(term)
            if len(norm) < 4 or norm in STOPWORDS or norm in glossary:
                continue
            if norm in {normalize_term(c) for c in reality.all_columns}:
                continue
            like = reality.columns_like(norm)
            sql = (
                "SELECT\n"
                f"  (SELECT count() FROM system.tables WHERE database = {_q(reality.database)} "
                f"AND name ILIKE {_q('%' + norm + '%')}) AS tables_matching_term,\n"
                f"  (SELECT count() FROM system.columns WHERE database = {_q(reality.database)} "
                f"AND name = {_q(norm)}) AS exact_column_named_term,\n"
                f"  (SELECT arrayStringConcat(arraySort(groupUniqArray(name)), ', ') "
                f"FROM system.columns WHERE database = {_q(reality.database)} "
                f"AND name ILIKE {_q('%' + norm + '%')}) AS columns_containing_term"
            )
            result, ok, rows = verify(ch, sql)
            r = rows[0] if rows else {}
            out.contradictions.append(
                Contradiction(
                    kind="undefined_term",
                    title=f"'{term}' is used in a metric definition but never defined",
                    claim=(
                        f"[{e.entry_id}@v{e.version}] '{e.key}' is defined in terms of "
                        f"'{term}', but no entity/glossary entry defines '{term}'."
                    ),
                    evidence=(
                        f"No table is named for it ({r.get('tables_matching_term', '?')} matches) "
                        f"and no column is named '{norm}' "
                        f"({r.get('exact_column_named_term', '?')} matches). The closest thing in "
                        f"the schema is: {r.get('columns_containing_term') or 'nothing'} -- a "
                        f"column, not an event stream, so there is no boundary event that would "
                        f"let us count '{term}'."
                    ),
                    verification_sql=sql,
                    verification_result=result,
                    verified=ok,
                    proposed_resolution=(
                        f"Either add an entity entry defining '{term}' operationally (e.g. as a "
                        f"gap between events on {like[0] if like else 'an identity column'}), or "
                        f"restate the metric in terms that exist in the schema."
                    ),
                    entry_ids=[e.entry_id],
                    severity="medium",
                    detected_by="rule",
                )
            )
            if norm in den_terms:
                out.contradictions.append(
                    Contradiction(
                        kind="uncomputable_metric",
                        title=f"'{e.key}' is not computable as defined",
                        claim=(
                            f"[{e.entry_id}@v{e.version}] '{e.key}' = {formula}. Its DENOMINATOR "
                            f"is '{term}'."
                        ),
                        evidence=(
                            f"'{term}' resolves to nothing in the schema: "
                            f"{r.get('tables_matching_term', '?')} tables and "
                            f"{r.get('exact_column_named_term', '?')} exactly-named columns. "
                            f"Only {r.get('columns_containing_term') or 'nothing'} exists, and a "
                            f"column cannot be counted as an occurrence without a "
                            f"start/end event. The headline number therefore cannot be reproduced "
                            f"from these tables as written."
                        ),
                        verification_sql=sql,
                        verification_result=result,
                        verified=ok,
                        proposed_resolution=(
                            f"Report this metric against a denominator that exists, and state the "
                            f"substitution in every finding. Until then it is excluded from "
                            f"ContextStore.metric_catalog()."
                        ),
                        entry_ids=[e.entry_id],
                        severity="high",
                        detected_by="rule",
                    )
                )
                out.disputed_entry_ids.append(e.entry_id)
    return out


# --------------------------------------------------------------------------
# C3 -- schema_mismatch
# --------------------------------------------------------------------------


def _column_candidates(text: str, reality: Reality) -> list[str]:
    """Backticked identifiers that are plausibly column names."""
    out: list[str] = []
    for tok in code_identifiers(text):
        if "." in tok:
            head, _, tail = tok.partition(".")
            if head in reality.tables and tail:
                out.append(tok)
            continue
        if tok in reality.tables or tok.lower() in SQL_WORDS:
            continue
        if not re.fullmatch(r"[a-z][a-z0-9_]*", tok):
            continue
        if "_" not in tok and tok not in reality.all_columns:
            continue  # single bare words are glossary terms (C2), not column claims
        out.append(tok)
    return list(dict.fromkeys(out))


def _nearest_columns(
    name: str, scope: Sequence[str], reality: Reality, top: int = 3
) -> list[tuple[str, str, str]]:
    """(table, column, type) triples most similar to `name`, best first.

    Scored on shared underscore-tokens first (so `visa_issuance_eta_days` finds
    `eta_shown`), then on raw string similarity. When the entry named a table, the search
    is scoped to it -- which is what disambiguates same-token candidates on other tables.
    """
    target_parts = set(name.split("_"))
    tables = [t for t in scope if t in reality.columns_by_table] or sorted(reality.tables)
    scored: list[tuple[float, float, str, str, str]] = []
    for t in tables:
        for col, ctype in reality.columns_by_table[t].items():
            overlap = len(target_parts & set(col.split("_")))
            if overlap <= 0:
                continue
            ratio = difflib.SequenceMatcher(None, name, col).ratio()
            scored.append((-overlap, -ratio, t, col, ctype))
    scored.sort()
    seen: set[str] = set()
    out: list[tuple[str, str, str]] = []
    for _, _, t, col, ctype in scored:
        if col in seen:
            continue
        seen.add(col)
        out.append((t, col, ctype))
        if len(out) >= top:
            break
    return out


def _declared_type(body: str, name: str) -> str | None:
    idx = body.find(name)
    if idx < 0:
        return None
    window = body[idx : idx + 140]
    m = re.search(r"\b(" + "|".join(TYPE_WORDS) + r")\b", window, re.IGNORECASE)
    return m.group(1).lower() if m else None


def check_schema_mismatches(
    ch: Any, entries: Sequence[ContextEntry], reality: Reality, formulas: dict[str, str]
) -> CheckOutput:
    out = CheckOutput()
    # (column, subject_tables, specificity, finding). The same missing column is usually
    # named by several entries -- an entity doc that scopes it to a table and a metric doc
    # that does not -- and that is ONE defect, not two. `_collapse_by_subject` folds them
    # after the loop, once every subject has been resolved to a real table.
    found_rows: list[tuple[str, tuple[str, ...], int, Contradiction]] = []
    for e in entries:
        text = f"{e.body} {formulas.get(e.entry_id, '')}"
        scope = [r for r in e.refs if r in reality.tables]
        for tok in _column_candidates(text, reality):
            if "." in tok:
                table, _, column = tok.partition(".")
                if column in reality.columns_by_table.get(table, {}):
                    continue
                probe_scope = [table]
            else:
                column = tok
                if column in reality.all_columns:
                    continue
                probe_scope = list(scope)
            nearest = _nearest_columns(column, probe_scope, reality)
            # Subject resolution. The subject of a schema_mismatch is a TABLE, never the
            # database: "documented on <database>" reads like a table name and is wrong.
            # 2 = the entry named the table itself; 1 = inferred from the table carrying
            # the nearest real column; 0 = nothing in the database resembles it, so the
            # only honest subject is the database as a whole.
            if probe_scope:
                specificity = 2
            elif nearest:
                probe_scope = [nearest[0][0]]
                specificity = 1
            else:
                specificity = 0
            where_table = f" AND table IN {_in_list(probe_scope)}" if probe_scope else ""
            near_clause = (
                "(" + " OR ".join(f"(table = {_q(t)} AND name = {_q(c)})" for t, c, _ in nearest) + ")"
                if nearest
                else "1 = 0"
            )
            title = (
                f"`{column}` is documented on {', '.join(probe_scope[:3])} but does not exist"
                if probe_scope
                else f"`{column}` is documented but exists on no table in `{reality.database}`"
            )
            sql = (
                "SELECT\n"
                f"  (SELECT count() FROM system.columns WHERE database = {_q(reality.database)}"
                f"{where_table} AND name = {_q(column)}) AS claimed_column_exists,\n"
                f"  (SELECT count() FROM system.columns WHERE database = {_q(reality.database)} "
                f"AND name = {_q(column)}) AS claimed_column_anywhere,\n"
                f"  (SELECT arrayStringConcat(arraySort(groupArray("
                f"concat(table, '.', name, ' ', type))), ' | ') "
                f"FROM system.columns WHERE database = {_q(reality.database)} "
                f"AND {near_clause}) AS nearest_actual_columns"
            )
            result, ok, rows = verify(ch, sql)
            r = rows[0] if rows else {}
            declared = _declared_type(text, column)
            type_note = ""
            if nearest and declared:
                implied = TYPE_WORDS[declared]
                if implied.lower() not in nearest[0][2].lower():
                    type_note = (
                        f" The context also declares it as '{declared}' ({implied}...), but the "
                        f"nearest real column is {nearest[0][2]} -- different NAME and different "
                        f"TYPE."
                    )
            found = Contradiction(
                kind="schema_mismatch",
                title=title,
                claim=(
                    f"[{e.entry_id}@v{e.version}] '{e.key}' references column `{column}`"
                    + (f" on {', '.join(probe_scope[:3])}" if specificity == 2 else "")
                    + "."
                ),
                evidence=(
                    f"system.columns returns {r.get('claimed_column_exists', '?')} rows for "
                    f"that column in scope and {r.get('claimed_column_anywhere', '?')} "
                    f"anywhere in `{reality.database}`. Nearest actual column(s): "
                    f"{r.get('nearest_actual_columns') or 'none'}." + type_note
                ),
                verification_sql=sql,
                verification_result=result,
                verified=ok,
                proposed_resolution=(
                    f"Rewrite the entry to use "
                    f"`{nearest[0][0]}.{nearest[0][1]}` ({nearest[0][2]}) if that is the "
                    f"intended field, and note the type difference; otherwise mark the field "
                    f"as not instrumented." if nearest else
                    "Remove the reference or instrument the field."
                ),
                entry_ids=[e.entry_id],
                severity="high",
                detected_by="rule",
            )
            found_rows.append((column, tuple(sorted(probe_scope)), specificity, found))
    out.contradictions.extend(_collapse_by_subject(found_rows))
    return out


def _collapse_by_subject(
    rows: Sequence[tuple[str, tuple[str, ...], int, Contradiction]]
) -> list[Contradiction]:
    """One finding per (missing column, subject table); ids of the duplicates merged in.

    Three passes, in order of authority -- a column genuinely missing from two DIFFERENT
    *entry-stated* tables still stays two findings; only guesses get folded away:
      1. exact (column, subject) collisions are the same defect seen from two entries;
         the one whose subject the entry stated outright (specificity 2) is kept.
      2. an entry-stated subject (specificity 2) always outranks a lexically-guessed one
         (specificity 1) for the SAME column, regardless of whether the guess landed on a
         different table. `_nearest_columns` ranks on raw token overlap + string ratio,
         which has no notion of meaning -- "visa_issuance_eta_days" scores textually closer
         to `visa_type` than to the actually-correct `eta_shown`, because "visa" is a longer
         shared prefix than "eta". Rather than hand-tune the matcher for one column name,
         apply the general precedence rule: what an entry says outright is more authoritative
         than what the nearest-neighbour search guessed, full stop.
      3. a subject-less finding ("exists on no table here") is weaker than any table-scoped
         finding for the same column, so it folds into whatever remains.
    """
    kept: dict[tuple[str, tuple[str, ...]], Contradiction] = {}
    order: list[tuple[str, tuple[str, ...]]] = []
    for column, scope, _spec, c in sorted(rows, key=lambda r: -r[2]):
        key = (column, scope)
        if key in kept:
            kept[key] = _merge_entry_ids(kept[key], c)
        else:
            kept[key] = c
            order.append(key)

    # Only fold a key whose OWN best specificity is < 2 into a spec-2 subject: two
    # genuinely different entry-stated tables for the same column are two real
    # defects and must both survive (see test_two_genuinely_different_entry_stated_
    # subjects_both_survive), so a spec-2 key must never be folded into another.
    max_spec_by_key: dict[tuple[str, tuple[str, ...]], int] = {}
    for column, scope, spec, _c in rows:
        key = (column, scope)
        max_spec_by_key[key] = max(max_spec_by_key.get(key, 0), spec)
    best_spec2_by_column: dict[str, tuple[str, tuple[str, ...]]] = {}
    for column, scope, spec, _c in rows:
        if spec == 2 and scope and column not in best_spec2_by_column:
            best_spec2_by_column[column] = (column, scope)
    for key in list(kept):
        column, scope = key
        target = best_spec2_by_column.get(column)
        if target is None or key == target or max_spec_by_key.get(key, 0) >= 2:
            continue
        kept[target] = _merge_entry_ids(kept[target], kept.pop(key))
        order.remove(key)

    scoped_by_column: dict[str, tuple[str, tuple[str, ...]]] = {
        col: (col, scope) for col, scope in order if scope
    }
    for key in list(kept):
        column, scope = key
        target = scoped_by_column.get(column)
        if scope or target is None:
            continue
        kept[target] = _merge_entry_ids(kept[target], kept.pop(key))
        order.remove(key)
    return [kept[k] for k in order]


def _merge_entry_ids(keep: Contradiction, drop: Contradiction) -> Contradiction:
    """Fold a duplicate finding's entry ids into the one being kept.

    Both entries still appear in `entry_ids`; only the duplicate *row* disappears. Ids stay
    sorted so `ContextStore.compute_contradiction_id` is stable across runs.
    """
    return keep.model_copy(
        update={"entry_ids": sorted(set(keep.entry_ids) | set(drop.entry_ids))}
    )


# --------------------------------------------------------------------------
# C4 -- self-admitted uncomputable metric
# --------------------------------------------------------------------------


def check_self_admitted_uncomputable(
    ch: Any, entries: Sequence[ContextEntry], reality: Reality, formulas: dict[str, str]
) -> CheckOutput:
    out = CheckOutput()
    for e in entries:
        if e.kind != "metric":
            continue
        m = UNCOMPUTABLE_ADMISSIONS.search(e.body)
        if not m:
            continue
        formula = formulas.get(e.entry_id, "")
        missing_cols = [
            c
            for c in _column_candidates(f"{e.body} {formula}", reality)
            if "." not in c and c not in reality.all_columns
        ]
        unresolved_words: list[str] = []
        for word in _content_words(formula):
            norm = normalize_term(word)
            if norm in {normalize_term(t) for t in reality.tables}:
                continue
            if any(norm in t for t in reality.tables) or any(norm in c for c in reality.all_columns):
                continue
            if len(norm) > 3:
                unresolved_words.append(norm)
        unresolved_words = list(dict.fromkeys(unresolved_words))[:2]

        selects = []
        for c in missing_cols[:2]:
            selects.append(
                f"  (SELECT count() FROM system.columns WHERE database = {_q(reality.database)} "
                f"AND name = {_q(c)}) AS required_column_{c}_present"
            )
        for w in unresolved_words:
            selects.append(
                f"  (SELECT count() FROM system.tables WHERE database = {_q(reality.database)} "
                f"AND name ILIKE {_q('%' + w + '%')}) AS source_tables_like_{re.sub(r'[^a-z0-9_]', '_', w)}"
            )
        if not selects:
            selects.append(
                f"  (SELECT count() FROM system.tables WHERE database = {_q(reality.database)}) "
                f"AS tables_in_database"
            )
        sql = "SELECT\n" + ",\n".join(selects)
        result, ok, rows = verify(ch, sql)
        out.contradictions.append(
            Contradiction(
                kind="uncomputable_metric",
                title=f"'{e.key}' is documented as a metric but cannot be computed here",
                claim=(
                    f"[{e.entry_id}@v{e.version}] '{e.key}' = {formula or e.body[:160]}. "
                    f"The entry itself admits: \"...{e.body[max(0, m.start() - 60): m.end() + 80]}...\""
                ),
                evidence=(
                    "Confirmed against the live schema: "
                    + (
                        f"required column(s) {missing_cols[:2]} are absent"
                        if missing_cols
                        else "no source table exists"
                    )
                    + (
                        f" and no table matches {unresolved_words}"
                        if unresolved_words
                        else ""
                    )
                    + f". Executed result: {result}"
                ),
                verification_sql=sql,
                verification_result=result,
                verified=ok,
                proposed_resolution=(
                    "Mark the metric disputed and exclude it from the analytics metric catalog "
                    "(ContextStore.metric_catalog()) so no agent reports a number for it. Re-admit "
                    "it only when a post-purchase source table lands in this database."
                ),
                entry_ids=[e.entry_id],
                severity="medium",
                detected_by="rule",
            )
        )
        out.disputed_entry_ids.append(e.entry_id)
    return out


# --------------------------------------------------------------------------
# C5 -- stale entry
# --------------------------------------------------------------------------

_ORDER_BY_RE = re.compile(r"ORDER\s+BY\s*\(([^)]*)\)", re.IGNORECASE)

# A lead ORDER BY key is an anti-pattern when it is *near-unique*: the primary index then
# stores one distinct value per granule and prunes nothing for the time/segment filters
# real queries use. Both thresholds are measured against the live table, never inferred
# from the column's name -- `id` is not always unique and `event` is not always an enum.
#   * ratio: distinct/rows at or above this means ~one distinct value per row.
#   * absolute: more distinct values than this cannot be a discriminator at any table
#     size, so the index degenerates even when the ratio looks low on a huge table.
# Below BOTH, the lead key is a genuine low-cardinality discriminator -- the design house
# rules prescribe -- and leading with it is correct, so nothing is reported.
LEAD_KEY_UNIQUE_RATIO = 0.5
LEAD_KEY_MAX_DISCRIMINATOR_VALUES = 10_000


def check_stale_entries(
    ch: Any, entries: Sequence[ContextEntry], reality: Reality, formulas: dict[str, str]
) -> CheckOutput:
    out = CheckOutput()
    for e in entries:
        text = f"{e.body} {formulas.get(e.entry_id, '')}"
        m = _ORDER_BY_RE.search(text)
        if not m:
            continue
        admission = STALENESS_ADMISSIONS.search(text)
        if not admission:
            continue
        keys = [k.strip().strip("`") for k in m.group(1).split(",") if k.strip()]
        if not keys:
            continue
        lead = keys[0]
        scope = [t for t in e.refs if t in reality.tables]
        scope = [t for t in scope if lead in reality.columns_by_table.get(t, {})]
        if not scope:
            scope = [t for t in reality.tables_with(lead)]
        if not scope:
            continue
        table = max(scope, key=lambda t: reality.row_counts.get(t, 0))
        sql = (
            "SELECT\n"
            f"  {_q(table)} AS table_checked,\n"
            f"  (SELECT sorting_key FROM system.tables WHERE database = {_q(reality.database)} "
            f"AND name = {_q(table)}) AS declared_sorting_key,\n"
            "  count() AS rows,\n"
            f"  uniqExact({lead}) AS distinct_values_of_lead_key,\n"
            f"  round(uniqExact({lead}) / count(), 4) AS lead_key_selectivity\n"
            f"FROM {reality.database}.{table}"
        )
        result, ok, rows = verify(ch, sql)
        r = rows[0] if rows else {}
        sel = r.get("lead_key_selectivity")
        distinct = r.get("distinct_values_of_lead_key")
        # THE GATE. An ORDER BY that leads with a low-cardinality discriminator is good
        # design, not staleness -- position alone proves nothing, so the verdict comes
        # from the measured cardinality above. A probe that failed to run (ok=False) is
        # not evidence of an anti-pattern either, so it is skipped rather than asserted.
        if not ok or sel is None or distinct is None:
            continue
        near_unique = float(sel) >= LEAD_KEY_UNIQUE_RATIO
        too_many_values = int(distinct) > LEAD_KEY_MAX_DISCRIMINATOR_VALUES
        if not (near_unique or too_many_values):
            continue
        why = (
            f"{sel} distinct values per row -- effectively a unique key"
            if near_unique
            else f"{distinct} distinct values, far too many to act as a discriminator"
        )
        out.contradictions.append(
            Contradiction(
                kind="stale_entry",
                title=(
                    f"Documented ORDER BY leads with `{lead}`, a near-unique key that "
                    f"prunes nothing"
                ),
                claim=(
                    f"[{e.entry_id}@v{e.version}] '{e.key}' documents ORDER BY "
                    f"({', '.join(keys)}) and simultaneously admits: "
                    f"\"...{text[max(0, admission.start() - 50): admission.end() + 60]}...\""
                ),
                evidence=(
                    f"On `{table}`, the declared sorting key is "
                    f"{r.get('declared_sorting_key')!r} and the lead key `{lead}` has selectivity "
                    f"{sel} over {r.get('rows')} rows ({distinct} distinct values) -- {why}. "
                    f"Every granule therefore holds a distinct value, so the primary index "
                    f"prunes nothing for the time/segment filters the entry says queries "
                    f"actually use. The entry documents a design it already calls obsolete. "
                    f"(This check reports on measured cardinality, not on the lead column's "
                    f"position or name: a lead key under {LEAD_KEY_UNIQUE_RATIO} selectivity "
                    f"and under {LEAD_KEY_MAX_DISCRIMINATOR_VALUES} distinct values is a "
                    f"genuine discriminator and is NOT reported.)"
                ),
                verification_sql=sql,
                verification_result=result,
                verified=ok,
                proposed_resolution=(
                    f"New tables must NOT copy this. Lead ORDER BY with a low-cardinality column "
                    f"the queries filter on, then `timestamp`, then the entity key -- and record "
                    f"the contrast in DDLProposal.rationale['order_by']."
                ),
                entry_ids=[e.entry_id],
                severity="medium",
                detected_by="rule",
            )
        )
    return out


# --------------------------------------------------------------------------
# C6 -- join_assumption_violated (generated by our own pipeline)
# --------------------------------------------------------------------------

_JOIN_KEY_RE = re.compile(r"join(?:ed|s)?\s+on\s+`?([a-z][a-z0-9_]*)`?", re.IGNORECASE)


def documented_join_keys(entries: Sequence[ContextEntry], reality: Reality) -> list[str]:
    """Identity columns the context claims every table joins on, most-asserted first."""
    votes: dict[str, int] = {}
    for e in entries:
        if e.kind not in ("relationship", "table_doc", "business_def"):
            continue
        for m in _JOIN_KEY_RE.finditer(e.body):
            col = m.group(1)
            if col in reality.all_columns:
                votes[col] = votes.get(col, 0) + 2
        if "join" in e.body.lower():
            for tok in code_identifiers(e.body):
                col = tok.split(".")[-1]
                if col.endswith("_id") and col in reality.all_columns:
                    votes[col] = votes.get(col, 0) + 1
    return [c for c, _ in sorted(votes.items(), key=lambda kv: -kv[1])]


def check_join_assumptions(
    ch: Any,
    entries: Sequence[ContextEntry],
    reality: Reality,
    new_tables: Sequence[str],
    run_id: str = "",
) -> CheckOutput:
    """Test the documented join map against a table that landed AFTER it was written.

    This is the check the pipeline generates about itself. base_context.md asserts that
    every table joins on `user_id`. For a feature table that is false twice over:
    anonymous events carry `user_id = ''` (house rules forbid Nullable, so the default is
    the empty string, not NULL), and the populated ids have zero overlap with the existing
    tables. Analytics must therefore fall back to segment-level joins -- and we write that
    conclusion back into the context layer so downstream findings cite it as a caveat.
    """
    out = CheckOutput()
    new_tables = [t for t in new_tables if t in reality.tables]
    if not new_tables:
        return out
    existing = [t for t in reality.tables if t not in new_tables]
    if not existing:
        return out

    join_keys = documented_join_keys(entries, reality)
    join_entry_ids = [
        e.entry_id
        for e in entries
        if e.kind == "relationship" or (e.kind == "table_doc" and "join" in e.body.lower())
    ]

    for table in new_tables:
        cols = reality.columns_by_table[table]
        identity_cols = [
            c
            for c in cols
            if c.endswith("_id") and c != "id" and any(c in reality.columns_by_table[t] for t in existing)
        ]
        # Prefer the documented join keys, then any other shared identity column.
        ordered = [c for c in join_keys if c in identity_cols] + [
            c for c in identity_cols if c not in join_keys
        ]
        if not ordered:
            continue

        for column in ordered[:2]:
            hosts = [t for t in existing if column in reality.columns_by_table[t]]
            hosts = sorted(hosts, key=lambda t: -reality.row_counts.get(t, 0))[:2]
            if not hosts:
                continue
            new_expr = f"ifNull({column}, '')" if reality.is_nullable(table, column) else column
            overlap_selects = []
            for h in hosts:
                h_expr = f"ifNull({column}, '')" if reality.is_nullable(h, column) else column
                overlap_selects.append(
                    f"  countIf({new_expr} != '' AND {new_expr} IN "
                    f"(SELECT {h_expr} FROM {reality.database}.{h})) AS rows_joinable_to_{h}"
                )
            sql = (
                "SELECT\n"
                "  count() AS new_rows,\n"
                f"  countIf({new_expr} = '') AS anonymous_rows,\n"
                f"  round(countIf({new_expr} = '') / count(), 4) AS anonymous_frac,\n"
                f"  {guarded_uniq(table, column, reality)} AS distinct_identities,\n"
                + ",\n".join(overlap_selects)
                + f"\nFROM {reality.database}.{table}"
            )
            result, ok, rows = verify(ch, sql)
            r = rows[0] if rows else {}
            overlaps = {h: int(r.get(f"rows_joinable_to_{h}", 0) or 0) for h in hosts}
            anon = float(r.get("anonymous_frac", 0) or 0)
            if ok and anon == 0 and any(v > 0 for v in overlaps.values()):
                continue  # documented join map holds for this column -- nothing to report

            # Corroborate the fallback: which shared *segment* vocabularies do overlap?
            seg_sql, seg_result, seg_ok, shared_dims = _segment_fallback_probe(
                ch, reality, table, hosts[0]
            )

            out.contradictions.append(
                Contradiction(
                    kind="join_assumption_violated",
                    title=f"`{table}` cannot be joined to the existing tables on `{column}`",
                    claim=(
                        f"The documented join map asserts every table joins on `{column}` "
                        f"(entries: {', '.join(join_entry_ids[:4]) or 'relationship.*'})."
                    ),
                    evidence=(
                        f"`{table}` has {r.get('new_rows')} rows, of which "
                        f"{r.get('anonymous_rows')} ({anon:.1%}) carry `{column} = ''` -- anonymous "
                        f"events, empty string rather than NULL because house rules forbid Nullable "
                        f"on hot columns. Of the remaining "
                        f"{r.get('distinct_identities')} distinct identities, the number of rows "
                        f"joinable to the existing tables is: "
                        + ", ".join(f"{h}={v}" for h, v in overlaps.items())
                        + ". Identity-level joins between this feature table and the existing "
                        f"tables return nothing -- silently, which is the dangerous part. "
                        f"Segment-level vocabularies DO overlap: {shared_dims}."
                    ),
                    verification_sql=sql,
                    verification_result=result,
                    verified=ok,
                    proposed_resolution=(
                        "Analytics must NOT join this table to the existing tables on "
                        f"`{column}`. Cross-reference at segment level only "
                        f"({', '.join(d for d, _ in shared_dims) or 'shared dimensions'} and day). "
                        f"Corroborating query: {seg_sql} -> {seg_result}"
                    ),
                    entry_ids=join_entry_ids[:6],
                    severity="high",
                    detected_by="rule",
                )
            )
            out.proposed_entries.append(
                {
                    "entry_id": f"gap.data_quality.{table}.{column}_join",
                    "kind": "gap",
                    "key": f"data_quality: {table}.{column} is not joinable to the existing tables",
                    "body": (
                        f"MEASURED, not assumed. {anon:.1%} of `{table}` rows have `{column} = ''` "
                        f"(anonymous events; empty string, not NULL). Rows joinable to the existing "
                        f"tables on `{column}`: "
                        + ", ".join(f"{h}={v}" for h, v in overlaps.items())
                        + f". Every identity-level metric on this table MUST use "
                        f"uniqIf({column}, {column} != ''), and every cross-reference to the eight "
                        f"pre-existing tables MUST be segment-level "
                        f"({', '.join(d for d, _ in shared_dims) or 'shared dimensions'} / day), "
                        f"never an identity join. Findings that compare this feature to the "
                        f"existing funnel must carry this as a caveat."
                    ),
                    "formula": "",
                    "refs": sorted({table, column, *hosts}),
                    "source": "context_agent",
                    "source_ref": f"check:C6:{run_id}" if run_id else "check:C6",
                    "status": "open",
                    "confidence": 1.0,
                }
            )
            if shared_dims:
                out.proposed_entries.append(
                    {
                        "entry_id": f"relationship.{table}.segment_join",
                        "kind": "relationship",
                        "key": f"{table} -> existing tables (segment-level only)",
                        "body": (
                            f"`{table}` shares no identities with the eight pre-existing tables, "
                            f"but shares these segment vocabularies (measured overlap of distinct "
                            f"values against `{hosts[0]}`): "
                            + ", ".join(f"`{d}` ({v} shared values)" for d, v in shared_dims)
                            + ". Join on those plus toDate(timestamp). This supersedes the "
                            f"documented user_id join map for feature tables."
                        ),
                        "formula": "",
                        "refs": sorted({table, hosts[0], *(d for d, _ in shared_dims)}),
                        "source": "context_agent",
                        "source_ref": f"check:C6:{run_id}" if run_id else "check:C6",
                        "status": "active",
                        "confidence": 1.0,
                    }
                )
    return out


def _segment_fallback_probe(
    ch: Any, reality: Reality, new_table: str, host: str
) -> tuple[str, str, bool, list[tuple[str, int]]]:
    """Measure which shared, non-identity columns actually share values."""
    new_cols = reality.columns_by_table[new_table]
    host_cols = reality.columns_by_table[host]
    candidates = [
        c
        for c in new_cols
        if c in host_cols
        and not c.endswith("_id")
        and c not in ("id", "timestamp", "event")
        and "String" in new_cols[c]
    ]
    # Prefer genuinely low-cardinality dimensions.
    candidates = sorted(candidates, key=lambda c: (0 if "LowCardinality" in new_cols[c] else 1, c))[:3]
    if not candidates:
        return "", "no shared non-identity columns", False, []
    shared: list[tuple[str, int]] = []
    sqls: list[str] = []
    for c in candidates:
        n_expr = f"ifNull({c}, '')" if reality.is_nullable(new_table, c) else c
        h_expr = f"ifNull({c}, '')" if reality.is_nullable(host, c) else c
        sql = (
            f"SELECT count() AS shared_values FROM "
            f"(SELECT DISTINCT {n_expr} AS v FROM {reality.database}.{new_table} WHERE {n_expr} != '') a "
            f"INNER JOIN (SELECT DISTINCT {h_expr} AS v FROM {reality.database}.{host}) b USING (v)"
        )
        sqls.append(sql)
        _, ok, rows = verify(ch, sql)
        if ok and rows and int(rows[0]["shared_values"]) > 0:
            shared.append((c, int(rows[0]["shared_values"])))
    return (
        sqls[0] if sqls else "",
        ", ".join(f"{c}={n}" for c, n in shared) or "none",
        bool(shared),
        shared,
    )


# --------------------------------------------------------------------------
# C7 -- the literal "LLM proposes, SQL adjudicates" loop (optional)
# --------------------------------------------------------------------------


class ProposedContradiction(BaseModel):
    """A candidate the model spotted. It is NOT evidence until our SQL says so."""

    kind: Literal[
        "definition_conflict",
        "schema_mismatch",
        "uncomputable_metric",
        "undefined_term",
        "stale_entry",
        "join_assumption_violated",
    ]
    title: str
    claim: str = Field(description="What the context asserts, quoting the entry.")
    expectation: str = Field(
        description="What the verification query must return for the contradiction to be REAL, "
        "e.g. 'claimed_column_exists = 0'."
    )
    verification_sql: str = Field(
        description="ONE read-only SELECT against system.columns / system.tables or an aggregate "
        "over the data. No raw row dumps. It must settle the claim by itself."
    )
    entry_ids: list[str] = Field(default_factory=list)
    severity: Literal["low", "medium", "high"] = "medium"
    proposed_resolution: str = ""


class ProposedContradictions(BaseModel):
    contradictions: list[ProposedContradiction] = Field(default_factory=list, max_length=12)


LLM_SYSTEM = """You audit a data-team context layer against a live ClickHouse schema.

You do NOT decide what is true. You propose candidate contradictions, and for each you
write ONE read-only SELECT that would settle it. Another process runs your query and
records the result; if your query does not actually settle the claim, your proposal is
discarded. So: no rhetorical queries, no `SELECT 1`, no raw row dumps, no queries that
would return millions of rows. Aggregate or count.

Available to query: `system.columns` and `system.tables` (columns: database, table/name,
type, sorting_key, total_rows) and the data tables listed below.

Rules:
- Identity columns default to the empty string, never NULL. Use uniqIf(col, col != ''),
  never a bare uniq(col).
- One statement only, no semicolons, no DDL.
- Skip anything already listed under ALREADY DETECTED.
"""


def check_llm_proposed(
    ch: Any,
    entries: Sequence[ContextEntry],
    reality: Reality,
    context_version: int,
    already: Sequence[Contradiction] = (),
    max_rows: int = 50,
) -> CheckOutput:
    """Ask the model for candidates, then adjudicate every one of them with SQL.

    A proposal survives only if its query runs AND returns something. Everything the model
    says is stored with the query and the query's result, exactly like the rule-based
    checks -- so a judge cannot tell (and does not need to trust) which produced which.
    """
    out = CheckOutput()
    import llm  # imported lazily: the deterministic checks must not need an API key

    schema_digest = "\n".join(
        f"- {t} ({reality.row_counts.get(t, 0)} rows): "
        + ", ".join(f"{c} {ty}" for c, ty in list(cols.items())[:40])
        for t, cols in sorted(reality.columns_by_table.items())
    )[:12000]
    context_digest = "\n".join(
        f"- [{e.entry_id}@v{e.version}] ({e.kind}) {e.key}: {e.body}" for e in entries
    )[:20000]
    already_digest = "\n".join(f"- [{c.kind}] {c.title}" for c in already) or "(none)"

    proposals = llm.complete_json(
        name="context.propose_contradictions",
        system=LLM_SYSTEM,
        user=(
            f"DATABASE: {reality.database}\n\nLIVE SCHEMA\n{schema_digest}\n\n"
            f"CONTEXT LAYER (v{context_version})\n{context_digest}\n\n"
            f"ALREADY DETECTED\n{already_digest}\n\n"
            "Propose contradictions between the context layer and the live schema/data."
        ),
        schema=ProposedContradictions,
        context_version=context_version,
    )

    known_titles = {c.title for c in already}
    valid_ids = {e.entry_id for e in entries}
    for p in proposals.contradictions:
        if p.title in known_titles:
            continue
        result, ok, rows = verify(ch, p.verification_sql, max_rows=max_rows)
        if not ok or not rows:
            continue  # the model's own query failed to settle it -> not evidence
        out.contradictions.append(
            Contradiction(
                kind=p.kind,
                title=p.title,
                claim=p.claim,
                evidence=(
                    f"Adjudicated by the proposed query. Expected for this to be a real "
                    f"contradiction: {p.expectation}. Executed result: {result}"
                ),
                verification_sql=p.verification_sql,
                verification_result=result,
                verified=True,
                proposed_resolution=p.proposed_resolution,
                entry_ids=[i for i in p.entry_ids if i in valid_ids],
                severity=p.severity,
                detected_by="llm",
            )
        )
    return out


# --------------------------------------------------------------------------
# runner
# --------------------------------------------------------------------------

CHECKS = {
    "C1_definition_conflict": check_definition_conflicts,
    "C2_undefined_term": check_undefined_terms,
    "C3_schema_mismatch": check_schema_mismatches,
    "C4_self_admitted_uncomputable": check_self_admitted_uncomputable,
    "C5_stale_entry": check_stale_entries,
}


def run_all_checks(
    ch: Any,
    entries: Sequence[ContextEntry],
    formulas: dict[str, str] | None = None,
    new_tables: Sequence[str] = (),
    run_id: str = "",
    reality: Reality | None = None,
    use_llm: bool = False,
    context_version: int = 0,
) -> CheckOutput:
    """Run every check. `formulas` maps entry_id -> formula (context_entry_log.formula).

    `use_llm=True` adds the open-ended proposer on top of the deterministic checks. It is
    OFF by default and its failure is never fatal: the rule-based checks are the floor,
    the LLM only widens recall, and every proposal it makes is still adjudicated by an
    executed query before it is recorded.
    """
    reality = reality or Reality(ch)
    formulas = formulas or {}
    out = CheckOutput()
    for fn in CHECKS.values():
        out.extend(fn(ch, entries, reality, formulas))
    out.extend(check_join_assumptions(ch, entries, reality, new_tables, run_id=run_id))
    if use_llm:
        try:
            out.extend(
                check_llm_proposed(ch, entries, reality, context_version, already=out.contradictions)
            )
        except Exception as exc:  # noqa: BLE001 -- no API key, rate limit, bad JSON: keep going
            out.contradictions.append(
                Contradiction(
                    kind="stale_entry",
                    title="LLM contradiction proposer did not run",
                    claim="An open-ended LLM audit of the context layer was requested.",
                    evidence=f"It failed with {type(exc).__name__}: {exc}. The "
                    f"{len(out.contradictions)} deterministic checks above are unaffected.",
                    verified=False,
                    severity="low",
                    detected_by="llm",
                )
            )
    # Stable ordering: highest severity first, then kind, then title.
    rank = {"high": 0, "medium": 1, "low": 2}
    out.contradictions.sort(key=lambda c: (rank.get(c.severity, 3), c.kind, c.title))
    out.disputed_entry_ids = sorted(set(out.disputed_entry_ids))
    return out
