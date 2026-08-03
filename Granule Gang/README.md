# Granule Gang

## Atlys Track

## Insight Out
Meet the little voices inside your data.

## Team Members
- Krishna @cybraia
- Shreya @alt-shreya

## What it does
> Much like a cartographer looks to Atlas for answers, your team can now look to this agentic workflow for answers.

Insight Out takes a raw feature spec (a markdown doc plus an `.ndjson` sample events file) and runs it through a multi-agent system: 
* an **Instrumentation Agent** `agents/instrumentation/agent.py` that designs and executes the ClickHouse DDL for the new feature 
* an **Analytics Agent** `agents/analytics/agent.py` that runs sequenced funnel and segment analysis over both the new tables and the existing funnel and writes a PM-readable insight report, and 
* a **Context Agent** `agents/context/agent.py` that keeps a single living business-context document up to date as new tables get instrumented and flags anything that goes stale or contradictory. 

Every run is traced end to end in Langfuse, and displayed to the user via STreamlit.

## Hosted Demo

[Demo hosted link](https://clickhousehackathon-4jwvrjw9d75syixdytc5wf.streamlit.app/)

## Demo Video

_TODO: add the 2–3 minute recorded demo video link here (mandatory for submission)._

## Architecture

Insight Out is three agents plus a shared context layer, run sequentially by
`main.py` for a single spec directory: **Context → Instrumentation → Analytics →
Visualization**.

- **Instrumentation Agent** (`agents/instrumentation/`) reads a feature spec and generates ClickHouse table DDL plus a daily segment-rollup materialized view, executes it against the live ClickHouse Cloud service, and registers the new tables' schema in `atlys.meta_context_registry`.

- **Analytics Agent** (`agents/analytics/`) hands off from Instrumentation once the new tables exist. on an interactive terminal run, it actually
   asks the user what insight they'd like to see next -- in plain English -- and acts on it: it turns that request into a single read-only ClickHouse SQL query itself (the LLM's only job is writing the SQL; ClickHouse does 100% of the aggregation once it runs), executes it, and interprets the returned rows into grounded narrative insights before looping back to ask again.

- **Context Agent** (`agents/context/`) runs both before and after the other two: it seeds/reads the current business-context document going in, and after
  Instrumentation creates new tables, it auto-documents them in the base_context. A deterministic freshness check (does every
  registered table still exist?) plus an LLM pass surface contradictions, gaps, and obsolete facts into an "Open flags" section.

**Where the context layer lives, and why:** the whole business-context document is stored as **one Markdown blob per version** in a ClickHouse table,
`analytics_context.business_context` (`doc_id`, `content`, `version`, `changelog_summary`, `updated_at`), a `ReplacingMergeTree` keyed on `doc_id`. 

Every change — the initial seed, an auto-documented table, a new audit flag, a resolved flag — is a new `INSERT` with `version = previous + 1` rather than a mutation. That makes the table double as its own audit trail: readers always `ORDER BY version DESC LIMIT 1` to get current state, but the full history of how
the context evolved is queryable directly, in the same store as the data it
describes, with no separate file store or vector DB to keep in sync. 

A vector store buys you semantic search over chunks, but **this document doesn't need retrieval-by-similarity** -- every reader wants the exact current version (or
an exact prior one), a `WHERE`/`ORDER BY` lookup, not a nearest-neighbor guess,
and chunking a single coherent doc into embeddings would just add a stale-index
problem on top of the one we're already solving. 

Keeping it in the same ClickHouse service as everything
else means the Analytics Agent reads context and event data through the same
client, in the same query engine, with **one fewer moving part** to keep in sync.

**Langfuse tracing:** all three agents emit spans/generations through a shared
tracer in `agents/tracing/`, so a single spec run produces one trace showing the
Context Agent's read, the Instrumentation Agent's DDL generation and execution,
the Analytics Agent's funnel queries and narrative generation, and the Context
Agent's post-run audit — in call order, with LLM prompts/completions attached. If
Langfuse isn't configured (no keys in `.env`), the same spans fall back to a local
JSONL file so the pipeline never depends on external tracing to run.

