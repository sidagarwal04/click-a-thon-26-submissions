# Frontend

Lane D. React + Vite + TypeScript. Renders the Evidence Bundle — fixtures-first, no metric math here.

## Setup
```bash
pnpm install
pnpm dev   # http://localhost:5173
```

Renders `src/sample_bundle.json` immediately (mirror of `/fixtures/sample_bundle.json`). When the
backend is up, `investigate()` calls `POST /investigate` and falls back to the fixture on error.
Point at a different API with `VITE_API_URL`.

## Components (all in `src/components/`)
- `MetricTree` — the drill-down path, colored by status (hero).
- `DiagnosisCard` — headline delta + narrative.
- `FactorSplit` — requests / fill / eCPM contribution.
- `RuledOutPanel` — checked-and-cleared hypotheses with numbers.

Keep it lean — judges deprioritize polished UI. See `prompts/04-dashboard.md`.
