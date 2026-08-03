import type { MetricDefinition } from "./types.js";

// Stand-in for `SELECT * FROM metric_definitions` until Postgres is
// provisioned — same shape either way. Reproduces exactly the 7 metrics
// currently hardcoded in sql/04_detect_and_populate.sql, as the equivalence
// check for the dynamic query generator (see scripts/prototype-registry.ts).
export const SEED_METRICS: MetricDefinition[] = [
  { id: "requests", label: "Requests", kind: "volume", numeratorId: "requests", scale: 1, requiresFill: false },
  { id: "revenue", label: "Revenue", kind: "volume", numeratorId: "revenue", scale: 1, requiresFill: false },
  { id: "fill_rate", label: "Fill Rate", kind: "ratio", numeratorId: "fills", denominatorId: "requests", scale: 1, requiresFill: false },
  { id: "render_rate", label: "Render Rate", kind: "ratio", numeratorId: "impressions", denominatorId: "fills", scale: 1, requiresFill: false },
  { id: "ctr", label: "CTR", kind: "ratio", numeratorId: "clicks", denominatorId: "impressions", scale: 1, requiresFill: false },
  { id: "ecpm", label: "eCPM", kind: "ratio", numeratorId: "revenue", denominatorId: "impressions", scale: 1000, requiresFill: false },
  { id: "rpr", label: "Revenue per Request", kind: "ratio", numeratorId: "revenue", denominatorId: "requests", scale: 1, requiresFill: false },
];