**LLM provider(s):** every agent calls through one shared entry point,
`agents/config.py:make_llm_call_fn()`. The primary provider is **Anthropic**
(`claude-haiku-4-5-20251001` by default) for fast, cheap structured generation
across schema design, narrative insights, and the context audit; **OpenRouter** is
a configured fallback if only that key is set.

## How we Built it

**Stack:** 
1. Python
2. ClickHouse Cloud (via the `clickhouse-connect` client)
3. Langfuse for tracing
4. Anthropic/OpenRouter for LLM calls, 
5. Streamlit for UI

**Sample Analyses** 

**Read the Q3 2026 / July 2026 rows in every table below as incomplete, not
anomalous** — see the callout after the tables.

### 1. Quarterly session → purchase conversion rate

> Answers the question: WHat percentage of times in the past quarters did a session convert to a purchase?

```sql
WITH
    quarterly_sessions AS (
        SELECT
            toStartOfQuarter(timestamp) AS quarter_start,
            app_session_id,
            max(CASE WHEN _table = 'purchase_completed' THEN 1 ELSE 0 END) AS has_purchased
        FROM (
            SELECT app_session_id, timestamp, 'destination_card_clicked' AS _table FROM atlys.destination_card_clicked WHERE timestamp IS NOT NULL AND app_session_id != '' AND app_session_id IS NOT NULL
            UNION ALL
            SELECT app_session_id, timestamp, 'application_started' AS _table FROM atlys.application_started WHERE timestamp IS NOT NULL AND app_session_id != '' AND app_session_id IS NOT NULL
            UNION ALL
            SELECT app_session_id, timestamp, 'document_uploaded' AS _table FROM atlys.document_uploaded WHERE timestamp IS NOT NULL AND app_session_id != '' AND app_session_id IS NOT NULL
            UNION ALL
            SELECT app_session_id, timestamp, 'purchase_completed' AS _table FROM atlys.purchase_completed WHERE timestamp IS NOT NULL AND app_session_id != '' AND app_session_id IS NOT NULL
        )
        GROUP BY quarter_start, app_session_id
    )
SELECT
    quarter_start,
    uniq(app_session_id) AS total_sessions,
    sum(has_purchased) AS completed_purchases,
    round(sum(has_purchased) * 100.0 / nullIf(uniq(app_session_id), 0), 4) AS conversion_rate_pct
FROM quarterly_sessions
GROUP BY quarter_start
ORDER BY quarter_start ASC;
```

| quarter_start | total_sessions | completed_purchases | conversion_rate_pct |
|---|---:|---:|---:|
| 2026-01-01 | 440,496 | 3,228 | 0.7328% |
| 2026-04-01 | 560,520 | 3,824 | 0.6822% |
| 2026-07-01 | 14 | 2 | 14.2857% |

### 2. Quarterly revenue (currency-normalized) + applications started

> How many started applications converted to revenue in the past few quarters, and what was the average revenue per conversion?

```sql
WITH
    currency_subtotals AS (
        SELECT
            toStartOfQuarter(timestamp) AS quarter_start,
            coalesce(currency, 'UNKNOWN') AS currency,
            sum(coalesce(value, 0)) AS native_sum,
            count() AS conversion_count
        FROM atlys.purchase_completed
        WHERE timestamp IS NOT NULL
        GROUP BY quarter_start, currency
    ),
    normalized_to_usd AS (
        SELECT
            quarter_start,
            'USD (All Currencies Converted)' AS currency_group,
            sum(
                CASE currency
                    WHEN 'USD' THEN native_sum
                    WHEN 'INR' THEN native_sum * 0.012
                    WHEN 'AED' THEN native_sum * 0.272
                    WHEN 'GBP' THEN native_sum * 1.28
                    WHEN 'AUD' THEN native_sum * 0.65
                    WHEN 'SAR' THEN native_sum * 0.267
                    WHEN 'QAR' THEN native_sum * 0.274
                    WHEN 'OMR' THEN native_sum * 2.60
                    WHEN 'SGD' THEN native_sum * 0.75
                    ELSE native_sum * 1.0
                END
            ) AS total_converted_revenue_usd,
            sum(conversion_count) AS total_conversions
        FROM currency_subtotals
        GROUP BY quarter_start
    ),
    quarterly_applications AS (
        SELECT toStartOfQuarter(timestamp) AS quarter_start, count() AS applications_started_count
        FROM atlys.application_started
        WHERE timestamp IS NOT NULL
        GROUP BY quarter_start
    )
SELECT
    COALESCE(n.quarter_start, a.quarter_start) AS quarter_start,
    n.currency_group,
    n.total_converted_revenue_usd,
    n.total_conversions,
    round(n.total_converted_revenue_usd / nullIf(n.total_conversions, 0), 2) AS revenue_per_conversion,
    a.applications_started_count
FROM normalized_to_usd AS n
FULL OUTER JOIN quarterly_applications AS a ON n.quarter_start = a.quarter_start
ORDER BY quarter_start ASC;
```

