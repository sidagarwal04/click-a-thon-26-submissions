# Dual-resolution detection runbook

## First start with existing historical data

Materialized views only process new inserts. For an existing `ad_events` table,
enable the guarded one-time backfill:

```env
DETECTION_AUTO_BACKFILL=true
```

Start the service with `make run`. Each v2 aggregate is backfilled only if it is
completely empty. After the first successful start, set the option back to
`false`.

## Enable investigation and narration

```env
LLM_ENABLED=true
OPENAI_API_KEY=...
OPENAI_BASE_URL=https://api.openai.com/v1
INVESTIGATION_MODEL=gpt-5.6-sol
NARRATOR_MODEL=gpt-5.6-sol
```

Both models use the OpenAI Responses API with strict structured outputs. The API
key is never included in formatted configuration or telemetry.

## Historical discovery

```bash
curl -sS -X POST http://localhost:8080/api/v2/detect/historical \
  -H 'Content-Type: application/json' \
  -d '{
    "start":"2026-06-01T00:00:00Z",
    "end":"2026-07-06T00:00:00Z",
    "investigate":true
  }'
```

Use `"investigate": false` to run only deterministic discovery, persistence, and
episode correlation without spending model tokens.

Historical discovery returns only confidence-qualified episodes: a signal must
persist across at least three nearby candidate windows. Agreement between the
10-minute and hourly scans raises confidence but does not replace persistence.
Isolated candidates remain stored for audit. CTR uses the separate
`DETECTION_ZSCORE_CTR_THRESHOLD` because its lower event count makes it noisier
than rate and volume metrics.

With `"investigate": true`, discovery returns immediately. Episodes selected for
the bounded agent have `verification_status: "investigating"`. Poll an episode
until it becomes `verified`, `insufficient_evidence`, or `error`:

```bash
curl -sS http://localhost:8080/api/v2/episodes/EPISODE_ID
```

Verified responses include canonical evidence and the narrator's structured
JSON narrative.

Investigation first performs a deterministic, lossless dimension sweep with
the raw fact time range filtered before `ANY LEFT JOIN` dictionary lookups. This
prevents missing dimension rows from silently dropping requests. The sweep
ranks segments with metric-specific contribution math, then the LLM rules out
alternatives and canonical verification re-runs the selected dimension and
segment. Narration explicitly names the verified culprit; it never asks an
operator to localize the anomaly by hand.

## Real-time detection

Trigger once:

```bash
curl -sS -X POST http://localhost:8080/api/v2/detect/realtime \
  -H 'Content-Type: application/json' \
  -d '{"investigate":true}'
```

Or enable the recurring one-minute runner:

```env
DETECTION_SCHEDULER_ENABLED=true
DETECTION_CHECK_FREQUENCY=1m
```

## Safety model

- The ClickHouse connection database controls table routing; SQL contains no
  deployment-specific database name.
- Agent SQL permits only `SELECT`, `WITH`, or `EXPLAIN` over approved tables.
- Every agent query requires bounded episode timestamps and a final `LIMIT`.
- The application appends execution-time, rows-read, bytes-read, and result-row
  caps and rejects external table functions or mutating SQL.
- Ratios are always recalculated as `sum(numerator)/sum(denominator)`.
- Canonical verification, not the LLM, decides whether evidence is accepted.
