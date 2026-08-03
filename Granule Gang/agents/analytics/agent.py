"""
Analytics Agent

1. Reads straight from the ContextAgent's own tables (analytics_context.business_context,
   atlys.meta_context_registry) to see what the Instrumentation/Context agents just
   did -- newly registered tables, the latest business-context document -- rather than
   only trusting whatever a caller happens to pass in.
2. Turns a natural-language analytics request into ClickHouse SQL. The LLM's ONLY
   job is to write the query text; ClickHouse does all the aggregation once it
   runs. "random" / "i'm feeling lucky" skips the LLM and runs a predetermined
   query instead.
3. Runs the query on ClickHouse and gets the aggregate result back.
4. Interprets that result: pulls in business context (to explain WHY, never to
   supply numbers) and asks the LLM to turn the query's own rows into actionable
   insights -- strictly grounded in what that query actually returned, not
   supplemented with other side-queries the user never saw (see
   interpret_results()'s docstring for why that was a real trust problem, not
   just noise).
"""

from pathlib import Path
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
import json
import random
import re

from agents.tracing.agent import get_tracer


@dataclass
class Insight:
    """Represents an analytical insight."""
    title: str
    description: str
    metric: str
    value: Any
    context: Dict[str, Any] = field(default_factory=dict)
    severity: str = "info"  # info, warning, critical
    tags: List[str] = field(default_factory=list)
    query: str = ""
    timestamp: str = ""


# ---------------------------------------------------------------------------
# "I'm feeling lucky" -- predetermined queries run when the user doesn't have a
# specific question. Each targets the 8 core production tables (base_context.md
# §3), so they run regardless of which spec's tables happen to be loaded.
# Column names follow base_context.md §3/§4 exactly (e.g. `value`/`currency` on
# purchase_completed, `is_crossed_failed_attempt_threshold` on document_uploaded).
# ---------------------------------------------------------------------------
LUCKY_QUERIES: List[Dict[str, str]] = [
    {
        "label": "Weekly conversion trend",
        "description": "Purchases and unique buyers by week, last 90 days.",
        "sql": """
            SELECT toStartOfWeek(timestamp) AS week,
                   count() AS purchases,
                   uniq(user_id) AS buyers
            FROM {database}.purchase_completed
            WHERE timestamp >= now() - INTERVAL 90 DAY
            GROUP BY week
            ORDER BY week
        """,
    },
    {
        "label": "Device split of the core funnel",
        "description": "Users reaching each core funnel step, split by device_type.",
        "sql": """
            SELECT device_type,
                   uniqIf(user_id, step = 'destination_card_clicked') AS clicked,
                   uniqIf(user_id, step = 'application_started') AS started,
                   uniqIf(user_id, step = 'purchase_completed') AS purchased
            FROM (
                SELECT user_id, device_type, 'destination_card_clicked' AS step FROM {database}.destination_card_clicked
                UNION ALL
                SELECT user_id, device_type, 'application_started' FROM {database}.application_started
                UNION ALL
                SELECT user_id, device_type, 'purchase_completed' FROM {database}.purchase_completed
            )
            GROUP BY device_type
            ORDER BY purchased DESC
        """,
    },
    {
        "label": "Top countries by purchase volume",
        "description": "geoip_country_code ranked by purchases and revenue, last 30 days.",
        "sql": """
            SELECT geoip_country_code,
                   count() AS purchases,
                   sum(value) AS revenue
            FROM {database}.purchase_completed
            WHERE timestamp >= now() - INTERVAL 30 DAY
            GROUP BY geoip_country_code
            ORDER BY revenue DESC
            LIMIT 20
        """,
    },
    {
        "label": "Daily anomalies in application starts",
        "description": "Days where application_started volume deviates from its trailing 7-day average.",
        "sql": """
            WITH daily AS (
                SELECT toDate(timestamp) AS day, count() AS starts
                FROM {database}.application_started
                WHERE timestamp >= now() - INTERVAL 60 DAY
                GROUP BY day
            )
            SELECT day, starts,
                   avg(starts) OVER (ORDER BY day ROWS BETWEEN 7 PRECEDING AND 1 PRECEDING) AS trailing_avg,
                   stddevPop(starts) OVER (ORDER BY day ROWS BETWEEN 7 PRECEDING AND 1 PRECEDING) AS trailing_std
            FROM daily
            ORDER BY day DESC
            LIMIT 30
        """,
    },
    {
        "label": "Document capture pass rate by OS",
        "description": "document_uploaded pass rate (is_crossed_failed_attempt_threshold = 0), split by os.",
        "sql": """
            SELECT os,
                   countIf(is_crossed_failed_attempt_threshold = 0) AS passes,
                   count() AS attempts,
                   passes / attempts AS pass_rate
            FROM {database}.document_uploaded
            WHERE os IS NOT NULL
            GROUP BY os
            ORDER BY attempts DESC
        """,
    },
]

