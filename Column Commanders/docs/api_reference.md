# API Reference
## Anomaly Detection Service

Base URL: `http://localhost:8080`

---

## POST /api/v2/detect/historical

Runs 10-minute discovery from `metrics_global_1m`, hourly discovery from
`metrics_global_1h`, candidate persistence, and episode correlation. When
`investigate` is true, selected episodes are returned with
`verification_status: "investigating"`; bounded LLM investigation, canonical
verification, and narration continue asynchronously.

The range is `[start, end)`. Omitting both uses the trailing configured lookback
relative to the ClickHouse watermark.

```json
{
  "start": "2026-06-01T00:00:00Z",
  "end": "2026-07-06T00:00:00Z",
  "investigate": true
}
```

The response contains actionable `candidates` and correlated `episodes`. For
historical runs, isolated signals are retained in ClickHouse for audit but are
suppressed unless they persist across at least three nearby candidate windows.
Agreement at both 10-minute and hourly resolutions increases confidence but
does not replace the persistence requirement. The response reports omitted totals
as `suppressed_candidate_count` and `suppressed_episode_count`. Poll
`GET /api/v2/episodes/{id}` for episodes marked `investigating`. A verified
episode contains `root_cause_dimension`, `root_cause_segment`, canonical
`evidence`, and a structured JSON `narration`.

Before the LLM reasons, the investigation pipeline runs a deterministic sweep
across ad format, app, app attributes, geographic/device attributes, and—when
coverage is valid—advertiser attributes. Each segment uses the same prior
same-period baseline as canonical verification. Contribution is calculated in
the affected metric's additive units (missing fills for fill rate, missing
impressions for render rate, click impact for CTR, and revenue impact for
revenue/eCPM/RPR). The LLM can query further to distinguish close candidates,
but only a canonically verified dimension and segment can be narrated.

---

## POST /api/v2/detect/realtime

Runs the latest complete 5-minute severe path and 10-minute standard path. The
10-minute path is emitted after `DETECTION_PERSISTENCE_CHECKS` consecutive runs.

```json
{
  "investigate": true
}
```

An optional RFC3339 `anchor` can be supplied for replay/testing. Otherwise the
watermark is used, with `DETECTION_LATENESS_ALLOWANCE` subtracted.

---

## GET /api/v2/episodes

Lists durable v2 episodes stored in ClickHouse.

## GET /api/v2/episodes/{id}

Returns one v2 episode. During background investigation this endpoint serves
the latest in-process evidence immediately; terminal episode state is persisted
to ClickHouse as each investigation finishes. Verified evidence is rehydrated
from `evidence_records` after service restarts.

---

## Compatibility API

The `/api/v1` endpoints below remain available for the original hourly/daily
detector and deterministic drilldown. When `NARRATOR_ENABLED=true`, completed
drilldowns are passed to the LLM narrator for a final evidence-grounded verdict.

---

## POST /api/v1/detect

Trigger detection for an explicit or auto-resolved time window.

V1 supports `revenue`, `fill_rate`, `ecpm`, `ctr`, and `requests`. Unsupported metric
filters return `400` rather than an empty successful result.

**Request** (all fields optional):
```json
{
  "window_end":  "2026-07-05T14:00:00Z",
  "window_size": "1h",
  "metric":      "fill_rate"
}
```

**Response 200:**
```json
{
  "window": { "start": "...", "end": "...", "duration": "1h", "grain": "hourly" },
  "anomaly_detected": true,
  "anomalies": [{ "metric": "fill_rate", "z_score": -162.9, "severity": "critical", ... }],
  "incidents": [{ "id": "...", "status": "active" }],
  "execution_time_ms": 312
}
```

---

## POST /api/v1/detect/auto

Same as `/detect` with no body. Window auto-resolved from watermark.

---

## GET /api/v1/incidents

List all active incidents.

**Response 200:**
```json
{ "incidents": [{ "id": "...", "metric": "fill_rate", "severity": "critical", "drilldown_ready": true }] }
```

---

## GET /api/v1/incidents/{id}

Get full incident details including drilldown.

**Response 200** (drilldown complete):
```json
{
  "incident": { "id": "...", "metric": "fill_rate", "z_score": -162.9 },
  "drilldown": {
    "guilty_factor": "fill_rate",
    "culprit_segments": [{ "dimension": "os_version", "segment": "Android 15", "contribution_pct": 0.987 }],
    "ruled_out_dimensions": ["ad_format", "region"]
  },
  "narration": {
    "headline": "Fill rate drop attributed to os_version=Android 15",
    "classification": "single-segment",
    "verdict": "Single-segment attribution supported by hold-out verification",
    "summary": "...",
    "business_impact": "...",
    "root_cause": "...",
    "evidence": ["..."],
    "ruled_out": ["..."],
    "confidence": 0.91,
    "next_actions": ["..."]
  },
  "queries_run": 12
}
```

`narration` is `null` when narration is disabled or the LLM call fails. The
deterministic `drilldown` remains available in either case.

**Response 202** (drilldown in progress):
```json
{ "incident": { ... }, "drilldown": null, "message": "incident analysis in progress, retry in a few seconds" }
```

**Response 404:** `{ "error": "incident not found" }`

---

## GET /health

```json
{
  "status": "ok",
  "clickhouse": { "ok": true },
  "data_anchor": "2026-07-05T23:59:59Z",
  "active_incidents": 0
}
```
