#!/usr/bin/env node
// Drive every filter through the real API path and report what each shape READ.
//
// Reads latency from ClickHouse's own summary header rather than wall-clock:
// wall-clock includes network from a laptop in India to ap-south-1 and would
// swamp the thing being measured. `chElapsedMs` and `readBytes` are what the
// rubric asks about, and they are server-side truth.
//
//   node scripts/bench_ui.mjs [label]
// Writes .run/bench-<label>.json so before/after can be diffed.

import { writeFileSync, mkdirSync } from "node:fs";

const API = process.env.API ?? "http://localhost:8787";
const LABEL = process.argv[2] ?? "run";
const RANGE = { from: process.env.FROM ?? "2026-07-26 05:30:00", to: process.env.TO ?? "2026-07-26 11:31:00" };

// One case per filter the dashboard exposes, plus the shapes it always issues.
const CASES = [
  { name: "series · no filter", path: "/api/series", q: {} },
  { name: "series · platform", path: "/api/series", q: { platform: "IPHONE" } },
  { name: "series · video_type", path: "/api/series", q: { video_type: "vod" } },
  { name: "series · audio_language", path: "/api/series", q: { audio_language: "en" } },
  { name: "series · subtitle_language", path: "/api/series", q: { subtitle_language: "und" } },
  { name: "series · player_version", path: "/api/series", q: { player_version: "1.8.2" } },
  { name: "series · platform+video_type", path: "/api/series", q: { platform: "IPHONE", video_type: "vod" } },
  { name: "series · 3 filters", path: "/api/series", q: { platform: "IPHONE", video_type: "vod", audio_language: "en" } },
  { name: "summary · no filter", path: "/api/summary", q: {} },
  { name: "summary · platform", path: "/api/summary", q: { platform: "ANDROID_PHONE" } },
  { name: "rollup · no filter", path: "/api/rollup", q: {} },
  { name: "breakdown · platform", path: "/api/breakdown/platform", q: {} },
  { name: "breakdown · content_id", path: "/api/breakdown/content_id", q: {} },
  { name: "breakdown · category", path: "/api/breakdown/category", q: {} },
  { name: "breakdown · app_version", path: "/api/breakdown/app_version", q: {} },
  { name: "facets", path: "/api/facets", q: {}, noRange: true },
];

const REPEATS = 5;
const pct = (xs, p) => xs.slice().sort((a, b) => a - b)[Math.min(xs.length - 1, Math.floor(xs.length * p))];

const results = [];
for (const c of CASES) {
  const qs = new URLSearchParams(c.noRange ? c.q : { ...RANGE, ...c.q }).toString();
  const url = `${API}${c.path}${qs ? `?${qs}` : ""}`;
  const ch = [], rows = [], bytes = [];
  for (let i = 0; i < REPEATS; i++) {
    const r = await fetch(url);
    if (!r.ok) { console.error(`  FAILED ${c.name}: ${r.status}`); break; }
    const j = await r.json();
    ch.push(j.stats.chElapsedMs); rows.push(j.stats.readRows); bytes.push(j.stats.readBytes);
  }
  if (!ch.length) continue;
  // Median, not mean: one cold read would otherwise dominate a 5-sample mean.
  results.push({
    name: c.name,
    ch_ms_p50: pct(ch, 0.5),
    ch_ms_max: Math.max(...ch),
    read_rows: rows[0],
    read_mib: +(bytes[0] / 1048576).toFixed(2),
  });
}

mkdirSync(".run", { recursive: true });
writeFileSync(`.run/bench-${LABEL}.json`, JSON.stringify(results, null, 2));

const pad = (s, n) => String(s).padEnd(n);
const rpad = (s, n) => String(s).padStart(n);
console.log(`\n  ${pad("shape", 30)} ${rpad("ch ms", 7)} ${rpad("rows read", 12)} ${rpad("MiB", 8)}`);
console.log(`  ${"-".repeat(60)}`);
for (const r of results) {
  console.log(`  ${pad(r.name, 30)} ${rpad(r.ch_ms_p50, 7)} ${rpad(r.read_rows.toLocaleString(), 12)} ${rpad(r.read_mib, 8)}`);
}
const totalMib = results.reduce((a, r) => a + r.read_mib, 0);
console.log(`  ${"-".repeat(60)}`);
console.log(`  ${pad("TOTAL", 30)} ${rpad(results.reduce((a, r) => a + r.ch_ms_p50, 0), 7)} ${rpad("", 12)} ${rpad(totalMib.toFixed(2), 8)}\n`);
