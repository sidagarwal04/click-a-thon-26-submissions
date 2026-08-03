"""Correctness gate for a proposed schema — the second gate before `executed`
(perf_tool proves fast, this proves correct), and the one that makes the suite
cumulative: every proposal's smoke tests get persisted in `agent_meta.test_cases`
and re-run on every subsequent proposal, so a rework round can't silently break a
table built earlier.

Reuses perf_tool's scratch-table pattern for the pre-execution checks — never
touches production (`atlys.*`) tables until the caller has already decided to execute.
"""
from __future__ import annotations

import json
import re
import time
import uuid
from dataclasses import dataclass, field

from agent_meta.db import get_client
from perf_tool import parse_column_names


@dataclass
class TestResult:
    description: str
    test_type: str
    query: str
    passed: bool
    actual: str
    duration_ms: float


@dataclass
class TestSuiteResult:
    passed: bool
    results: list[TestResult] = field(default_factory=list)


_AS_QUERY_RE = re.compile(r"\bAS\s+(SELECT|WITH)\b", re.IGNORECASE)


def _extract_select(mv_ddl: str) -> str:
    """Pulls the query portion out of a `CREATE MATERIALIZED VIEW ... AS SELECT/WITH
    ...` statement so it can be run standalone. Must be paren-depth-aware: a naive
    first-match search breaks on CTEs (`WITH standard AS (SELECT ...)`), where
    "AS (SELECT" inside the CTE list matches before the real top-level "AS SELECT"/
    "AS WITH" boundary. Real boundary is the first `AS SELECT`/`AS WITH` at paren
    depth 0 — a CTE's `name AS (` is always followed by `(`, never directly by the
    SELECT/WITH keyword, so this disambiguates correctly."""
    for m in _AS_QUERY_RE.finditer(mv_ddl):
        prefix = mv_ddl[: m.start()]
        if prefix.count("(") == prefix.count(")"):
            return mv_ddl[m.start(1):]
    return mv_ddl


_CREATE_OBJECT_RE = re.compile(
    r"\bCREATE\s+(?:TABLE|MATERIALIZED\s+VIEW)\s+(?:IF\s+NOT\s+EXISTS\s+)?([a-zA-Z0-9_.]+)", re.IGNORECASE
)


def _created_object_name(stmt: str) -> str | None:
    """Name of the table/view a CREATE statement declares (e.g. 'atlys.my_view' or
    'my_view'), or None if this statement doesn't create one (rare — a plain query)."""
    m = _CREATE_OBJECT_RE.search(stmt)
    return m.group(1) if m else None


def _substitute_names(sql: str, mapping: dict[str, str]) -> str:
    """Replaces real table/MV names with their scratch equivalents in ONE pass,
    longest-name-first, so a scratch name that happens to contain a shorter real
    name as a substring (e.g. scratch table `..._events__testharness__abc123`
    containing the real name `events`) never gets re-matched and double-substituted.
    Matches `db.name` and bare `name` forms, on word boundaries only."""
    if not mapping:
        return sql
    ordered = sorted(mapping.items(), key=lambda kv: -len(kv[0]))
    pattern = re.compile(
        r"(?:\batlys\.)?\b(" + "|".join(re.escape(name) for name, _ in ordered) + r")\b"
    )
    return pattern.sub(lambda m: mapping[m.group(1)], sql)


def build_smoke_queries(table_name: str, columns_ddl: str, pm_question_queries: list[tuple[str, str]] | None = None) -> list[tuple[str, str]]:
    """Generic smoke queries every table gets, plus any spec-specific ones the
    caller derived from the spec's "questions the PM will ask" section."""
    cols = set(parse_column_names(columns_ddl))
    queries = [("row count is non-zero", f"SELECT count() FROM {{table}}")]
    if "user_id" in cols:
        queries.append(("distinct users countable", f"SELECT uniqExact(user_id) FROM {{table}}"))
    if "device_type" in cols:
        queries.append(("segment breakdown by device_type", f"SELECT device_type, count() FROM {{table}} GROUP BY device_type"))
    if pm_question_queries:
        queries.extend(pm_question_queries)
    return queries


