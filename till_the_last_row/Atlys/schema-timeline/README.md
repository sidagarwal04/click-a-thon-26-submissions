# Schema Timeline — "Schema changes over time" visualization

The Tracing & Visualization Layer (`PROBLEM_STATEMENT.md` §4) requires a visualization
layer that shows all three of:

1. **Schema changes over time**
2. **Agent-generated insights with confidence scores**
3. **Context layer diff / changelog**

This web app covers **all three**. It is tiny and self-contained (Python standard library
only — **no `pip install`, no npm, no build step**) and reconstructs everything *from
artifacts the pipeline already produces*, so it always reflects the real current state with
nothing to keep in sync.

## What it shows

- **Timeline** (newest first) interleaving:
  - **▣ schema commits** — every git commit that touched `Atlys/schemas/*.sql` / `*.metrics.json` / `*.insights.json`, with the spec(s) it changed.
  - **◇ context versions** — each `context_version` bump from `librechat/context_docs/log.md`, with an expandable **diff** (added / updated / contradiction, per file) and its trigger + source. *(→ requirement 3: context diff / changelog.)*
- **Schemas panel** — one expandable card per generated schema showing its header
  provenance (spec, validation, target), DDL objects (tables / MVs), `ORDER BY`,
  `PARTITION BY`, `TTL`, data-skipping indexes, deliberate **deviations**, the
  **metrics** it serves, this schema's **agent insights**, and its **git history**.
  *(→ requirement 1: schema changes over time.)*
- **Agent-generated insights panel** — every insight the Analytics Agent produced, as a
  card with a **numeric confidence score + bar** (High/Med/Low colour), evidence, why,
  segment breakdown, **known-issue chips (K1–K7)**, related metrics, and a **Langfuse
  trace link** ("no trace, no credit"). Includes a confidence-distribution summary and a
  graceful empty state until the first `*.insights.json` lands.
  *(→ requirement 2: agent-generated insights with confidence scores.)*
- **Headline stats** — schemas, tables, materialized views, metrics, insights, schema
  commits, context versions.

## The insights manifest (requirement 2)

The Analytics Agent, in pipeline mode, writes **one manifest per spec** alongside the
schema — `Atlys/schemas/{spec_name}.insights.json` — committed via the same
`clickhouse_git_write` MCP the Instrumentation Agent uses. See
`agents/analytics/skills/atlys-feature-insight/SKILL.md` **Step 8** for the full schema and
the H/M/L → numeric-confidence mapping rules. Shape (abridged):

```json
{
  "spec_name": "08_destination_card_clicked",
  "base_table": "atlys.destination_card_clicked",
  "generated_by": "analytics-agent",
  "trace_url": "https://<langfuse>/traces/<id>",
  "data_caveats": "os NULL coalesced; back-filled rows excluded",
  "insights": [
    {
      "id": "guest-browse-lower-conversion",
      "headline": "Guest-browse clicks convert ~38% worse than logged-in.",
      "confidence": 0.82, "confidence_label": "High",
      "confidence_reason": "large sample, stable, defined in context",
      "evidence": "guest 6.1% vs logged-in 9.8% (n=41,203)",
      "why": "guests hit the auth wall before application",
      "direction": "negative",
      "segments": [{ "segment": "is_guest_browse=1", "value": 6.1, "unit": "%", "n": 12840 }],
      "related_known_issues": [], "related_metrics": ["guest_browse_conversion"],
      "suggested_next_step": "A/B a guest checkout that defers auth"
    }
  ]
}
```

A worked example ships at `Atlys/schemas/08_destination_card_clicked.insights.json`.

## Where the data comes from (no new infrastructure)

| Source | Used for |
|---|---|
| `git log -- Atlys/schemas/` | when each schema changed, by whom, revision counts |
| each `.sql` header comment | spec / validation / target provenance + `[D#]` deviations |
| `.sql` DDL body | tables, MVs, ORDER BY, PARTITION BY, TTL, skip indexes |
| `*.metrics.json` manifest | metrics each schema serves |
| `*.insights.json` manifest | agent-generated insights + confidence scores + trace links |
| `librechat/context_docs/log.md` | context version bumps + per-file diff/changelog |

The model is rebuilt **live on every request** (see `timeline.py`), so committing a new
schema or bumping context is reflected on refresh.

## Run

```bash
# from the repo root
python3 Atlys/schema-timeline/server.py
# open http://127.0.0.1:8777
```

Config via env: `TIMELINE_HOST` (default `127.0.0.1`), `TIMELINE_PORT` (default `8777`).

### Structured CLI (no browser)

```bash
python3 Atlys/schema-timeline/timeline.py          # human-readable timeline
python3 Atlys/schema-timeline/timeline.py --json    # full JSON model
```

### Docker

```bash
docker build -t atlys-schema-timeline Atlys/schema-timeline
# mount the repo so it can read git history + schema files + context log
docker run --rm -p 8777:8777 -v "$PWD:/repo:ro" atlys-schema-timeline
```

Or via the bundled compose file:

```bash
docker compose -f Atlys/schema-timeline/docker-compose.yml up
```

## API

| Route | Returns |
|---|---|
| `GET /` | the dashboard (`static/index.html`) |
| `GET /api/timeline` | full JSON model — `totals`, `schemas`, `insights`, `events`, `context_versions` |
| `GET /api/schema/<spec_name>` | one schema's detail (incl. its insights) |
| `GET /api/insights` | flattened agent insights + confidence distribution + known-issues cited |
| `GET /healthz` | `{"ok": true}` |

## Files

- `timeline.py` — read-only model builder (git + files → JSON) and CLI.
- `server.py` — stdlib `http.server` app serving the API + static UI.
- `static/index.html` — single-file dashboard (inline CSS/JS, works offline).
- `Dockerfile`, `docker-compose.yml` — containerized run.
