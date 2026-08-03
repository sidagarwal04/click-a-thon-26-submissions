# The Aggregation Avengers

## Track
 SonyLIV

## Project
True CCU

## Team Members
- Ranganadh
- Vikas
- Venkat

## Github Handle
https://github.com/ranganadh2014/true_ccu

## What it does
True CCU answers "how many people are watching right now?" for SonyLIV at streaming scale — minute-grain concurrency with peak and peak-minute, sliceable by platform, content, language, country, app/player version and more, served from a pre-aggregated ClickHouse gold layer.

## Hosted Demo
It is currently local ready

## Demo Video
https://drive.google.com/drive/folders/1mqNeHMX3NmBxSm0OlKq6fSGIl8CviHTw?usp=drive_link

## Architecture
```
ch-hackathon-*.csv ──HTTP INSERT──► ClickHouse Cloud
                                     bronze_events / bronze_content
                                          │  10_language.sql
                                          │  20_silver.sql   (batch)
                                          ▼
                                     silver_events  (905,558 rows, row-complete)
                                          │  mv_gold_ccu_minute   (materialized view)
                                          ▼
                                     gold_ccu_minute (105,083 rows, 2.5 MiB)
                                          │
                    Express API :8787 ────┘
                          │
                    React dashboard :5173

  API + pipeline ──OTLP──► ClickStack container ──► HyperDX UI :8081
                            (its own ClickHouse, telemetry only)
```

## How we built it
- **Three layers, one job each** — bronze keeps the CSVs exactly as delivered, silver cleans them up (fixing timestamps, folding 41 messy language codes into 15, flagging duplicates instead of deleting them), and gold holds the ready-to-serve minute-by-minute counts.
- **Gold is built automatically** — materialized views roll every new silver row into gold as it arrives, so the dashboard never has to scan the raw events.
- **Peak is calculated, not stored** — we keep the count for every minute and take the maximum at query time, because the peak for "Android" and the peak for "Hindi" can happen at different minutes than the peak for both together.
- **Node + Express API** — a small read-only service in front of gold, which switches to a lighter no-filter table when the user hasn't picked any filters.
- **React + TypeScript dashboard** — charts drawn by hand in SVG, no chart library and nothing loaded from a CDN.
- **nginx in front** — serves the app and proxies the API, so ClickHouse credentials never reach the browser.
- **Docker Compose** — the whole demo comes up with one command.
- **ClickStack for observability** — the API and the pipeline send traces and metrics over OpenTelemetry, so each run leaves a visible trail in HyperDX.
- **Ready for the unseen day** — new columns are added with a plain `ALTER`, no reload and no change to the logic.

## How to run it
https://github.com/ranganadh2014/true_ccu/blob/main/CLAUDE_RUNBOOK.md
