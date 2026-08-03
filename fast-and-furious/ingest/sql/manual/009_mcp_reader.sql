-- 009_mcp_reader.sql — the restricted ClickHouse user the MCP server connects as.
--
-- RUN THIS AS AN ADMIN. It is deliberately NOT applied by `make schema`: sonyliv_svc
-- holds no ACCESS MANAGEMENT privilege (see SHOW GRANTS — there is no CREATE USER and no
-- GRANT OPTION), so the service user cannot create this account or hand out these rights.
-- That is the correct arrangement — a user that can mint users cannot be confined by
-- grants — but it does mean a human with admin rights has to run this file once.
--
--   clickhouse client --host <host> --secure --user <admin> --password \
--       --queries-file ingest/sql/009_mcp_reader.sql
--
-- WHY A SEPARATE USER AT ALL. The MCP server hands a language model the ability to run
-- SQL. The server does validate statements (see cmd/sonyliv-mcp/guard.go), but a
-- validator is a parser, and parsers are talked past. The grant is the boundary that
-- holds when the parser is wrong, so the two are layered deliberately and neither is
-- trusted alone. Everything below is SELECT — no INSERT, no ALTER, no CREATE, no DROP,
-- no dictionary reload, no access management.
--
-- WHAT IS DELIBERATELY NOT GRANTED, and why it matters more than what is. These six
-- objects carry user identity — `user_id`, `user_key`, `canonical_user_id`:
--
--     events_raw   events_clean   events_dedup
--     events_raw_to_clean_mv      fleet_sessions      session_intervals
--
-- The serving layer is aggregate-only: its narrowest row is one dimension combination in
-- one minute, and no row identifies a person. So the split below is not merely "the
-- tables the dashboards happen to use" — it is the line between per-person event data
-- and pre-aggregated counts, and the MCP user is on the aggregate side of it.
--
-- Also withheld: serving_concurrency_minute_staging, which exists only as the swap
-- target for REPLACE PARTITION and holds torn state mid-rebuild; and every system table,
-- so the model cannot read query text, part paths, or configuration.

CREATE USER IF NOT EXISTS sonyliv_mcp
    IDENTIFIED WITH sha256_password BY '__MCP_PASSWORD__'
    SETTINGS
        -- readonly = 2 permits SELECT and settings changes but no writes. It is a
        -- backstop only: the grants below already withhold every write privilege.
        readonly = 2,
        -- A runaway aggregation should fail loudly rather than evict the serving layer
        -- from page cache and slow the live dashboards down.
        max_execution_time = 30,
        max_result_rows = 100000,
        max_memory_usage = 4000000000,
        -- The rollups run continuously against this same service; an MCP query must not
        -- be able to starve them.
        priority = 5;

-- Pre-aggregated fact tables. The narrowest grain here is one dimension combination in
-- one time bucket.
GRANT SELECT ON sonyliv_prod.serving_concurrency_live   TO sonyliv_mcp;
GRANT SELECT ON sonyliv_prod.serving_concurrency_minute TO sonyliv_mcp;

-- Freshness and build history, so the model can tell "no viewers" from "not built yet".
-- Without these it will read a lagging layer as a traffic collapse.
GRANT SELECT ON sonyliv_prod.serving_watermark         TO sonyliv_mcp;
GRANT SELECT ON sonyliv_prod.serving_watermark_history TO sonyliv_mcp;

-- The read views. ClickHouse expands a normal view at parse time and checks privileges
-- against the underlying tables — these are INVOKER, not DEFINER (confirmed: no SQL
-- SECURITY clause on any of them). Granting the view alone would therefore fail, which
-- is exactly why the two fact tables above are granted as well.
GRANT SELECT ON sonyliv_prod.serving_live_total      TO sonyliv_mcp;
GRANT SELECT ON sonyliv_prod.serving_live_content    TO sonyliv_mcp;
GRANT SELECT ON sonyliv_prod.serving_minute_current  TO sonyliv_mcp;
GRANT SELECT ON sonyliv_prod.serving_drop_signal     TO sonyliv_mcp;

-- Title and category lookup. dictGet ONLY — the dictionary holds its own source
-- credentials (SOURCE(CLICKHOUSE(... TABLE 'content_current' USER 'sonyliv_svc' ...))),
-- so it resolves titles without the caller ever being able to read content_current or
-- content_dim directly.
GRANT dictGet ON sonyliv_prod.content_dict TO sonyliv_mcp;

-- Verification. Run as the new user; every line must hold.
--
--   SELECT currentUser();                                        -- sonyliv_mcp
--   SELECT count() FROM sonyliv_prod.serving_minute_current;     -- succeeds
--   SELECT count() FROM sonyliv_prod.events_clean;               -- ACCESS_DENIED
--   SELECT count() FROM sonyliv_prod.session_intervals;          -- ACCESS_DENIED
--   SELECT count() FROM system.query_log;                        -- ACCESS_DENIED
--   INSERT INTO sonyliv_prod.serving_watermark VALUES (...);     -- ACCESS_DENIED
--
-- cmd/sonyliv-mcp/check-grants.sh runs exactly these and reports pass/fail per line,
-- including the negative cases — an allowlist is only proven by what it refuses.
