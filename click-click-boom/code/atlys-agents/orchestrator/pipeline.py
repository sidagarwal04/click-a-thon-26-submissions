"""The centerpiece: drives one spec through
drafted -> pending_review -> [needs_rework loop, capped] -> approved
  -> [test harness] -> executed -> [context commit]
as a single Langfuse trace with nested spans.

Design rule, consistent throughout: this module owns all deterministic work
(ClickHouse reads/writes, perf_tool, test_harness, the state machine, the revision
cap) and calls the 4 LibreChat agents only for the reasoning steps, handing each one
pre-computed evidence as input rather than trusting it to fetch/compute things itself.
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import time
import uuid
from collections import Counter

from agent_meta.db import get_client
from orchestrator.agent_io import AgentOutputError, _call_json_agent, _extract_json
from perf_tool import AllCandidatesFailedError, Candidate, run_perf_test
from test_harness import build_smoke_queries, register_tests, run_new_table_tests, run_regression_suite
from tracing import traced_run

# Same directory mcp_servers/data_tools_server.py uses for run_query's scratch
# offload (both processes run on the host, not in LibreChat's Docker container, so
# they share this filesystem path directly) — sample_events gets written here
# instead of embedded inline in the propose payload. Measured: 150 sample events
# serialize to ~66K characters (~16-20K tokens), which used to get resent verbatim
# on every propose call including every rework round, dwarfing everything else in
# the payload combined. The proposer now reads it via grep_scratch/read_scratch or
# execute_python (pandas) instead — same lean-tool pattern already used for large
# run_query results, applied to the proposer's own input this time.
SCRATCH_DIR = pathlib.Path(__file__).resolve().parent.parent / ".tool_scratch"
SCRATCH_DIR.mkdir(exist_ok=True)

# Shared budget across review rework, test-harness failures, AND execute failures
# (all three now feed back into the same propose->review->test->execute loop) —
# higher than a review-only cap would need, since it now has to cover more failure
# modes with the same total attempts.
MAX_REVISIONS = 15


# AgentOutputError, _extract_json, _call_json_agent now live in
# orchestrator/agent_io.py so analytics_agent.py can import them without creating
# a circular dependency (pipeline lazily imports analytics_agent at call time).


def _get_nested(d: dict, dotted_key: str):
    cur = d
    for part in dotted_key.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


# Matches a bare column ("event_date") or a single function call around one
# arg-list ("toYYYYMM(event_date)") -- deliberately narrow, not a general SQL
# parser. A real run had partition_key come back as "" or as prose ("No
# partition initially; use event_date for filtering") instead of a valid
# expression -- both are schema-valid strings (partition_key is a required but
# otherwise unconstrained free-form field) but neither is valid DDL. Rather
# than trying to fix up prose into SQL, treat anything that doesn't match this
# shape the same as "no partitioning wanted" -- always safe in ClickHouse,
# unlike emitting `PARTITION BY <empty-or-garbage>` which is a guaranteed
# syntax error.
_VALID_PARTITION_EXPR = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\([^()]*\))?$")


def _normalize_partition_key(partition_key) -> str:
    pk = (partition_key or "").strip()
    return pk if _VALID_PARTITION_EXPR.match(pk) else ""


def _partition_clause(partition_key: str) -> str:
    """`PARTITION BY <key> ` when there's a real key, else "" -- an empty
    partition_key must not produce a bare `PARTITION BY ` (ClickHouse then reads
    the next token, usually the literal word ORDER, as the partition
    expression and chokes on the BY that follows it)."""
    return f"PARTITION BY {partition_key} " if partition_key else ""


def _column_mapping_to_dict(column_mapping) -> dict[str, str]:
    """agent_runner/schemas.py's strict json_schema reshapes column_mapping from
    {raw_field: column_name} to [{raw_field, column_name}, ...] -- strict mode can't
    express a dynamic-key object. Converts back to the dict every consumer here
    still expects. Also accepts a plain dict for robustness (e.g. if an agent
    without a strict schema ever supplies this field)."""
    if isinstance(column_mapping, dict):
        return column_mapping
    return {entry["raw_field"]: entry["column_name"] for entry in column_mapping}


def _flatten_events(events: list[dict], column_mapping: dict[str, str]) -> list[dict]:
    """Raw events can have nested objects (e.g. Express Checkout's `payment.amount`).
    column_mapping (from the proposer) tells us how to flatten them into the columns
    the DDL actually declares. Top-level scalar fields also pass through unchanged so
    envelope columns (id, timestamp, user_id, ...) work even if the agent didn't
    enumerate every single one in column_mapping — unmapped/unused keys are silently
    dropped by ClickHouse's input_format_skip_unknown_fields on insert.

    Any raw-value cleanup a join key needs (encoding, casing, format — see
    INSTRUMENTATION_PROPOSER's join-key-hygiene rule) is NOT done here: the proposer
    declares it as a `MATERIALIZED` column in columns_ddl using ordinary ClickHouse SQL
    functions, and ClickHouse computes it itself from the raw ingested column at insert
    time — identically for perf test, test harness, and the real production load,
    with no separate Python-side transform step to keep in sync."""
    flat = []
    for e in events:
        row = {k: v for k, v in e.items() if not isinstance(v, dict)}
        for raw_key, col_name in column_mapping.items():
            row[col_name] = _get_nested(e, raw_key)
        flat.append(row)
    return flat


def get_current_context() -> list[dict]:
    client = get_client(database="agent_meta")
    rows = client.query("SELECT section, content, confidence FROM current_context ORDER BY section").result_rows
    return [{"section": s, "content": json.loads(c), "confidence": conf} for s, c, conf in rows]


def _write_proposal(client, **kwargs) -> str:
    proposal_id = str(uuid.uuid4())
    row = {
        "proposal_id": proposal_id, "parent_proposal_id": None, "revision": 0,
        "spec_name": "", "table_name": "", "ddl": "", "ordering_key": "", "partition_key": "",
        "materialized_views": [], "perf_report": "", "confidence": 0.0, "rationale": "",
        "status": "drafted", "trace_url": "",
        **kwargs,
    }
    cols = list(row.keys())
    client.insert("schema_proposals", [[row[c] for c in cols]], column_names=cols)
    return proposal_id


def _update_proposal_status(client, proposal_id: str, **fields):
    # append-only table: write a fresh row carrying the new status forward.
    prior = client.query(
        "SELECT parent_proposal_id, revision, spec_name, table_name, ddl, ordering_key, partition_key, "
        "materialized_views, perf_report, confidence, rationale, status, trace_url "
        "FROM schema_proposals WHERE proposal_id = %(pid)s ORDER BY ts DESC LIMIT 1",
        parameters={"pid": proposal_id},
    ).result_rows[0]
    keys = ["parent_proposal_id", "revision", "spec_name", "table_name", "ddl", "ordering_key", "partition_key",
            "materialized_views", "perf_report", "confidence", "rationale", "status", "trace_url"]
    row = dict(zip(keys, prior))
    row.update(fields)
    row["proposal_id"] = proposal_id
    cols = list(row.keys())
    client.insert("schema_proposals", [[row[c] for c in cols]], column_names=cols)


_CREATE_OBJECT_RE = re.compile(
    r"CREATE\s+(?:TABLE|MATERIALIZED\s+VIEW)\s+(?:IF\s+NOT\s+EXISTS\s+)?([a-zA-Z0-9_.]+)",
    re.IGNORECASE,
)


def _mv_object_names(mv: dict) -> list[str]:
    """Every real table/view name a materialized view's own DDL creates --
    `mv['name']` alone misses a `TO <backing_table>` target's backing table,
    which is its OWN separate `CREATE TABLE` statement inside `mv['ddl']`
    (see pipeline.py's execute step: "Some MVs are 2 statements: a backing
    table ... plus the CREATE MATERIALIZED VIEW itself"). Parses the DDL
    directly rather than trusting `name` alone, so cleanup (here and the
    execute-error handler) actually removes everything a real MV created,
    not just the view object -- confirmed missing the backing table on a
    real TO-target MV before this fix."""
    names = {n.split(".")[-1] for n in _CREATE_OBJECT_RE.findall(mv.get("ddl", ""))}
    if mv.get("name"):
        names.add(mv["name"])
    return sorted(names)


def _drop_mv_objects(data_client, mv: dict) -> list[str]:
    """DROP TABLE and DROP VIEW are both harmless no-ops (IF EXISTS) against
    whichever kind an object actually isn't -- cheaper than tracking which
    of a backing table vs. the view itself each name refers to."""
    names = _mv_object_names(mv)
    for name in names:
        data_client.command(f"DROP TABLE IF EXISTS atlys.{name}")
        data_client.command(f"DROP VIEW IF EXISTS atlys.{name}")
    return names


def _cleanup_previous_execution(meta_client, data_client, run, spec_name: str) -> None:
    """Drops whatever a PRIOR successful ingest_spec() run for this exact
    spec_name left behind in atlys, before this run does any new work.

    Without this, re-ingesting the same spec was actively destructive: the
    base table DDL is `CREATE TABLE <name> (...)` with no IF NOT EXISTS, so
    if the new proposal reuses the same table_name (likely -- it's derived
    from the same spec), CREATE fails with "table already exists". That
    failure was only ever handled as a generic execute-error: the except
    block's cleanup unconditionally does `DROP TABLE IF EXISTS
    atlys.<table_name>` for its OWN failed attempt, which in this case is
    actually the PREVIOUS run's real table -- dropped with nothing
    re-created in its place if the revision budget was already exhausted.
    Real data loss as a side effect of error handling, not a deliberate
    "replace old data" step.

    Looks at every row this spec_name has ever reached status='executed'
    with, not just the latest, so an earlier run that used a DIFFERENT
    table_name doesn't leave an orphaned table sitting in atlys forever."""
    rows = meta_client.query(
        "SELECT DISTINCT table_name, materialized_views FROM schema_proposals "
        "WHERE spec_name = %(spec)s AND status = 'executed'",
        parameters={"spec": spec_name},
    ).result_rows
    if not rows:
        return
    dropped = []
    for table_name, mv_json_list in rows:
        if table_name:
            data_client.command(f"DROP TABLE IF EXISTS atlys.{table_name}")
            dropped.append(table_name)
        for mv_raw in mv_json_list:
            try:
                mv = json.loads(mv_raw) if isinstance(mv_raw, str) else mv_raw
            except json.JSONDecodeError:
                continue
            dropped.extend(_drop_mv_objects(data_client, mv or {}))
    if dropped:
        run.log(step="cleanup_previous_execution", input={"spec_name": spec_name}, output={"dropped": dropped})


def _write_review(client, proposal_id: str, revision: int, review: dict, sections_used: list[str], trace_url: str) -> str:
    review_id = str(uuid.uuid4())
    client.insert(
        "schema_reviews",
        [[review_id, proposal_id, revision, review["verdict"], json.dumps(review["findings"]),
          sections_used, float(review.get("reviewer_confidence", 0.5)), trace_url]],
        column_names=["review_id", "proposal_id", "revision", "verdict", "findings",
                       "context_sections_used", "reviewer_confidence", "trace_url"],
    )
    return review_id


def _as_text(value) -> str:
    """The agent's JSON schema says `before`/`diff_summary`/`rationale` are strings,
    but a model occasionally hands back a nested object instead (e.g. `before` as a
    dict describing the prior section rather than a string summary of it). Coerce
    defensively rather than letting one malformed field crash the whole write."""
    if value is None:
        return ""
    return value if isinstance(value, str) else json.dumps(value)


def _write_context_sections(client, sections: list[dict], trace_url: str):
    rows = []
    for s in sections:
        after_json = json.dumps({k: s.get(k) for k in ("title", "summary", "body", "fields", "sources")})
        rows.append([
            str(uuid.uuid4()), s["section"], _as_text(s.get("before", "")), after_json,
            _as_text(s.get("diff_summary", "")), _as_text(s.get("rationale", "")), "chronicle",
            float(s.get("confidence", 0.7)), trace_url,
        ])
    if rows:
        client.insert(
            "context_versions", rows,
            column_names=["version_id", "section", "before", "after", "diff_summary", "rationale", "trigger", "confidence", "trace_url"],
        )


def _build_perf_query_patterns(columns_ddl: str) -> list[str]:
    from perf_tool import parse_column_names
    cols = set(parse_column_names(columns_ddl))
    patterns = ["SELECT count() FROM {table}"]
    if "user_id" in cols:
        patterns.append("SELECT uniqExact(user_id) FROM {table}")
    for candidate_col in ("event_type", "device_type"):
        if candidate_col in cols:
            patterns.append(f"SELECT {candidate_col}, count() FROM {{table}} GROUP BY {candidate_col}")
            break
    return patterns


def _record_findings(history: list[dict], new_findings: list[dict], round_num: int) -> list[dict]:
    """Tags new findings with the round they surfaced in and appends to the running
    history (in place), returning it for convenience at the call site."""
    for f in new_findings:
        history.append({**f, "found_in_round": round_num})
    return history


# Cap on how many accumulated findings get sent to the proposer, most-recent-first —
# a safety bound on finding_history's growth (measured: 3.3K chars round 1 -> 9.5K
# chars round 4 on a real run). Small next to the sample_events fix below, but
# unbounded growth across a long rework chain is still worth capping cheaply.
MAX_FINDINGS_IN_PAYLOAD = 8


def _write_sample_scratch_file(sample_events: list[dict]) -> dict:
    """Writes sample_events as NDJSON to the shared scratch dir instead of embedding
    them inline — same offload pattern data_tools_server.py already uses for large
    run_query results, applied here to the proposer's own input. Returns a small
    pointer object (filename + counts) that costs a few hundred chars instead of the
    ~66K chars 150 raw events serialize to. execute_python's subprocess runs with
    cwd=SCRATCH_DIR (see mcp_servers/data_tools_server.py), so the proposer can do
    `pd.read_json('<filename>', lines=True)` with just the bare filename."""
    filename = f"sample_events_{uuid.uuid4().hex[:8]}.ndjson"
    (SCRATCH_DIR / filename).write_text(
        "\n".join(json.dumps(e, default=str) for e in sample_events)
    )
    counts = Counter(e.get("event", "unknown") for e in sample_events)
    return {
        "scratch_file": filename,
        "n_events": len(sample_events),
        "event_type_counts": dict(counts),
    }


def _propose(
    run, spec_name: str, spec_markdown: str, sample_scratch_info: dict,
    prior_findings: list[dict] | None, previous_draft: dict | None,
    resume_from: str | None = None,
) -> tuple[dict, str | None]:
    # sample_scratch_info is a small pointer (filename + counts), never the raw
    # events — computed once in ingest_spec via _write_sample_scratch_file, same
    # every round. Measured: 150 raw events serialize to ~66K characters (~16-20K
    # tokens); embedding that inline on every propose call used to dwarf everything
    # else in the payload combined. The proposer inspects the scratch file on demand
    # via grep_scratch/read_scratch or execute_python (pandas) instead — same
    # lean-tool pattern as any other large tool result, applied to the agent's own
    # input this time.
    payload = {"spec_markdown": spec_markdown, "sample_events": sample_scratch_info}
    if prior_findings:
        # Sent explicitly even when resuming (resume_from) the proposer's own
        # conversation: prior_findings is genuinely NEW information (the
        # reviewer's critique, not something the proposer already knows), and
        # previous_draft is a concrete, unambiguous anchor for "the actual
        # previous DDL/MVs" alongside whatever it recalls from its own
        # conversation history — belt and suspenders, cheap next to the
        # revision-quality risk of relying on recall alone.
        payload["revise_to_address"] = prior_findings[-MAX_FINDINGS_IN_PAYLOAD:]
        payload["previous_attempt"] = previous_draft
    result, r = _call_json_agent(
        "instrumentation_proposer", payload, run, "propose",
        required_keys=[
            "table_name", "columns_ddl", "ordering_key_candidates", "column_mapping",
            "materialized_views", "confidence", "rationale",
        ],
        reasoning_fn=lambda parsed: parsed.get("rationale"),
        resume_from=resume_from,
        spec_name=spec_name,
    )
    return result, r.response_id


def _review(run, proposal: dict, resume_from: str | None = None) -> tuple[dict, str | None]:
    payload = {"proposal": proposal}

    def _reasoning(parsed: dict) -> str:
        findings_summary = "; ".join(
            f"[{f.get('severity')}] {f.get('description')}" for f in parsed.get("findings", [])
        )
        return f"{parsed.get('verdict', '?')}" + (f" — {findings_summary}" if findings_summary else "")

    result, r = _call_json_agent(
        "context_reviewer", payload, run, "review",
        required_keys=["verdict", "findings"], reasoning_fn=_reasoning,
        resume_from=resume_from,
        table_name=proposal.get("table_name"),
    )
    return result, r.response_id


def _chronicle(run, executed_proposal: dict, spec_name: str) -> dict:
    payload = {"executed_proposal": executed_proposal, "spec_name": spec_name}

    def _reasoning(parsed: dict) -> str | None:
        summary = "; ".join(
            f"{s.get('section')}: {s.get('diff_summary')}" for s in parsed.get("sections", [])
        )
        return summary or None

    result, _r = _call_json_agent(
        "context_chronicler", payload, run, "chronicle",
        required_keys=["sections"], reasoning_fn=_reasoning,
        table_name=executed_proposal.get("table_name"), spec_name=spec_name,
    )
    return result


def ingest_spec(
    spec_name: str, spec_markdown: str, sample_events: list[dict],
    full_events: list[dict] | None = None, pm_question_queries: list[tuple[str, str]] | None = None,
) -> dict:
    """Runs one feature spec through the full pipeline. Returns a summary dict with
    the final status, proposal_id, table_name, and the Langfuse trace_url that proves
    this all came from the pipeline, not a human.

    sample_events is design-time CONTEXT ONLY, given to the proposer so it can see
    real field shapes/nesting when drafting columns_ddl/column_mapping — small and
    stratified (e.g. ~30 per event type) on purpose, to keep its prompt cheap. It is
    NOT what gets tested or loaded. full_events is the actual dataset: perf_tool times
    candidates against it, test_harness's insert_integrity checks the landed row count
    against it (this IS the completeness gate — a truncated load fails it directly,
    no separate check needed), and the real production INSERT at execute uses it.
    Falls back to sample_events if full_events isn't supplied, so a caller that only
    has a small sample degrades to the old (sample-only) behavior rather than erroring.
    """
    meta_client = get_client(database="agent_meta")
    full_events = full_events if full_events is not None else sample_events
    sample_scratch_info = _write_sample_scratch_file(sample_events)

    # Durably store spec_markdown so a LATER, separate step (the dashboard's
    # explicit "Create Insight" trigger -- see analytics_agent.run_analytics_for_spec)
    # can look it up without needing the original in-memory call or local file.
    meta_client.insert(
        "spec_sources", [[spec_name, spec_markdown]], column_names=["spec_name", "spec_markdown"],
    )

    with traced_run(agent="pipeline", spec=spec_name) as run:
        # Clean re-ingest, not an accidental one: drop whatever a PRIOR
        # successful run of this exact spec left in atlys BEFORE any new
        # propose/review work starts -- see _cleanup_previous_execution's
        # docstring for why this used to be actively destructive instead.
        _cleanup_previous_execution(meta_client, get_client(database="atlys"), run, spec_name)

        revision = 0
        prior_findings = None
        previous_draft = None
        proposal_id = None
        final_proposal = None
        final_review = None
        # Each agent's own conversation, resumed across rework revisions instead
        # of starting fresh every time -- real memory of what it already
        # said/did (see agent_runner/runner.py's resume_from docstring), not a
        # replacement for prior_findings/previous_draft (kept as-is below;
        # those are genuinely NEW information -- the reviewer's findings, the
        # last concrete draft -- not something the model already has in its
        # own conversation history).
        propose_resume_id: str | None = None
        review_resume_id: str | None = None
        # Cumulative across ALL rounds, not just the latest failure. Each round used
        # to overwrite prior_findings with only the newest failure, so the proposer
        # never saw the pattern across rounds — e.g. round 1 flags MV-A's Nullable
        # ORDER BY, proposer fixes MV-A but introduces the identical bug in a NEW
        # MV-B in round 2, and round 2's findings (MV-B only) give no signal that
        # this is a recurring category, not a one-off. Tagged with the round found
        # so the proposer can tell "this was already addressed" (a fix attempt
        # happened after it) from "this is still live" (no later attempt touched it).
        finding_history: list[dict] = []

        while True:
            try:
                draft, propose_resume_id = _propose(
                    run, spec_name, spec_markdown, sample_scratch_info, prior_findings, previous_draft,
                    resume_from=propose_resume_id,
                )
            except AgentOutputError as e:
                # _call_json_agent already retried once internally; this means
                # it failed twice in a row. Treat like any other failure mode —
                # bounded feedback into the same loop, not a crash.
                run.log(step="propose_json_error", input=e.raw_text[:1000], output=str(e.parse_error))
                if revision >= MAX_REVISIONS:
                    raise
                revision += 1
                prior_findings = _record_findings(finding_history, [{
                    "severity": "block", "category": "invalid_json",
                    "description": f"Your last two attempts didn't produce valid JSON: {e.parse_error}",
                    "suggested_fix": "Output ONLY a single JSON object matching the schema — no markdown fences, no prose, no truncation.",
                }], revision)
                continue

            # Defensive normalization: a real run had the proposer write
            # table_name as "atlys.group_application_events" (schema-qualified)
            # instead of bare. perf_tool builds scratch tables as
            # "{scratch_db}.{table_name}__{label}__{hex}" -- a qualified
            # table_name then produces a 3-segment identifier
            # ("atlys_staging.atlys.group_application_events__...") which
            # ClickHouse's parser rejects outright (a table identifier is at
            # most database.table). Keep only the last dot-separated segment.
            if "." in draft.get("table_name", ""):
                draft["table_name"] = draft["table_name"].rsplit(".", 1)[-1]

            # Defensive normalization: the schema says columns_ddl is "column
            # definitions only... no ENGINE/ORDER BY" (i.e. no surrounding
            # parens either), but a real run wrapped it in an extra outer `(...)`
            # anyway -- every consumer (perf_tool, test_harness, execute) already
            # wraps it in `CREATE TABLE x (...)`, so a self-added outer paren
            # produces `((...))`  and a syntax error at the very first column.
            # Strip it here, once, rather than trusting every downstream
            # CREATE-statement builder to defend against it independently.
            cols = draft.get("columns_ddl", "").strip()
            # Stronger version of the same failure: a real run on this branch (after
            # strict json_schema was already active, so this ISN'T a JSON-shape
            # problem -- columns_ddl is a free-form string the schema can't validate
            # DDL syntax inside) had the proposer write a FULL `CREATE TABLE name
            # (...) ENGINE = ... ORDER BY ...` statement into columns_ddl three
            # revisions in a row, despite the prompt saying column-defs-only. Extract
            # just the column-def body when this happens instead of only trusting
            # the model to comply — greedy match backtracks to the LAST `)` before
            # ENGINE/end, which is correct even with nested parens in column types
            # like LowCardinality(Nullable(String)).
            # Requires the literal ENGINE keyword right after the columns' closing
            # paren -- NOT optional. An earlier version made it optional and matched
            # greedily to the string's last ")" instead, which is WRONG whenever
            # ORDER BY/PARTITION BY (which come after ENGINE) themselves contain
            # parens, e.g. "... ) ENGINE = MergeTree ... ORDER BY (event_date)" —
            # greedy backtracking found ORDER BY's closing paren, not the columns'.
            m = re.search(r"CREATE\s+TABLE\b.*?\((.*)\)\s*ENGINE\b", cols, re.IGNORECASE | re.DOTALL)
            if m:
                cols = m.group(1).strip()
            else:
                # A DIFFERENT real failure mode (same run, later revisions): no
                # leading CREATE TABLE this time, but the ENGINE/PARTITION BY/
                # ORDER BY/SETTINGS tail still leaked directly onto otherwise-bare
                # column defs. Cut everything from ENGINE onward.
                tail = re.search(r"\bENGINE\s*=", cols, re.IGNORECASE)
                if tail:
                    cols = cols[: tail.start()].strip()
            if cols.startswith("(") and cols.endswith(")"):
                cols = cols[1:-1].strip()
            # Whichever branch fired can leave one unmatched trailing ")" — the
            # model's own accidental close of a CREATE TABLE wrapper it otherwise
            # never fully wrote (e.g. "...CHECK length(x) > 0\n)\nENGINE..." — the
            # tail-cut above removes "ENGINE..." but leaves that stray "\n)").
            # Every real column-type paren (LowCardinality(String), CHECK(...))
            # opens and closes within the same column, so a genuinely balanced
            # columns_ddl has equal counts.
            if cols.count(")") > cols.count("(") and cols.endswith(")"):
                cols = cols[:-1].strip().rstrip(",").strip()
            draft["columns_ddl"] = cols

            previous_draft = draft
            # full_events, not sample_events: perf test, test harness (whose
            # insert_integrity check compares landed-row-count to len(sample_rows) —
            # this IS the completeness gate now, for free) and the real production
            # INSERT must all see the same real, complete dataset the proposer only
            # saw a small stratified slice of.
            #
            # Same failure class as ordering_key_candidates/materialized_views above
            # (valid top-level JSON, malformed nested value -- a real run had a
            # column_mapping VALUE that was itself a dict instead of a plain column
            # name string, which crashed as "unhashable type: 'dict'" trying to use
            # it as a dict key). This has now shown up in three independent nested
            # fields across real runs, so the pattern is: don't try to enumerate
            # every possible way a field can be malformed in advance -- catch the
            # structural error where it actually happens and feed it back.
            try:
                flattened_events = _flatten_events(full_events, _column_mapping_to_dict(draft.get("column_mapping", [])))
            except (KeyError, TypeError, AttributeError) as e:
                run.log(step="propose_malformed_column_mapping", input=draft.get("column_mapping"), output=str(e))
                if revision >= MAX_REVISIONS:
                    raise
                revision += 1
                prior_findings = _record_findings(finding_history, [{
                    "severity": "block", "category": "invalid_json",
                    "description": f"column_mapping is malformed ({e}). It must be an array of {{raw_field, column_name}} pairs — column_name must be a plain string, not a nested object.",
                    "suggested_fix": "Fix column_mapping so every entry has string raw_field and column_name values, not a dict/list for column_name.",
                }], revision)
                continue

            with run.span("perf_evaluation", revision=revision):
                # Top-level required_keys (checked in _call_json_agent) doesn't
                # reach into list-item structure -- ordering_key_candidates can be
                # present but contain items missing their OWN required keys (seen
                # on a real run: valid top-level JSON, but a candidate item
                # missing "label"). Same failure class as AgentOutputError above,
                # same treatment: bounded feedback into the rework loop, not a
                # crash, rather than trying to exhaustively schema-validate every
                # nested structure in Python.
                try:
                    candidates = [
                        Candidate(
                            label=c["label"], ordering_key=c["ordering_key"],
                            partition_key=_normalize_partition_key(c.get("partition_key", "toYYYYMM(timestamp)")),
                        )
                        for c in draft["ordering_key_candidates"]
                    ]
                except (KeyError, TypeError) as e:
                    run.log(step="propose_malformed_candidates", input=draft.get("ordering_key_candidates"), output=str(e))
                    if revision >= MAX_REVISIONS:
                        raise
                    revision += 1
                    prior_findings = _record_findings(finding_history, [{
                        "severity": "block", "category": "invalid_json",
                        "description": f"ordering_key_candidates items are malformed ({e}). Each item needs exactly: label, ordering_key, partition_key (optional).",
                        "suggested_fix": "Fix the ordering_key_candidates array so every item has 'label' and 'ordering_key' as string keys — check for typos/missing fields in each candidate object.",
                    }], revision)
                    continue
                try:
                    perf_report = run_perf_test(
                        table_name=draft["table_name"],
                        columns_ddl=draft["columns_ddl"],
                        candidates=candidates,
                        sample_source=flattened_events,
                        query_patterns=_build_perf_query_patterns(draft["columns_ddl"]),
                        sample_limit=len(full_events),
                        include_baseline=True,
                    )
                except AllCandidatesFailedError as e:
                    # columns_ddl itself is broken (e.g. invalid ClickHouse type
                    # nesting) — every candidate fails identically. Don't crash the
                    # pipeline: feed the real DDL error back to the proposer as a
                    # rework trigger, same path as a reviewer block-finding.
                    run.log(step="perf_evaluation_ddl_error", input=draft["columns_ddl"], output=e.errors)
                    if revision >= MAX_REVISIONS:
                        raise
                    revision += 1
                    prior_findings = _record_findings(finding_history, [{
                        "severity": "block", "category": "invalid_ddl",
                        "description": f"columns_ddl failed to create in ClickHouse: {next(iter(e.errors.values()))}",
                        "suggested_fix": "Fix the ClickHouse type syntax (e.g. LowCardinality must wrap Nullable, not the reverse: LowCardinality(Nullable(String))) and resubmit.",
                    }], revision)
                    continue
                winner = next(c for c in candidates if c.label == perf_report.winner) if perf_report.winner != "baseline_legacy" else candidates[0]
                # Full report (every candidate's real timings/rows-read/bytes-read,
                # not just the winner) -- perf_report.to_json() already has this,
                # it just wasn't being logged. This IS the evidence the ordering
                # key decision is based on; a UI showing this needs the real
                # comparison, not just the final answer.
                # json.loads(perf_report.to_json()) not [c.__dict__ ...]: candidates
                # contain nested QueryTiming dataclass objects, not JSON-serializable
                # directly -- to_json() already has the recursive dataclass->dict
                # handling (same method _write_proposal uses), reused here rather
                # than duplicating it.
                run.log(
                    step="perf_winner",
                    input=[c.label for c in candidates],
                    output=json.loads(perf_report.to_json()),
                )

            ddl = (
                f"CREATE TABLE {draft['table_name']} ({draft['columns_ddl']}) "
                f"ENGINE = MergeTree {_partition_clause(winner.partition_key)}ORDER BY {winner.ordering_key}"
            )
            # Same failure class as ordering_key_candidates above (valid top-level
            # JSON, malformed nested item — a real run hit test_harness.py's
            # `mv["ddl"]` KeyError on an MV item missing that key) — checked ONCE
            # here rather than defended against separately in both call sites that
            # use materialized_views (ddl_syntax_check pre-review AND the full
            # test_harness post-review), and before either wastes a scratch round
            # trip on a proposal we already know is malformed.
            mvs = draft.get("materialized_views", [])
            bad_mvs = [i for i, mv in enumerate(mvs) if not isinstance(mv, dict) or "name" not in mv or "ddl" not in mv]
            if bad_mvs:
                run.log(step="propose_malformed_mvs", input=mvs, output=f"items missing name/ddl at index {bad_mvs}")
                if revision >= MAX_REVISIONS:
                    raise ValueError(f"materialized_views items at index {bad_mvs} missing required 'name'/'ddl' keys, revision cap reached")
                revision += 1
                prior_findings = _record_findings(finding_history, [{
                    "severity": "block", "category": "invalid_json",
                    "description": f"materialized_views item(s) at index {bad_mvs} are missing 'name' and/or 'ddl'. Every MV needs both.",
                    "suggested_fix": "Fix the materialized_views array so every item has 'name' (string) and 'ddl' (the full CREATE MATERIALIZED VIEW statement) as keys.",
                }], revision)
                continue

            # Same failure class, one level deeper: an mv dict CAN have both
            # 'name' and 'ddl' keys (passing the check above) while 'ddl'
            # itself is only the backing target table's CREATE TABLE
            # statement, missing the actual `CREATE MATERIALIZED VIEW ... AS
            # SELECT ...` that makes it a materialized view at all -- a real
            # run submitted exactly this for 4 revisions straight (7-10),
            # burning the whole MAX_REVISIONS budget on a proposal that could
            # never pass test_harness's mv_integrity query-logic check:
            # test_harness.py's _extract_select correctly found no "AS
            # SELECT" (there wasn't one) and returned the ddl unchanged, which
            # then got wrapped as `SELECT count() FROM (CREATE TABLE ...)` --
            # a guaranteed ClickHouse syntax error that read like a
            # test_harness bug but was actually malformed proposer output.
            # Catching it here is a cheap, deterministic, one-line-regex
            # check instead of spending a full review + data-insert test
            # cycle to discover the same thing.
            incomplete_mvs = [
                i for i, mv in enumerate(mvs)
                if isinstance(mv.get("ddl"), str) and not re.search(r"CREATE\s+MATERIALIZED\s+VIEW", mv["ddl"], re.IGNORECASE)
            ]
            if incomplete_mvs:
                run.log(step="propose_incomplete_mv_ddl", input=mvs, output=f"no CREATE MATERIALIZED VIEW statement at index {incomplete_mvs}")
                if revision >= MAX_REVISIONS:
                    raise ValueError(f"materialized_views items at index {incomplete_mvs} have no CREATE MATERIALIZED VIEW statement, revision cap reached")
                revision += 1
                prior_findings = _record_findings(finding_history, [{
                    "severity": "block", "category": "invalid_ddl",
                    "description": f"materialized_views item(s) at index {incomplete_mvs} don't contain a CREATE MATERIALIZED VIEW statement anywhere in their 'ddl' -- looks like only the backing target table's CREATE TABLE was included.",
                    "suggested_fix": "If this MV needs a separate backing target table (a `TO`-target pattern), 'ddl' must contain BOTH statements: the backing CREATE TABLE AND the CREATE MATERIALIZED VIEW ... TO <target> AS SELECT ... that actually populates it, separated by ';'. A bare backing table with no MATERIALIZED VIEW statement never gets data written to it.",
                }], revision)
                continue

            proposal = {
                "table_name": draft["table_name"], "columns_ddl": draft["columns_ddl"], "ddl": ddl,
                "ordering_key": winner.ordering_key,
                "partition_key": winner.partition_key, "column_mapping": _column_mapping_to_dict(draft.get("column_mapping", [])),
                "materialized_views": mvs,
                "confidence": draft.get("confidence", 0.5),
                # _as_text: a real run returned rationale as a list of bullet
                # strings instead of one string (schema says string) -- unlike
                # the malformed-structure cases above, this is benign and cheaply
                # normalizable (join the bullets), not worth burning a revision on.
                "rationale": _as_text(draft.get("rationale", "")) + f" | ordering key chosen by perf_tool: {perf_report.speedup_vs_baseline}x vs legacy baseline.",
            }

            # DDL syntax gate — runs BEFORE review, not after. Reviewer LLM calls and
            # the full data-insert test cycle are both expensive (money + a shared
            # revision from MAX_REVISIONS); a broken MV CREATE statement is a cheap,
            # mechanical failure ClickHouse itself can tell us about in milliseconds.
            # Catching it here means a syntax error costs one fast scratch-DDL round
            # trip instead of a full review round PLUS the same test_harness failure
            # it would have hit anyway later. Base table DDL isn't re-checked here —
            # perf_evaluation above already validated it via the candidate scratch
            # tables it creates for timing.
            if proposal["materialized_views"]:
                with run.span("ddl_syntax_check", revision=revision):
                    syntax_suite = run_new_table_tests(
                        table_name=proposal["table_name"], columns_ddl=proposal["columns_ddl"],
                        ordering_key=proposal["ordering_key"], partition_key=proposal["partition_key"],
                        sample_rows=[], smoke_queries=[],
                        materialized_views=proposal["materialized_views"], ddl_only=True,
                    )
                    run.log(
                        step="ddl_syntax_result", input=None,
                        output={"passed": syntax_suite.passed, "failures": [r.__dict__ for r in syntax_suite.results if not r.passed]},
                    )
                    if not syntax_suite.passed:
                        if revision >= MAX_REVISIONS:
                            # Let it fall through to the real review/test cycle rather than
                            # rejecting outright — the shared cap means we're out of cheap
                            # shots either way, and the normal test_harness_failed path below
                            # gives a more complete final error report than stopping here would.
                            pass
                        else:
                            revision += 1
                            prior_findings = _record_findings(finding_history, [{
                                "severity": "block", "category": "invalid_ddl",
                                "description": f"MV DDL failed to create in scratch (syntax/type check, before review): {[r.description + ': ' + r.actual for r in syntax_suite.results if not r.passed]}",
                                "suggested_fix": "Fix the failing MV's CREATE statement (check ORDER BY column nullability, type nesting, and referenced column names) and resubmit.",
                            }], revision)
                            continue

            mv_json = [json.dumps(mv) for mv in proposal["materialized_views"]]
            proposal_id = _write_proposal(
                meta_client, spec_name=spec_name, table_name=proposal["table_name"], ddl=proposal["ddl"],
                ordering_key=proposal["ordering_key"], partition_key=proposal["partition_key"],
                materialized_views=mv_json, perf_report=perf_report.to_json(),
                confidence=proposal["confidence"], rationale=proposal["rationale"],
                status="pending_review", revision=revision, trace_url=run.url,
            ) if proposal_id is None else proposal_id
            if revision > 0:
                _update_proposal_status(
                    meta_client, proposal_id, status="pending_review", revision=revision,
                    ddl=proposal["ddl"], ordering_key=proposal["ordering_key"], partition_key=proposal["partition_key"],
                    materialized_views=mv_json, perf_report=perf_report.to_json(),
                    confidence=proposal["confidence"], rationale=proposal["rationale"],
                )

            try:
                review, review_resume_id = _review(run, proposal, resume_from=review_resume_id)
            except AgentOutputError as e:
                # Reviewer failed to produce valid JSON twice in a row — treat as
                # a request_changes with no specific findings (we don't know what
                # it would have flagged) rather than crashing the whole pipeline.
                run.log(step="review_json_error", input=e.raw_text[:1000], output=str(e.parse_error))
                review = {"verdict": "request_changes", "findings": [{
                    "severity": "block", "category": "reviewer_output_error",
                    "description": f"Reviewer failed to produce valid JSON: {e.parse_error}",
                    "suggested_fix": "Re-propose; the reviewer couldn't be evaluated this round.",
                }], "context_sections_used": [], "reviewer_confidence": 0.0}
            _write_review(meta_client, proposal_id, revision, review, review.get("context_sections_used", []), run.url)

            final_proposal, final_review, final_flattened_events = proposal, review, flattened_events
            at_cap = revision >= MAX_REVISIONS
            if review["verdict"] != "approve" and not at_cap:
                revision += 1
                prior_findings = _record_findings(finding_history, review["findings"], revision)
                run.log(
                    step="review_feedback_to_proposer",
                    input={"verdict": review["verdict"]},
                    output={"revision": revision, "findings_sent_to_proposer": prior_findings[-MAX_FINDINGS_IN_PAYLOAD:]},
                )
                _update_proposal_status(meta_client, proposal_id, status="needs_rework", revision=revision)
                continue
            if review["verdict"] != "approve":
                run.log(step="revision_cap_hit", input={"revision": revision}, output={"proceeding_anyway": True, "unresolved_findings": review["findings"]})
                proposal["confidence"] = min(proposal["confidence"], 0.4)

            _update_proposal_status(meta_client, proposal_id, status="approved")
            # Its own visible step, not just a ClickHouse status write -- the
            # gate passing (or being forced open at the revision cap) is a
            # real, distinct milestone worth seeing on its own, between the
            # reviewer's verdict and the real execution that follows it.
            run.log(
                step="approved",
                input=None,
                output={
                    "table_name": proposal.get("table_name"),
                    "verdict": review["verdict"],
                    "revision": revision,
                    "proceeded_at_revision_cap": at_cap and review["verdict"] != "approve",
                    "confidence": proposal.get("confidence"),
                },
            )

            with run.span("test_harness"):
                smoke_queries = build_smoke_queries(final_proposal["table_name"], final_proposal["columns_ddl"], pm_question_queries)
                suite = run_new_table_tests(
                    table_name=final_proposal["table_name"],
                    columns_ddl=final_proposal["columns_ddl"],
                    ordering_key=final_proposal["ordering_key"], partition_key=final_proposal["partition_key"],
                    sample_rows=final_flattened_events, smoke_queries=smoke_queries,
                    materialized_views=final_proposal.get("materialized_views", []),
                )
                # Log only failures to the trace, not the full suite (which is mostly
                # passes) — this is a readability fix for the trace/dashboard, not a
                # behavior change: the LLM below (prior_findings) has ALWAYS only ever
                # received the failures list, never the full suite. Full results remain
                # in agent_meta.test_runs for anyone who needs the complete picture.
                run.log(
                    step="test_harness_result", input=None,
                    output={
                        "passed": suite.passed,
                        "n_passed": sum(1 for r in suite.results if r.passed),
                        "n_total": len(suite.results),
                        "failures": [r.__dict__ for r in suite.results if not r.passed],
                    },
                )
                if not suite.passed:
                    if at_cap:
                        _update_proposal_status(meta_client, proposal_id, status="needs_rework")
                        return {"status": "needs_rework", "reason": "test_harness_failed", "proposal_id": proposal_id, "trace_url": run.url, "test_results": [r.__dict__ for r in suite.results]}
                    revision += 1
                    prior_findings = _record_findings(finding_history, [{
                        "severity": "block", "category": "test_harness_failure",
                        "description": f"Correctness test(s) failed: {[r.description + ': ' + r.actual for r in suite.results if not r.passed]}",
                        "suggested_fix": "Fix the failing query/MV logic (check column names, types, and join keys) and resubmit.",
                    }], revision)
                    _update_proposal_status(meta_client, proposal_id, status="needs_rework", revision=revision)
                    continue

            # Real execution — rolled back on any failure and fed back as rework,
            # same pattern as perf_evaluation/review/test_harness. Increasingly
            # sophisticated MV SQL (CTEs, TO targets, refreshable views) keeps
            # surfacing new ClickHouse edge cases the scratch tests don't catch
            # (e.g. an MV's own ORDER BY using a Nullable column) — bounded
            # feed-back-and-retry handles unknown failure modes generically instead
            # of us hand-patching every possible DDL quirk in advance.
            # (label, statement) tracked as we go so the except handler can pinpoint
            # exactly which statement failed — with several MVs each potentially
            # multi-statement, "execution failed: <ClickHouse error>" alone doesn't
            # tell the model WHICH one, and ClickHouse's own error text often
            # doesn't name the table/column either (e.g. "Sorting key contains
            # nullable columns" — that's it, no identifiers). Without this, a
            # rework round can't reliably tell which MV to fix and may leave the
            # actual culprit untouched while "fixing" something else.
            executing: tuple[str, str] | None = None
            try:
                with run.span("execute"):
                    data_client = get_client(database="atlys")
                    executing = ("base table", final_proposal["ddl"])
                    data_client.command(final_proposal["ddl"])
                    for mv in final_proposal.get("materialized_views", []):
                        # Some MVs are 2 statements: a backing table (for a `TO`
                        # target) plus the CREATE MATERIALIZED VIEW itself.
                        # ClickHouse's HTTP interface rejects multi-statement
                        # bodies, so split and run each.
                        for stmt in mv["ddl"].split(";"):
                            stmt = stmt.strip()
                            if stmt:
                                executing = (mv.get("name", "unnamed MV"), stmt)
                                data_client.command(stmt)
                    if final_flattened_events:
                        body = "\n".join(json.dumps(r, default=str) for r in final_flattened_events).encode()
                        data_client.raw_insert(
                            final_proposal["table_name"], insert_block=body, fmt="JSONEachRow",
                            settings={"input_format_skip_unknown_fields": 1},
                        )

                    # Refreshable MVs (`REFRESH EVERY ...`) don't populate from the
                    # INSERT above at all -- unlike a trigger-based MV, they only
                    # recompute on their own schedule, and CREATE happens before the
                    # INSERT (has to, for a trigger-based MV to catch it), so a
                    # refreshable MV's automatic first refresh can race ahead of the
                    # data landing -- it then "succeeds" with zero rows and won't
                    # try again for up to the full REFRESH interval. Found via a real
                    # run: forex's trigger-based MV populated correctly (1807 rows),
                    # but abandoned_checkout_recovery's REFRESH EVERY 1 HOUR MV sat at
                    # 0 rows despite reporting a successful refresh. Force a fresh
                    # refresh here, after data is confirmed landed, and wait for it
                    # to actually complete rather than trusting the schedule.
                    for mv in final_proposal.get("materialized_views", []):
                        mv_name = mv.get("name")
                        if mv_name and "REFRESH" in mv["ddl"].upper():
                            executing = (mv_name, f"SYSTEM REFRESH VIEW atlys.{mv_name}")
                            data_client.command(f"SYSTEM REFRESH VIEW atlys.{mv_name}")
                            for _ in range(15):  # ~15s bounded wait, not indefinite
                                status_rows = data_client.query(
                                    "SELECT status FROM system.view_refreshes WHERE view = {name:String}",
                                    parameters={"name": mv_name},
                                ).result_rows
                                if status_rows and status_rows[0][0] != "Running":
                                    break
                                time.sleep(1)
                            run.log(step="refreshable_mv_synced", input=mv_name, output={"status": status_rows[0][0] if status_rows else "unknown"})

                    run.log(
                        step="executed",
                        input=None,
                        output={
                            "base_table": f"atlys.{final_proposal['table_name']}",
                            "base_table_ddl": final_proposal["ddl"],
                            "rows_inserted": len(final_flattened_events) if final_flattened_events else 0,
                            "materialized_views": [
                                {"name": f"atlys.{mv.get('name')}", "ddl": mv.get("ddl", "")}
                                for mv in final_proposal.get("materialized_views", [])
                            ],
                        },
                    )
            except Exception as e:
                failed_label, failed_stmt = executing or ("unknown", "")
                run.log(step="execute_error", input={"failed_object": failed_label, "statement": failed_stmt}, output=str(e))
                data_client.command(f"DROP TABLE IF EXISTS atlys.{final_proposal['table_name']}")
                for mv in final_proposal.get("materialized_views", []):
                    # _drop_mv_objects parses the DDL for every real object it
                    # creates, not just mv['name'] -- a `TO <backing_table>`
                    # target's backing table is its own separate CREATE TABLE
                    # statement that mv['name'] alone never named.
                    _drop_mv_objects(data_client, mv)
                if at_cap:
                    _update_proposal_status(meta_client, proposal_id, status="rejected")
                    return {"status": "rejected", "reason": "execute_failed", "proposal_id": proposal_id, "trace_url": run.url, "error": str(e)}
                revision += 1
                prior_findings = _record_findings(finding_history, [{
                    "severity": "block", "category": "invalid_ddl",
                    "description": f"Real execution against ClickHouse failed on '{failed_label}'. Failing statement: {failed_stmt}\nError: {e}",
                    "suggested_fix": "Fix ONLY the failing statement identified above (e.g. if it's an ORDER BY referencing a Nullable column, fix that column's typing or the ordering key) — keep everything else from previous_attempt unchanged unless it's also actually wrong.",
                }], revision)
                _update_proposal_status(meta_client, proposal_id, status="needs_rework", revision=revision)
                continue

            break

        _update_proposal_status(meta_client, proposal_id, status="executed")
        register_tests(proposal_id, final_proposal["table_name"], smoke_queries)

        with run.span("regression_suite"):
            regression = run_regression_suite(proposal_id, run.url)
            run.log(step="regression_result", input=None, output={"passed": regression.passed, "n_tests": len(regression.results)})

        chronicle_ok = True
        with run.span("chronicle"):
            try:
                chronicle = _chronicle(run, final_proposal, spec_name)
                _write_context_sections(meta_client, chronicle["sections"], run.url)
                run.log(
                    step="context_updated",
                    input=None,
                    output={
                        "sections": [
                            {
                                "section": s.get("section"),
                                "title": s.get("title"),
                                "is_new": not s.get("before"),
                                "diff_summary": s.get("diff_summary"),
                            }
                            for s in chronicle["sections"]
                        ],
                    },
                )
            except AgentOutputError as e:
                # The schema itself is already executed and real — don't discard a
                # successful run because the context-layer writeup failed. Surface
                # it clearly instead of silently losing the context update.
                run.log(step="chronicle_json_error", input=e.raw_text[:1000], output=str(e.parse_error))
                chronicle_ok = False

        # Analytics agent is a separate, explicitly-triggered step (see
        # analytics/analytics_agent.run_analytics / scripts/run_analytics_*.py)
        # -- ingest_spec() no longer calls it automatically, so executing a
        # schema never implicitly generates an insight.
        return {
            "status": "executed", "proposal_id": proposal_id, "table_name": final_proposal["table_name"],
            "ddl": final_proposal["ddl"], "revisions": revision, "regression_passed": regression.passed,
            "chronicle_ok": chronicle_ok, "trace_url": run.url,
        }
