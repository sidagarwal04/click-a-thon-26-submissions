// One-time/rarely-changed setup, run locally: `npm run setup:local`.
// Needs CLICKHOUSE_URL/CLICKHOUSE_USER/CLICKHOUSE_PASSWORD in the environment.
import { runSetup } from "../lib/incremental/tick.js";

const results = await runSetup();
for (const r of results) {
  const status = r.ok ? "OK" : `FAILED — ${r.error}`;
  console.log(`${r.step}: ${status} (${r.statements} statements, ${r.elapsedMs}ms)`);
}
