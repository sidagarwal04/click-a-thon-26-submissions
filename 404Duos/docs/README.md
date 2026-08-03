# InsightIQ Documentation

InsightIQ is a ClickHouse-native analytics control plane for ad-tech event streams: a reactive cascade inside ClickHouse detects anomalies and attributes root causes; the Node API investigates in-process and narrates evidence-backed answers.

| Doc | What it covers |
|-----|----------------|
| [Architecture](./architecture.md) | System design, request paths, principles |
| [Submission architecture](../ARCHITECTURE.md) | Click-a-thon 1–2 pager (InMobi) |
| [Native pipeline](./pipeline.md) | ClickHouse cascade, seasonality baseline, noise-floored Z-score, multi-dim RCA |
| [Setup & run](./setup.md) | Local environment, ports, credentials |
| [Deploy (public demo)](./deploy.md) | Railway API (in-process RCA), Vercel web |
| [Data model](./data-model.md) | Tables, engines, query patterns |
| [API reference](./api-reference.md) | Engine + Node endpoints |
| [Product guide](./product-guide.md) | Dashboard, Alerts, Investigation, Chat |

Metrics glossary: [`../metrics_glossary.md`](../metrics_glossary.md)