def run_new_table_tests(
    table_name: str,
    columns_ddl: str,
    ordering_key: str,
    partition_key: str,
    sample_rows: list[dict],
    smoke_queries: list[tuple[str, str]],
    materialized_views: list[dict] | None = None,
    scratch_db: str = "atlys_staging",
    ddl_only: bool = False,
) -> TestSuiteResult:
    """`ddl_only=True`: skip insert_integrity, query_smoke, and each MV's query-logic
    check — just create the base table (empty) and run every MV's real CREATE
    statement(s) against scratch. This is a fast, data-free syntax/type check meant
    to run BEFORE the reviewer sees the proposal at all, so a broken MV (e.g.
    Nullable-in-ORDER-BY) triggers an immediate, cheap rework round instead of first
    burning a reviewer LLM call and a full data-insert test cycle on a proposal that
    was never going to execute. The full (ddl_only=False) run still happens after
    review, unchanged — this doesn't replace that, it just catches the cheap,
    mechanical class of failure earlier."""
    # database="atlys", not "default": MVs legitimately JOIN against existing real
    # tables using bare (unqualified) names, assuming the connection's default
    # database is atlys — matches how the agent reasons about it via list_tables.
    # A "default" client would fail to resolve those bare references even though
    # the SQL itself is completely correct. Caught by a real test failure, not
    # anticipated — see the express_checkout_events run that hit exactly this.
    client = get_client(database="atlys")
    client.command(f"CREATE DATABASE IF NOT EXISTS {scratch_db}")
    scratch_table = f"{scratch_db}.{table_name}__testharness__{uuid.uuid4().hex[:6]}"
    results: list[TestResult] = []

    # partition_key may be "" (orchestrator/pipeline.py normalizes an empty/prose
    # partition_key to "" rather than a real expression) -- a bare "PARTITION BY "
    # with nothing after it makes ClickHouse read the next token (the literal
    # word ORDER) as the partition expression and choke on the BY that follows.
    partition_clause = f"PARTITION BY {partition_key} " if partition_key else ""
    try:
        client.command(f"DROP TABLE IF EXISTS {scratch_table}")
        client.command(
            f"CREATE TABLE {scratch_table} ({columns_ddl}) "
            f"ENGINE = MergeTree {partition_clause}ORDER BY {ordering_key} "
            f"SETTINGS allow_nullable_key = 1"
        )

        if not ddl_only:
            # --- insert_integrity ---
            t0 = time.perf_counter()
            body = "\n".join(json.dumps(r, default=str) for r in sample_rows).encode("utf-8")
            client.raw_insert(
                scratch_table, insert_block=body, fmt="JSONEachRow",
                settings={"input_format_skip_unknown_fields": 1},
            )
            actual_count = client.query(f"SELECT count() FROM {scratch_table}").result_rows[0][0]
            elapsed = (time.perf_counter() - t0) * 1000
            passed = actual_count == len(sample_rows)
            results.append(TestResult(
                description=f"insert integrity: {len(sample_rows)} rows in -> {actual_count} rows landed",
                test_type="insert_integrity", query=f"INSERT INTO {table_name} ... ({len(sample_rows)} rows)",
                passed=passed, actual=f"{actual_count} rows", duration_ms=round(elapsed, 2),
            ))

            # --- query_smoke ---
            for description, query_template in smoke_queries:
                q = query_template.format(table=scratch_table)
                t0 = time.perf_counter()
                try:
                    r = client.query(q)
                    elapsed = (time.perf_counter() - t0) * 1000
                    results.append(TestResult(
                        description=description, test_type="query_smoke", query=q,
                        passed=True, actual=f"ok, {r.row_count} rows returned", duration_ms=round(elapsed, 2),
                    ))
                except Exception as e:
                    elapsed = (time.perf_counter() - t0) * 1000
                    results.append(TestResult(
                        description=description, test_type="query_smoke", query=q,
                        passed=False, actual=f"ERROR: {e}", duration_ms=round(elapsed, 2),
                    ))

        # --- mv_integrity: TWO checks per MV, both against scratch, before anything
        # touches production.
        #
        # (1) DDL check — run the agent's ACTUAL CREATE TABLE/CREATE MATERIALIZED
        #     VIEW statement(s) verbatim (name-substituted only), not a synthetic
        #     stand-in. This matters: an earlier version of this function tested
        #     the MV's query logic by re-wrapping it in our OWN `CREATE TABLE ...
        #     ENGINE = MergeTree ORDER BY tuple() AS <select>` — which silently
        #     discarded whatever ENGINE/ORDER BY the agent actually declared. That
        #     let a Nullable-column-in-ORDER-BY bug slip through test_harness
        #     completely and only surface at real execution, burning a full
        #     rework round for something scratch testing should have caught in
        #     round 1. Found by inspecting a real trace, not anticipated.
        # (2) Query-logic check — the extracted SELECT, run standalone. Still
        #     needed separately: ClickHouse materialized views only process NEW
        #     inserts after creation (no POPULATE here), so querying a freshly
        #     created MV's target table would show 0 rows regardless of whether
        #     the query logic is actually correct — this checks the logic itself.
        #
        # MVs are processed in order; each one's real created object(s) are
        # registered in name_map so a later MV that joins against an earlier one
        # (a legitimate chained-views pattern) resolves for real, not "table not
        # found". Substitution is name-mapping-based, not naive sequential
        # .replace (which double-substitutes when a scratch name embeds a real
        # name as a substring — a real bug caught by inspecting a live failure).
        mv_scratch_tables: list[str] = []
        name_map = {table_name: scratch_table}
        try:
            for mv in materialized_views or []:
                mv_name = mv.get("name", f"mv_{uuid.uuid4().hex[:6]}")
                local_map = dict(name_map)
                ddl_ok = True

                for raw_stmt in mv["ddl"].split(";"):
                    stmt = raw_stmt.strip()
                    if not stmt:
                        continue
                    created_name = _created_object_name(stmt)
                    scratch_obj = None
                    if created_name:
                        bare = created_name.split(".")[-1]
                        scratch_obj = f"{scratch_db}.{bare}__testharness__{uuid.uuid4().hex[:6]}"
                        local_map[bare] = scratch_obj
                    test_stmt = _substitute_names(stmt, local_map)
                    t0 = time.perf_counter()
                    try:
                        client.command(test_stmt)
                        elapsed = (time.perf_counter() - t0) * 1000
                        results.append(TestResult(
                            description=f"MV '{mv_name}' DDL: {created_name or 'statement'}",
                            test_type="mv_integrity", query=test_stmt,
                            passed=True, actual="created ok in scratch", duration_ms=round(elapsed, 2),
                        ))
                        if scratch_obj:
                            mv_scratch_tables.append(scratch_obj)
                    except Exception as e:
                        elapsed = (time.perf_counter() - t0) * 1000
                        results.append(TestResult(
                            description=f"MV '{mv_name}' DDL: {created_name or 'statement'}",
                            test_type="mv_integrity", query=test_stmt,
                            passed=False, actual=f"ERROR: {e}", duration_ms=round(elapsed, 2),
                        ))
                        ddl_ok = False
                        break  # later statements in this MV likely depend on this one

                if not ddl_ok:
                    continue  # don't bother query-testing a MV whose DDL doesn't even create

                if ddl_only:
                    continue  # DDL syntax is all this mode checks — scratch base table has no
                    # data yet, so a query-logic check here would only prove the scratch table
                    # is empty, not that the query logic is correct.

                # First created object in this MV's own statements is its
                # queryable data table in the common `CREATE TABLE target; CREATE
                # MATERIALIZED VIEW ... TO target ...` pattern; for a single bare
                # `CREATE MATERIALIZED VIEW ... AS SELECT` it's the only object.
                mv_data_names = {k: v for k, v in local_map.items() if k not in name_map}
                if mv_data_names:
                    first_key = next(iter(mv_data_names))
                    name_map[mv_name] = mv_data_names[first_key]

                select_sql = _substitute_names(_extract_select(mv["ddl"]), name_map)
                # Wrapped in `SELECT count() FROM (...)` rather than run raw: MVs that
                # aggregate with *State combinators (minState, argMinState, etc. — the
                # standard pattern for a mergeable rollup) return AggregateFunction(...)
                # columns, which clickhouse-connect cannot deserialize client-side (it's
                # an opaque binary state meant to be read via -Merge, not fetched raw).
                # This check only needs to confirm the query's joins/filters/expressions
                # execute and produce rows — count() sidesteps per-column deserialization
                # entirely while still exercising the real logic. Found via a live
                # failure: "AggregateFunction(min, DateTime) deserialization not
                # supported" on an otherwise-correct funnel MV.
                count_sql = f"SELECT count() FROM ({select_sql})"
                t0 = time.perf_counter()
                try:
                    r = client.query(count_sql)
                    row_count = r.result_rows[0][0] if r.result_rows else 0
                    elapsed = (time.perf_counter() - t0) * 1000
                    results.append(TestResult(
                        description=f"MV '{mv_name}' query logic ({mv.get('answers_pm_question', '')})",
                        test_type="mv_integrity", query=select_sql,
                        passed=True, actual=f"ok, {row_count} rows produced", duration_ms=round(elapsed, 2),
                    ))
                except Exception as e:
                    elapsed = (time.perf_counter() - t0) * 1000
                    results.append(TestResult(
                        description=f"MV '{mv_name}' query logic ({mv.get('answers_pm_question', '')})",
                        test_type="mv_integrity", query=select_sql,
                        passed=False, actual=f"ERROR: {e}", duration_ms=round(elapsed, 2),
                    ))
        finally:
            # Best-effort cleanup: DROP TABLE and DROP VIEW are not interchangeable
            # no-ops in ClickHouse the way IF EXISTS might suggest -- IF EXISTS only
            # suppresses "doesn't exist", not "exists but is the wrong kind" (e.g.
            # `DROP VIEW IF EXISTS <a real table>` raises INCORRECT_QUERY, it
            # doesn't silently skip). We don't reliably know which kind each scratch
            # object is (a 2-statement MV pattern creates one of each), so try both,
            # but a cleanup failure must never crash a run whose real results are
            # already computed -- this is our own bug, not something the LLM's
            # proposal did wrong, and shouldn't cost anyone a revision or a crash.
            for t in mv_scratch_tables:
                for drop_stmt in (f"DROP TABLE IF EXISTS {t}", f"DROP VIEW IF EXISTS {t}"):
                    try:
                        client.command(drop_stmt)
                    except Exception:
                        pass
    finally:
        try:
            client.command(f"DROP TABLE IF EXISTS {scratch_table}")
        except Exception:
            pass

    return TestSuiteResult(passed=all(r.passed for r in results), results=results)


