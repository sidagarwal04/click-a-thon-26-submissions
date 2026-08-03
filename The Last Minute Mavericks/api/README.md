# RCA Engine API — wire the frontend to the REAL engine

Serves the live investigation bundle from ClickHouse so the UI stops using fixtures.

## Run
```bash
uvicorn api.server:app --host 0.0.0.0 --port 8077     # then open http://localhost:8077/docs
```
Needs `.env` (ClickHouse + LLM). The scan is computed once on startup (~15s, incl. LLM narration)
and cached; `POST /refresh` recomputes. CORS is open for local dev.

## Endpoints
| Method | Path | Returns |
|---|---|---|
| GET | `/health` | `{status, db, investigations}` |
| GET | `/scan` | the full bundle `{scan_summary, investigations:[...]}` |
| GET | `/investigations` | **just the incident list — what the UI `incidents()` renders** |
| GET | `/investigation/{id}` | one incident |
| POST | `/refresh` | recompute live from ClickHouse |

## Shape of one investigation (what the UI consumes)
```json
{
  "id": "inv_fill_rate_2026-06-28",
  "metric": "fill_rate",
  "window": ["2026-06-28","2026-06-30"],
  "verdict": "LOCALIZED_2D",
  "headline": "fill_rate -50.6% at os_version=iOS 18.1 × region=APAC",
  "culprit": {"dimension":"os_version×region","segment":"os_version=iOS 18.1 × region=APAC","deviation_pct":-50.6},
  "decomposition": [{"factor":"fill_rate","deviation_pct":-50.6,"verdict":"driver"}, ...],
  "ruled_out": [{"segment":"os_version=iOS 18.1","deviation_pct":-12.5,"why":"dilution — explained by ..."}, ...],
  "evidence": [{"id":"ev_1","label":"...","value":0.3879,"sql":"SELECT ...","query_id":"..."}, ...],
  "diagnosis": {"diagnosis":"fill_rate fell to 0.3879 ...","citations":["ev_2"],"source":"llm+validator"}
}
```

## For the UI (Naman)
Point the `incidents()` swap point at `GET /investigations`. Field-name alignment with the UI's
golden fixture (`hypotheses`/`evidence_store`) is the one open item — flag any renames you need and
we map them server-side in ~10 min.