# Few-shot style anchor for nl_to_sql()'s system prompt: bucketed grouping with a
# guarded-division percentage, and a multi-CTE trend with currency normalization --
# both real, previously hand-written analyses, not toy examples. The point isn't
# these exact queries; it's "aggregate down to a handful of meaningful rows" instead
# of a flat multi-dimension dump.
_GOOD_QUERY_EXAMPLES = """=== EXAMPLE 1: bucketed segment comparison (countIf/avgIf, not CASE/SUM(CASE...)) ===
SELECT
    CASE
        WHEN lower(citizenship) IN ('in', 'pk') THEN 'Latin / Major Script (IN, PK)'
        ELSE 'Non-Latin / Other Script (Other)'
    END AS citizenship_group,
    count() AS total_uploads,
    countIf(retry_count > 0) AS uploads_with_retries,
    round(countIf(retry_count > 0) * 100.0 / nullIf(count(), 0), 2) AS pct_with_retries,
    round(avgIf(retry_count, retry_count > 0), 2) AS avg_retries_when_retried,
    countIf(coalesce(is_crossed_failed_attempt_threshold, 0) = 1) AS threshold_failures
FROM atlys.document_uploaded
WHERE lower(doc_type) LIKE '%passport%'
GROUP BY citizenship_group
ORDER BY pct_with_retries DESC;

=== EXAMPLE 2: monthly trend with currency normalization (CTEs, not a raw dump) ===
WITH
    currency_subtotals AS (
        SELECT toStartOfMonth(timestamp) AS month_start, coalesce(currency, 'UNKNOWN') AS currency,
               sum(coalesce(value, 0)) AS native_sum, count() AS conversion_count
        FROM atlys.purchase_completed
        WHERE timestamp >= now() - INTERVAL 12 MONTH
        GROUP BY month_start, currency
    ),
    normalized_to_usd AS (
        SELECT month_start,
               sum(CASE currency WHEN 'USD' THEN native_sum WHEN 'INR' THEN native_sum * 0.012 ELSE native_sum END) AS total_revenue_usd,
               sum(conversion_count) AS total_conversions
        FROM currency_subtotals
        GROUP BY month_start
    )
SELECT month_start, total_revenue_usd, total_conversions,
       round(total_revenue_usd / nullIf(total_conversions, 0), 2) AS revenue_per_conversion
FROM normalized_to_usd
ORDER BY month_start ASC
LIMIT 200;

=== EXAMPLE 3: sequential funnel with a time bound (windowFunnel, not self-joins) ===
-- "Did a user reach step N within a window after step 1?" -- e.g. did they click a
-- reminder within 7 days of it opening, then convert within 30 days of that. Use
-- windowFunnel() for this, not a chain of self-joins with a hand-written date-math
-- ON condition per step -- every extra join is another place to get INTERVAL syntax
-- wrong, and windowFunnel expresses the whole time-bounded sequence in one call.
WITH steps AS (
    SELECT user_id, timestamp, 'reminder_opened' AS step FROM atlys.reminder_opened
    WHERE timestamp >= now() - INTERVAL 90 DAY
    UNION ALL
    SELECT user_id, timestamp, 'reminder_cta_clicked' AS step FROM atlys.reminder_cta_clicked
    WHERE timestamp >= now() - INTERVAL 90 DAY
    UNION ALL
    SELECT user_id, timestamp, 'reconverted' AS step FROM atlys.reconverted
    WHERE timestamp >= now() - INTERVAL 90 DAY
),
levels AS (
    SELECT user_id,
           windowFunnel(30 * 86400)(timestamp, step = 'reminder_opened', step = 'reminder_cta_clicked', step = 'reconverted') AS level
    FROM steps
    GROUP BY user_id
)
SELECT
    countIf(level >= 1) AS opened,
    countIf(level >= 2) AS clicked,
    countIf(level >= 3) AS reconverted,
    round(countIf(level >= 2) * 100.0 / nullIf(countIf(level >= 1), 0), 2) AS open_to_click_pct,
    round(countIf(level >= 3) * 100.0 / nullIf(countIf(level >= 2), 0), 2) AS click_to_reconvert_pct
FROM levels
LIMIT 200;"""

_LUCKY_TRIGGERS = ("random", "i'm feeling lucky", "im feeling lucky", "feeling lucky", "surprise me", "lucky")

# Only read-only statements may be executed -- the SQL text in this file comes
# straight from an LLM. Blocks anything that mutates data/schema; a stray
# semicolon (a second statement smuggled in) is rejected separately.
_FORBIDDEN_SQL_KEYWORDS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|ATTACH|DETACH|RENAME|"
    r"GRANT|REVOKE|KILL|OPTIMIZE|SYSTEM|EXCHANGE|SET)\b",
    re.IGNORECASE,
)

# ClickHouse requires date arithmetic to go through INTERVAL (`ts + INTERVAL 30
# DAY`); a bare `ts + 30 DAY` is a SYNTAX_ERROR, not silently coerced. The LLM
# gets this right most of the time but not always -- inconsistently, even
# within the same query (one join's ON clause using INTERVAL correctly, the
# next one dropping it). Matches a +/- sign followed directly by a number and
# a time unit with nothing (in particular no "INTERVAL") in between.
_MISSING_INTERVAL_RE = re.compile(
    r"[+-]\s*\d+\s*(SECOND|MINUTE|HOUR|DAY|WEEK|MONTH|QUARTER|YEAR)S?\b",
    re.IGNORECASE,
)