def register_tests(proposal_id: str, table_name: str, smoke_queries: list[tuple[str, str]]):
    """Persist this proposal's smoke tests so future proposals' regression runs include
    them. Query is stored with the real table_name substituted (not the scratch name),
    since after execution these run against the production `atlys.{table_name}`."""
    client = get_client(database="agent_meta")
    rows = [
        [str(uuid.uuid4()), proposal_id, table_name, "query_smoke",
         q.format(table=f"atlys.{table_name}"), "no_error", description]
        for description, q in smoke_queries
    ]
    client.insert(
        "test_cases", rows,
        column_names=["test_id", "introduced_by_proposal_id", "table_name", "test_type", "query", "expected", "description"],
    )


def run_regression_suite(proposal_id: str, trace_url: str = "") -> TestSuiteResult:
    """Re-run every accumulated test in agent_meta.test_cases (across every table
    instrumented so far, not just the one just added) against the current, real state
    of `atlys`. This is what catches a rework round breaking something built earlier."""
    meta_client = get_client(database="agent_meta")
    data_client = get_client(database="atlys")
    test_cases = meta_client.query(
        "SELECT test_id, table_name, query, expected, description FROM test_cases"
    ).result_rows

    results: list[TestResult] = []
    run_rows = []
    for test_id, table_name, query, expected, description in test_cases:
        t0 = time.perf_counter()
        try:
            data_client.query(query)
            elapsed = (time.perf_counter() - t0) * 1000
            passed, actual = True, "ok"
        except Exception as e:
            elapsed = (time.perf_counter() - t0) * 1000
            passed, actual = False, f"ERROR: {e}"
        results.append(TestResult(description, "query_smoke", query, passed, actual, round(elapsed, 2)))
        run_rows.append([str(uuid.uuid4()), proposal_id, test_id, 1 if passed else 0, actual, int(elapsed), trace_url])

    if run_rows:
        meta_client.insert(
            "test_runs", run_rows,
            column_names=["run_id", "proposal_id", "test_id", "passed", "actual", "duration_ms", "trace_url"],
        )

    return TestSuiteResult(passed=all(r.passed for r in results), results=results)
