# Submission map — Jalagaara Gang · InMobi track

| Requirement | Where |
|---|---|
| Source code (3-stage pipeline) | [`code/`](code/) — `backend/rca/` detection · decomposition · drilldown |
| README with run steps + demo link + architecture | [`README.md`](README.md) |
| Architecture doc (1–2 pages + diagram) | [`architecture/`](architecture/) |
| Demo video (2–3 min) | [`demo/README.md`](demo/README.md) |
| Pitch deck (PDF) | [`pitch-deck.pdf`](pitch-deck.pdf) |
| Unseen incident results | [`unseen_incident_results/`](unseen_incident_results/) |
| Drill-down runs in ClickHouse, not the LLM | `code/backend/rca/drilldown.py` — every level is a `GROUP BY` |
| OSS stack integration | Langfuse (self-hosted) + LibreChat — `code/backend/narrator/tracing.py`, `code/librechat.yaml` |
| LLM provider + rationale | [`README.md`](README.md) — narration only, never analysis |

The organizers' `InMobi/data/ad_events.parquet` (98 MB) is omitted from `code/` — it exceeds
GitHub's per-file limit and is the provided dataset, not our work. Everything else is included.