class AnalyticsAgent:
    """Agent that analyzes data and produces actionable insights."""

    CORE_FUNNEL_STEPS = ["destination_card_clicked", "application_started", "document_uploaded", "purchase_completed"]
    SEGMENT_CUT_COLUMNS = ("device_type", "geoip_country_code", "funnel_type")
    # Below the LIMIT 200 backstop but high enough that hitting it signals the
    # request itself was too broad, not just a query that happens to have a lot
    # of legitimate rows -- see handle_insight_request()'s "narrow it" hint.
    _BROAD_RESULT_HINT_THRESHOLD = 150

    def __init__(self, client, database: str, context_agent=None, openrouter_config=None, mcp_client=None):
        self.client = client
        self.database = database
        self.context_agent = context_agent
        self.insights: List[Insight] = []

        self.openrouter_config = openrouter_config
        self._llm_client = None
        if openrouter_config and openrouter_config.enabled:
            self._llm_client = openrouter_config.get_client()

        # When set (see main.py's analytics stage), every ClickHouse read this
        # agent makes goes through the ClickHouse MCP server instead of the
        # clickhouse_connect client directly -- `client` is still kept around as
        # the fallback for standalone/test usage that doesn't wire an MCP client up.
        self.mcp_client = mcp_client

    def run_query(self, query: str) -> List[Dict]:
        """Execute a query and return results as list of dicts. This is the one
        place any agent code -- deterministic or LLM-generated -- actually talks
        to ClickHouse (via the ClickHouse MCP server when configured, otherwise
        directly through clickhouse_connect)."""
        if self.mcp_client is not None:
            return self.mcp_client.run_select_query(query)
        result = self.client.query(query)
        columns = result.column_names
        return [dict(zip(columns, row)) for row in result.result_rows]

    # ============================================================
    # 1. What changed -- read straight from the ContextAgent's tables
    # ============================================================

    def discover_context_changes(self) -> Dict[str, Any]:
        """Everything the ContextAgent/InstrumentationAgent currently know:
        every table registered in atlys.meta_context_registry (newest first),
        plus the latest version of the unified business-context document from
        ContextAgent.get_latest_context(). This is how the Analytics Agent
        finds out what just got instrumented without needing it handed to it
        as an argument."""
        context = self.context_agent.get_latest_context() if self.context_agent else {}
        return {
            "newly_instrumented_tables": self._registered_tables(),
            "business_context_version": context.get("version", 0),
            "business_context_changelog": context.get("changelog_summary", ""),
        }

    def _registered_tables(self) -> List[Dict[str, Any]]:
        """Every currently-registered table in meta_context_registry, newest first."""
        query = f"""
            SELECT entity_name, kind, description, source_spec, version, created_at
            FROM {self.database}.meta_context_registry
            WHERE is_current = 1
            ORDER BY created_at DESC
        """
        try:
            return self.run_query(query)
        except Exception as e:
            print(f"Could not read meta_context_registry: {e}")
            return []

    def list_available_tables(self) -> List[str]:
        """All queryable tables in the database (core funnel + anything newly
        instrumented), for scoping SQL generation and schema summaries."""
        try:
            rows = self.run_query(
                f"SELECT name FROM system.tables WHERE database = '{self.database}' AND engine NOT LIKE '%View%'"
            )
            return sorted({r["name"] for r in rows} | set(self.CORE_FUNNEL_STEPS))
        except Exception:
            return list(self.CORE_FUNNEL_STEPS)

    def _print_context_changes(self, changes: Dict[str, Any]) -> None:
        tables = changes.get("newly_instrumented_tables", [])
        print(f"\nContext check: {len(tables)} table(s) currently registered in meta_context_registry.")
        for t in tables[:5]:
            print(f"  - {t.get('entity_name', '?')} (source: {t.get('source_spec') or 'n/a'})")
        if len(tables) > 5:
            print(f"  ...and {len(tables) - 5} more")
        version = changes.get("business_context_version", 0)
        changelog = changes.get("business_context_changelog", "")
        if version:
            print(f"  Business context document at version {version}" + (f" -- {changelog}" if changelog else ""))
        else:
            print("  No business context document found (has ContextAgent.load_v1() been run?)")

    # ============================================================
    # 2. Natural language -> SQL (LLM writes ONLY the query)
    # ============================================================

    def ask_user_for_request(self, prompt_fn: Callable[[str], str] = input) -> str:
        return prompt_fn(
            "\nWhat insight would you like? Describe it in plain English -- trends, "
            "anomalies, segment comparisons, correlations -- or type 'random' / "
            "\"i'm feeling lucky\" for a surprise query. ('quit' to stop)\n> "
        ).strip()

    def _is_lucky(self, request: str) -> bool:
        normalized = re.sub(r"[^a-z0-9' ]", "", request.strip().lower())
        return any(trigger in normalized for trigger in _LUCKY_TRIGGERS)

    def _schema_summary(self, tables: Optional[List[str]] = None) -> str:
        """Real column names/types/comments from system.columns, so the SQL-writing
        LLM works off the actual schema instead of guessing."""
        where = f"database = '{self.database}'"
        if tables:
            in_list = ",".join(f"'{t}'" for t in tables)
            where += f" AND table IN ({in_list})"
        try:
            rows = self.run_query(f"""
                SELECT table, name, type, comment
                FROM system.columns
                WHERE {where}
                ORDER BY table, position
            """)
        except Exception as e:
            return f"(schema lookup failed: {e})"

        by_table: Dict[str, List[Dict]] = {}
        for r in rows:
            by_table.setdefault(r["table"], []).append(r)

        lines = []
        for table, cols in by_table.items():
            lines.append(f"Table {self.database}.{table}:")
            for c in cols:
                desc = f"  -- {c['comment']}" if c.get("comment") else ""
                lines.append(f"  {c['name']} {c['type']}{desc}")
        return "\n".join(lines) if lines else "(no schema info available)"

    def _context_text(self, tables: Optional[List[str]] = None) -> str:
        """The business-context document, verbatim, for an LLM prompt.
        `tables` is accepted for interface compatibility but no longer
        filters anything -- the whole document is the atomic unit now (see
        agents/context/agent.py); it already includes metrics, known issues,
        the join map, auto-instrumented tables, and any open flags."""
        if not self.context_agent:
            return "No context agent configured."
        ctx = self.context_agent.get_latest_context()
        content = ctx.get("content", "")
        if not content:
            return "No business context document found (has ContextAgent.load_v1() been run?)."
        return f"Business context document (version {ctx.get('version', '?')}):\n{content}"

    def _extract_sql(self, raw: str) -> str:
        text = raw.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(sql)?\s*", "", text)
            text = re.sub(r"```\s*$", "", text)
        return text.strip().rstrip(";").strip()

    def _validate_readonly_sql(self, sql: str) -> None:
        if not sql:
            raise ValueError("LLM returned an empty query.")
        if ";" in sql:
            raise ValueError("Only a single statement is allowed (found a ';' inside the query).")
        if not re.match(r"^(SELECT|WITH)\b", sql.strip(), re.IGNORECASE):
            raise ValueError("Generated query must be a read-only SELECT/WITH statement.")
        if _FORBIDDEN_SQL_KEYWORDS.search(sql):
            raise ValueError("Generated query contains a disallowed keyword -- only read-only SELECTs are permitted.")
        # Cheap, high-signal truncation check: a response cut off mid-generation
        # (hit max_tokens before finishing) almost always leaves an unclosed
        # paren -- e.g. a WITH-chain's last CTE missing its closing ")" and the
        # final SELECT entirely. Catching that here fails fast with a clear
        # reason instead of a round-trip to ClickHouse for a cryptic
        # "Unmatched parentheses" SYNTAX_ERROR pointing at a `LIMIT` we bolted
        # onto the end of already-broken SQL.
        opens, closes = sql.count("("), sql.count(")")
        if opens != closes:
            raise ValueError(
                f"Generated query has unbalanced parentheses ({opens} '(' vs {closes} ')') -- "
                "it was likely cut off mid-generation. Try a simpler/narrower request, or just ask again."
            )
        bad_interval = _MISSING_INTERVAL_RE.search(sql)
        if bad_interval:
            raise ValueError(
                f"Generated query does date arithmetic without INTERVAL ({bad_interval.group(0)!r}) -- "
                "ClickHouse requires e.g. `+ INTERVAL 30 DAY`, not `+ 30 DAY`. Try again."
            )

    def _sql_system_prompt(self) -> str:
        return f"""You are an expert ClickHouse SQL analyst.
You write SQL -- you never compute, guess, or state the answer yourself; ClickHouse
executes the query and does 100% of the aggregation.

CRITICAL -- result size discipline. Every row you return gets fed into another LLM
call to interpret; an unnecessarily wide result burns tokens and money for zero
analytical benefit, and dumping raw dimension cross-products isn't an insight anyway.
- ALWAYS bound event tables by time. If the request doesn't name a range (e.g.
  "trends", "recently", "lately", no dates mentioned), default to the LAST QUARTER:
  `WHERE timestamp >= now() - INTERVAL 90 DAY`. Never scan a table's full history
  unless the request explicitly asks for all-time or names a wider range.
- Pick the grain and the 1-2 dimensions that actually answer the question, not every
  dimension "just in case". A result of roughly 10-50 rows is usually the right size
  for a question like this; if your query would return far more, aggregate further --
  a coarser time grain (week/month instead of day), a CASE-bucketed grouping instead
  of a raw high-cardinality breakdown (see Example 1), or one fewer GROUP BY column.
- ALWAYS end with `LIMIT 200` as a hard backstop, even after aggregating well.
- Round floats to 2 decimals; guard every division with nullIf(denominator, 0).

Other rules:
- Output ONE single ClickHouse SQL statement, starting with SELECT or WITH. Nothing else:
  no prose, no explanation, no markdown fences.
- Read-only only: never INSERT/UPDATE/DELETE/DROP/ALTER/CREATE/TRUNCATE/SET/SYSTEM.
- Only reference tables/columns that appear in the provided schema.
- For trends: group by toStartOfDay/toStartOfWeek/toStartOfMonth(timestamp) -- choose
  the grain so row count stays reasonable across the window (weekly, not daily, for a
  multi-month span).
- For anomalies: compare a value against its trailing average/stddev (e.g. window
  functions with ROWS BETWEEN, or stddevPop over a grouped window).
- For segment comparisons: GROUP BY the relevant segment column(s) (e.g. device_type,
  geoip_country_code, os, funnel_type) and order by the primary metric, not the segment name.
- For correlations: use corr() or covarPop() between two numeric measures.
- For ANY "did step B happen after step A" question -- funnels, drop-off,
  recovery/re-engagement, "converted within N days of X" -- default to
  windowFunnel() (see Example 3) over a UNIONed event stream, per the provided
  analysis guidance. Do NOT hand-write a chain of self-joins with a per-step
  date-math ON condition; that's both less idiomatic and exactly how the
  INTERVAL mistake above tends to happen (one more join, one more chance to
  drop it). Only fall back to explicit joins if the steps span tables with no
  shared timestamp-ordered identifier windowFunnel can key on.
- Always qualify table names with the database (e.g. atlys.purchase_completed).
- ALL date/time arithmetic must go through INTERVAL: `ts + INTERVAL 30 DAY`,
  `ts - INTERVAL 7 DAY`. A bare `ts + 30 DAY` (no INTERVAL) is a ClickHouse
  SYNTAX_ERROR, not shorthand -- this applies every single time you add/subtract
  a duration, including inside JOIN ... ON clauses, not just in WHERE.
- Prefer ClickHouse's conditional aggregate functions over generic
  CASE/SUM(CASE...) patterns: use `countIf(cond)`, `sumIf(cond, val)`, and
  `avgIf(cond, val)` instead of `sum(CASE WHEN cond THEN 1 ELSE 0 END)` or
  `avg(CASE WHEN cond THEN val END)` -- they're shorter, clearer, and this is
  exactly the kind of engine-native function the query should showcase, not
  portable-but-generic ANSI SQL. Use `coalesce(col, default)` for any nullable
  column rather than leaving a NULL to silently drop out of an aggregate. Use
  `windowFunnel()` (see Example 3) for any "did step B happen after step A"
  question rather than self-joins.

{_GOOD_QUERY_EXAMPLES}
Match this style: CTEs when the logic has real stages, CASE-based bucketing over raw
per-value breakdowns, guarded division, sensible rounding, ORDER BY the metric that
matters (not the group label)."""

    def _ensure_row_limit(self, sql: str, default_limit: int = 200) -> str:
        """Deterministic backstop, independent of how well the prompt's row-budget
        guidance gets followed: if the generated query has no LIMIT, add one. Every
        row that comes back gets fed into another LLM call to interpret, so an
        unbounded result is a direct token/cost hit, not just a style nit."""
        if re.search(r"\bLIMIT\s+\d+", sql, re.IGNORECASE):
            return sql
        return f"{sql.rstrip()}\nLIMIT {default_limit}"

    def nl_to_sql(self, request: str, tables: Optional[List[str]] = None) -> str:
        """Turn a natural-language analytics request into a single read-only SQL
        query. The LLM's only output is SQL text -- no aggregation happens in the
        LLM, all of it happens once the query runs on ClickHouse."""
        if not self._llm_client:
            raise RuntimeError("No LLM configured (OPENROUTER_API_KEY) -- cannot translate the request to SQL.")

        tables = tables or self.list_available_tables()
        schema_summary = self._schema_summary(tables)
        context_text = self._context_text(tables)

        prompt = f"""Write a ClickHouse SQL query that answers this request:
"{request}"

=== SCHEMA ({self.database}) ===
{schema_summary}

=== BUSINESS CONTEXT ===
{context_text}

Return only the SQL statement."""

        with get_tracer().trace_span("analytics.nl_to_sql", input_data={"request": request}):
            response = self._llm_client.chat.completions.create(
                model=self.openrouter_config.model,
                messages=[
                    {"role": "system", "content": self._sql_system_prompt()},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                # 800 was sized for simple single-table aggregations; the style
                # guidance above (CTEs, guarded division, bucketed grouping) and
                # multi-table comparisons routinely need more room than that to
                # finish -- 800 was cutting a real multi-CTE query off mid-way
                # through its last CTE, before the final SELECT, producing
                # invalid SQL (unbalanced parens) that only failed once it hit
                # ClickHouse.
                max_tokens=2500,
            )
            raw = (response.choices[0].message.content or "").strip()
            sql = self._extract_sql(raw)
            self._validate_readonly_sql(sql)
            return self._ensure_row_limit(sql)

    # ============================================================
    # 3. Run the query on ClickHouse (coordinate + fetch results)
    # ============================================================

    def handle_insight_request(self, request: str) -> List[Insight]:
        """End to end for a single user request: get SQL (LLM-written, or a
        predetermined 'lucky' query), run it on ClickHouse, interpret the result."""
        with get_tracer().trace_span("analytics.handle_insight_request", input_data={"request": request}):
            if self._is_lucky(request):
                lucky = random.choice(LUCKY_QUERIES)
                label = f"(feeling lucky) {lucky['label']}"
                sql = lucky["sql"].strip().format(database=self.database)
                print(f"Feeling lucky -- running: {lucky['label']} -- {lucky['description']}")
            else:
                label = request
                sql = self.nl_to_sql(request)

            print(f"\nGenerated query:\n{sql}\n")
            rows = self.run_query(sql)
            print(f"ClickHouse returned {len(rows)} row(s).")
            if len(rows) >= self._BROAD_RESULT_HINT_THRESHOLD:
                print(
                    "  Hint: that's a lot of rows for one question -- try narrowing it: name a "
                    "specific segment ('by device_type'), a shorter time window, or a specific "
                    "metric instead of everything at once. A vague request burns more tokens for a fuzzier answer."
                )

            insights = self.interpret_results(request=label, sql=sql, rows=rows)
            for insight in insights:
                print(f"\n[{insight.severity.upper()}] {insight.title}\n{insight.description}")
            return insights

    def run_interactive(self, prompt_fn: Callable[[str], str] = input, max_rounds: Optional[int] = None) -> List[Insight]:
        """Interactive loop: show what the ContextAgent has recorded, then
        repeatedly ask the user what they want to know, turn it into SQL, run it,
        and interpret the result -- until they quit."""
        self._print_context_changes(self.discover_context_changes())

        insights_before = len(self.insights)
        rounds = 0
        while max_rounds is None or rounds < max_rounds:
            request = self.ask_user_for_request(prompt_fn)
            if not request or request.lower() in {"quit", "exit", "q", "done"}:
                break
            try:
                self.handle_insight_request(request)
            except Exception as e:
                print(f"Could not complete that request: {e}")
            rounds += 1

        # One batch write for the whole session, not one per question --
        # matches update_context()'s "batch per run, not per item" rule.
        if self.context_agent and hasattr(self.context_agent, "add_analytical_findings"):
            self.context_agent.add_analytical_findings(self.insights[insights_before:], source="interactive session")

        return self.insights

    # ============================================================
    # 4. Interpret results: business context -> insights, strictly grounded
    #    in what the query actually returned
    # ============================================================

    def interpret_results(self, request: str, sql: str, rows: List[Dict]) -> List[Insight]:
        """Apply business context to a raw ClickHouse result and turn it into
        actionable insights via the LLM narrative engine.

        Deliberately does NOT run extra "multi-cut" queries (device/geo/segment
        breakdowns) behind the scenes anymore. A prior version did, and it was
        a real trust problem, not just noise: analyze_by_segment() has no time
        filter, so those side-queries pulled ALL-TIME totals into the same
        prompt as e.g. a "last 90 days" trend query, with nothing telling the
        LLM (or the user) they came from a different scope -- the LLM then
        blended them into one narrative, producing numbers (e.g. "iOS: 63.5K
        app starters") that don't trace back to the query actually shown on
        screen. Insights are now grounded ONLY in `rows` -- the exact result
        of the exact query the user saw. If a request needs a device/geo/
        segment cut, that has to be in the query itself (the SQL system prompt
        already asks for the right dimensions).
        """
        context_text = self._context_text()

        payload = {
            "request": request,
            "query": sql,
            "result_row_count": len(rows),
            "result_rows": rows[:200],  # cap so a large result set doesn't blow the prompt
        }

        if not self._llm_client:
            # No LLM configured -- still surface the raw result as an insight
            # rather than silently producing nothing.
            return [self.generate_insight(
                title=request[:80],
                description=f"{len(rows)} row(s) returned. LLM not configured, so no narrative interpretation was generated.",
                metric="row_count",
                value=len(rows),
                severity="info",
                tags=["ad_hoc"],
                query=sql,
            )]

        return self.generate_narrative_insights(payload, context_text, pm_questions=[request])

    # ============================================================
    # Deterministic analysis helpers (funnel, segments, anomalies)
    # ============================================================

    def sequential_funnel(self, steps: List[str], id_column: str = "user_id", window_days: int = 30) -> Dict[str, int]:
        """Count users reaching each step of `steps`, IN ORDER, within a
        `window_days` window -- via ClickHouse's windowFunnel(), per
        base_context.md §7's explicit guidance ("Prefer windowFunnel/
        sequenceMatch over per-table row dumps"). A prior version counted
        count(DISTINCT user_id) independently per table with no ordering/join
        constraint at all, which isn't a funnel -- it doesn't verify a user who
        appears in step N+1 ever passed through step N.
        """
        if not steps:
            return {}
        union_sql = "\nUNION ALL\n".join(
            f"SELECT {id_column}, timestamp, '{t}' AS step FROM {self.database}.{t}"
            for t in steps
        )
        conds = ", ".join(f"step = '{t}'" for t in steps)
        level_counts = ", ".join(f"countIf(level >= {i + 1}) AS step_{i + 1}" for i in range(len(steps)))
        query = f"""
        SELECT {level_counts}
        FROM (
            SELECT {id_column}, windowFunnel({window_days * 86400})(timestamp, {conds}) AS level
            FROM ( {union_sql} )
            GROUP BY {id_column}
        )
        """
        rows = self.run_query(query)
        row = rows[0] if rows else {f"step_{i + 1}": 0 for i in range(len(steps))}
        return {step: row.get(f"step_{i + 1}", 0) for i, step in enumerate(steps)}

    def get_funnel_metrics(self) -> Dict[str, Any]:
        """Sequential funnel over the 4 core pre-purchase steps."""
        return self.sequential_funnel(self.CORE_FUNNEL_STEPS)

    def get_drop_off_rates(self, funnel: Optional[Dict[str, int]] = None) -> Dict[str, float]:
        """Calculate drop-off rates between funnel steps."""
        funnel = funnel if funnel is not None else self.get_funnel_metrics()
        rates = {}
        steps = list(funnel.keys())
        for i in range(len(steps) - 1):
            current = funnel[steps[i]]
            next_step = funnel[steps[i + 1]]
            if current > 0:
                rates[f"{steps[i]} -> {steps[i+1]}"] = (current - next_step) / current * 100
        return rates

    def analyze_by_segment(self, segment_column: str, table: str) -> List[Dict]:
        """Analyze metrics broken down by a segment."""
        query = f"""
        SELECT
            {segment_column},
            count(DISTINCT user_id) as users,
            count() as events
        FROM {self.database}.{table}
        WHERE {segment_column} IS NOT NULL
        GROUP BY {segment_column}
        ORDER BY users DESC
        LIMIT 20
        """
        return self.run_query(query)

    def detect_anomalies(self, table: str, metric_column: str,
                         time_column: str = "timestamp",
                         window: str = "1 day") -> List[Dict]:
        """Detect statistical anomalies in time series data."""
        query = f"""
        WITH stats AS (
            SELECT
                toStartOfDay({time_column}) as day,
                avg({metric_column}) as avg_val,
                stddevPop({metric_column}) as std_val
            FROM {self.database}.{table}
            WHERE {time_column} >= now() - INTERVAL 30 DAY
            GROUP BY day
        )
        SELECT
            day,
            avg_val,
            std_val,
            CASE WHEN avg_val > (lag(avg_val) OVER (ORDER BY day) + 2 * lag(std_val) OVER (ORDER BY day))
                 THEN 'spike'
                 WHEN avg_val < (lag(avg_val) OVER (ORDER BY day) - 2 * lag(std_val) OVER (ORDER BY day))
                 THEN 'drop'
                 ELSE 'normal'
            END as anomaly_type
        FROM stats
        ORDER BY day DESC
        LIMIT 30
        """
        return self.run_query(query)

    def generate_insight(self, title: str, description: str, metric: str,
                         value: Any, severity: str = "info", **kwargs) -> Insight:
        """Create and store an insight."""
        insight = Insight(
            title=title,
            description=description,
            metric=metric,
            value=value,
            severity=severity,
            **kwargs
        )
        self.insights.append(insight)
        return insight

    def generate_narrative_insights(
        self, query_results: Dict[str, Any], context: str, pm_questions: Optional[List[str]] = None
    ) -> List[Insight]:
        """Use LLM to generate narrative insights from query results."""
        if not self._llm_client:
            print("No LLM client configured, falling back to basic insights")
            return []

        questions_block = ""
        if pm_questions:
            bullet_list = "\n".join(f"- {q}" for q in pm_questions)
            questions_block = f"""
        This feature's spec lists these specific questions a PM will ask. Prioritize
        insights that directly answer them over generic funnel commentary -- if the
        query results don't support answering one, say so rather than skipping it silently:
        {bullet_list}
        """

        prompt = f"""
        Analyze the following query results and context to generate actionable product insights.
        {questions_block}
        Context:
        {context}

        Query Results:
        {json.dumps(query_results, indent=2, default=str)}

        GROUNDING RULE -- every number in every insight must come from "Query Results"
        above. Do not introduce a figure, percentage, or segment breakdown that isn't
        literally present there, even if it's true in general or you recall it from
        elsewhere in Context -- if "Query Results" doesn't have it, you don't state it.
        Context may explain WHY a number in Query Results looks the way it does (e.g. a
        known issue), but it is never itself the source of a number in an insight.

        Style rules for "description" -- these are read on a dashboard, not in a report:
        - ONE sentence, ~20 words max. Lead with the number, not the setup.
        - State the action directly ("Fix the iOS OTP autofill bug" not "Consider
          investigating whether the OTP issue may be contributing to this").
        - Cut hedging and connective filler: no "This suggests", "It's worth noting",
          "may potentially", "warrants investigation". Say what you mean.
        - If a known issue from context explains it, name it in ~3 words, don't restate
          the issue's full description.

        Output JSON format:
        {{
            "insights": [
                {{
                    "title": "Short title",
                    "description": "One terse sentence: the number + the action.",
                    "metric": "name of key metric",
                    "value": "value of metric",
                    "severity": "info, warning, or critical",
                    "tags": ["tag1", "tag2"]
                }}
            ]
        }}

        CRITICAL: Return ONLY valid JSON. Do not include markdown blocks, explanations, or any other text.
        """

        with get_tracer().trace_span("analytics.generate_narrative_insights"):
            try:
                response = self._llm_client.chat.completions.create(
                    model=self.openrouter_config.model,
                    messages=[
                        {"role": "system", "content": "You are an expert product analyst who writes tight, scannable dashboard copy for busy PMs -- no filler, no hedging, straight to the point."},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.3,
                    max_tokens=4000,
                    response_format={"type": "json_object"},
                )

                content = response.choices[0].message.content.strip()
                # Strip markdown formatting if present
                if content.startswith("```json"):
                    content = content[7:]
                elif content.startswith("```"):
                    content = content[3:]
                if content.endswith("```"):
                    content = content[:-3]
                content = content.strip()

                parsed = json.loads(content)

                new_insights = []
                for item in parsed.get("insights", []):
                    insight = self.generate_insight(
                        title=item.get("title", "Insight"),
                        description=item.get("description", ""),
                        metric=item.get("metric", ""),
                        value=item.get("value", ""),
                        severity=item.get("severity", "info"),
                        tags=item.get("tags", [])
                    )
                    new_insights.append(insight)
                return new_insights
            except Exception as e:
                print(f"Failed to generate narrative insights: {e}")
                return []

    def analyze_spec_tables(self, table_names: List[str]) -> Dict[str, Any]:
        """Analyze the tables InstrumentationAgent just created for the current
        spec: a sequential funnel over them (in the order given, which follows
        the spec's own event sequence) plus per-table segment breakdowns. This
        is what makes a spec's insights about *that* feature, rather than only
        ever repeating the 4 core funnel tables' generic numbers regardless of
        which spec is running.
        """
        if not table_names:
            return {}

        funnel: Dict[str, int] = {}
        drop_offs: Dict[str, float] = {}
        if len(table_names) > 1:
            try:
                funnel = self.sequential_funnel(table_names)
                drop_offs = self.get_drop_off_rates(funnel)
            except Exception as e:
                print(f"Spec funnel query failed: {e}")

        segments: Dict[str, List[Dict]] = {}
        for table in table_names:
            for segment in ("device_type", "geoip_country_code"):
                try:
                    rows = self.analyze_by_segment(segment, table)
                    if rows:
                        segments[f"{table}_{segment}"] = rows
                except Exception:
                    pass

        return {"tables": table_names, "funnel": funnel, "drop_offs": drop_offs, "segments": segments}

    def run_full_analysis(
        self,
        spec_tables: Optional[List[str]] = None,
        pm_questions: Optional[List[str]] = None,
        spec_name: str = "",
    ) -> List[Insight]:
        """Run the complete analysis pipeline: the 4 core pre-purchase funnel
        tables (always-relevant background) plus, when given, the current
        spec's own newly-instrumented tables and its "Questions the PM will
        ask". A prior version only ever analyzed the 4 core tables -- every
        spec produced the same generic funnel commentary and never actually
        answered that spec's own PM questions.
        """
        with get_tracer().trace_span("analytics.run_full_analysis", metadata={"spec_name": spec_name}):
            insights_before = len(self.insights)

            # What the ContextAgent/InstrumentationAgent have on record right now
            # (independent of the spec_tables argument below).
            changes = self.discover_context_changes()

            # Core pre-purchase funnel
            funnel = self.get_funnel_metrics()
            drop_offs = self.get_drop_off_rates(funnel)

            self.generate_insight(
                title="Conversion Funnel Overview",
                description=f"Funnel metrics: {json.dumps(funnel)}",
                metric="funnel_users",
                value=funnel,
                severity="info",
                tags=["funnel", "overview"]
            )

            for step, rate in drop_offs.items():
                severity = "warning" if rate > 50 else "info"
                self.generate_insight(
                    title=f"Drop-off: {step}",
                    description=f"{rate:.1f}% of users drop off at this step",
                    metric="drop_off_rate",
                    value=rate,
                    severity=severity,
                    tags=["funnel", "drop_off"]
                )

            segments_data = {}
            for table in ["destination_card_clicked", "application_started", "purchase_completed"]:
                for segment in self.SEGMENT_CUT_COLUMNS:
                    try:
                        segments = self.analyze_by_segment(segment, table)
                        if segments:
                            top = segments[0]
                            segments_data[f"{table}_{segment}"] = segments
                            self.generate_insight(
                                title=f"Top {segment} for {table}",
                                description=f"{top[segment]}: {top['users']} users",
                                metric=f"top_{segment}",
                                value=top,
                                severity="info",
                                tags=["segment", table, segment]
                            )
                    except Exception:
                        pass

            # The current spec's own tables -- what makes this run's insights
            # specific to the feature being analyzed.
            spec_analysis: Dict[str, Any] = {}
            if spec_tables:
                spec_analysis = self.analyze_spec_tables(spec_tables)
                if spec_analysis.get("funnel"):
                    self.generate_insight(
                        title=f"{spec_name or 'Feature'} funnel",
                        description=f"Sequential funnel over {', '.join(spec_tables)}: {json.dumps(spec_analysis['funnel'])}",
                        metric="spec_funnel_users",
                        value=spec_analysis["funnel"],
                        severity="info",
                        tags=["funnel", "spec", spec_name] if spec_name else ["funnel", "spec"],
                    )
                for step, rate in spec_analysis.get("drop_offs", {}).items():
                    severity = "warning" if rate > 50 else "info"
                    self.generate_insight(
                        title=f"{spec_name or 'Feature'} drop-off: {step}",
                        description=f"{rate:.1f}% of users drop off at this step",
                        metric="spec_drop_off_rate",
                        value=rate,
                        severity=severity,
                        tags=["funnel", "drop_off", "spec", spec_name] if spec_name else ["funnel", "drop_off", "spec"],
                    )

            # Now generate narrative insights using LLM
            query_results = {
                "core_funnel": funnel,
                "core_drop_offs": drop_offs,
                "core_segments": segments_data,
                "spec_analysis": spec_analysis,
                "context_changes": {
                    "newly_instrumented_tables": [t.get("entity_name") for t in changes.get("newly_instrumented_tables", [])],
                    "business_context_version": changes.get("business_context_version", 0),
                },
            }

            context_summary = self._context_text()
            self.generate_narrative_insights(query_results, context_summary, pm_questions=pm_questions)

            # One batch write for this whole run, not one per insight --
            # matches update_context()'s "batch per run, not per item" rule.
            if self.context_agent and hasattr(self.context_agent, "add_analytical_findings"):
                self.context_agent.add_analytical_findings(self.insights[insights_before:], source=spec_name or "core funnel analysis")

            return self.insights

    def export_insights(self, output_path: Path, format: str = "json"):
        """Export insights to file."""
        data = [
            {
                "title": i.title,
                "description": i.description,
                "metric": i.metric,
                "value": i.value,
                "severity": i.severity,
                "tags": i.tags,
                "query": i.query,
                "timestamp": i.timestamp,
            }
            for i in self.insights
        ]
        if format == "json":
            output_path.write_text(json.dumps(data, indent=2, default=str))
        elif format == "markdown":
            md = "# Analytics Insights\n\n"
            for i in self.insights:
                md += f"## {i.title} [{i.severity.upper()}]\n"
                md += f"{i.description}\n\n"
                md += f"**Metric:** {i.metric}  \n"
                md += f"**Value:** {i.value}  \n\n"
            output_path.write_text(md)


if __name__ == "__main__":
    import clickhouse_connect
    from agents.config import get_config, make_llm_call_fn
    from agents.context.agent import ContextAgent
    from agents.analytics.mcp_client import ClickHouseMCPClient

    ch_config, lf_config, or_config = get_config()
    client = clickhouse_connect.get_client(
        host=ch_config.host,
        port=ch_config.port,
        username=ch_config.user,
        password=ch_config.password,
        secure=ch_config.secure,
        database=ch_config.database,
    )

    context_agent = None
    if or_config.enabled:
        context_agent = ContextAgent(client=client, llm_call_fn=make_llm_call_fn(or_config))

    mcp_client = ClickHouseMCPClient.connect_or_none(ch_config)
    try:
        agent = AnalyticsAgent(
            client=client,
            database=ch_config.database,
            context_agent=context_agent,
            openrouter_config=or_config,
            mcp_client=mcp_client,
        )
        agent.run_interactive()
    finally:
        if mcp_client is not None:
            mcp_client.close()