| quarter_start | total_converted_revenue_usd | total_conversions | revenue_per_conversion | applications_started_count |
|---|---:|---:|---:|---:|
| 2026-01-01 | $207,380.92 | 3,228 | $64.24 | 68,089 |
| 2026-04-01 | $243,651.67 | 3,824 | $63.72 | 86,315 |
| 2026-07-01 | $89.78 | 2 | $44.89 | 9 |

### 3. Monthly revenue (currency-normalized) + applications started

> How many started applications converted to revenue in the past few months, and what was the average revenue per conversion? (Revenue converted to USD using the following static conversion rates

 ``` 
  'INR' ->  0.012
  'AED' -> 0.272
  'GBP' -> 1.28
  'AUD' -> 0.65
  'SAR' -> 0.267
  'QAR' -> 0.274
  'OMR' -> 2.60
  'SGD' -> 0.75
  ```

```sql
WITH
    currency_subtotals AS (
        SELECT
            toStartOfMonth(timestamp) AS month_start,
            coalesce(currency, 'UNKNOWN') AS currency,
            sum(coalesce(value, 0)) AS native_sum,
            count() AS conversion_count
        FROM atlys.purchase_completed
        WHERE timestamp IS NOT NULL
        GROUP BY month_start, currency
    ),
    normalized_to_usd AS (
        SELECT
            month_start,
            'USD (All Currencies Converted)' AS currency_group,
            sum(
                CASE currency
                    WHEN 'USD' THEN native_sum
                    WHEN 'INR' THEN native_sum * 0.012
                    WHEN 'AED' THEN native_sum * 0.272
                    WHEN 'GBP' THEN native_sum * 1.28
                    WHEN 'AUD' THEN native_sum * 0.65
                    WHEN 'SAR' THEN native_sum * 0.267
                    WHEN 'QAR' THEN native_sum * 0.274
                    WHEN 'OMR' THEN native_sum * 2.60
                    WHEN 'SGD' THEN native_sum * 0.75
                    ELSE native_sum * 1.0
                END
            ) AS total_converted_revenue_usd,
            sum(conversion_count) AS total_conversions
        FROM currency_subtotals
        GROUP BY month_start
    ),
    monthly_applications AS (
        SELECT toStartOfMonth(timestamp) AS month_start, count() AS applications_started_count
        FROM atlys.application_started
        WHERE timestamp IS NOT NULL
        GROUP BY month_start
    )
SELECT
    COALESCE(n.month_start, a.month_start) AS month_start,
    n.currency_group,
    n.total_converted_revenue_usd,
    n.total_conversions,
    round(n.total_converted_revenue_usd / nullIf(n.total_conversions, 0), 2) AS revenue_per_conversion,
    a.applications_started_count
FROM normalized_to_usd AS n
FULL OUTER JOIN monthly_applications AS a ON n.month_start = a.month_start
ORDER BY month_start ASC;
```

| month_start | total_converted_revenue_usd | total_conversions | revenue_per_conversion | applications_started_count |
|---|---:|---:|---:|---:|
| 2026-01-01 | $68,675.07 | 1,060 | $64.79 | 21,580 |
| 2026-02-01 | $62,935.26 | 1,001 | $62.87 | 21,211 |
| 2026-03-01 | $75,770.59 | 1,167 | $64.93 | 25,298 |
| 2026-04-01 | $84,247.20 | 1,290 | $65.31 | 26,280 |
| 2026-05-01 | $84,172.00 | 1,332 | $63.19 | 29,665 |
| 2026-06-01 | $75,232.52 | 1,202 | $62.59 | 30,370 |
| 2026-07-01 | $89.78 | 2 | $44.89 | 9 |


