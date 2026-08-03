# InMobi RCA — incident view

One screen: incident list + metric tree + funnel +
diagnosis + ruled-out ledger + latency badge. Vite + React + TypeScript +
shadcn/ui + ECharts.

```bash
npm install
npm run dev   # http://localhost:3100
```

Currently fetches `public/diagnosis.json` (a hand-built fixture matching the
real `Investigation`/`Event` shape in `src/types.ts`, which mirrors the
engine's dataclasses field-for-field). To point it at the real API instead,
change the one URL constant in `src/useInvestigation.ts` to
`${API_BASE}/api/v1/investigation` — nothing else in the component tree needs
to change, since `GET /api/v1/investigation` serves that same JSON shape.
