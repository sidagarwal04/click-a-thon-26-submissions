/**
 * RCA report API — serves structured reports and filterable chart series.
 * Credentials stay on the RCA agent / ClickHouse side; this layer serves
 * pre-computed ledger JSON (+ mock series until wired to live reproduce queries).
 */
const express = require("express");
const cors = require("cors");
const { listReports, getReport } = require("./report-store");
const { fetchGlobalSeries, fetchSegmentSeries } = require("./live-series");
const {
  parseFilters,
  globalMetricSeries,
  segmentSeries,
  contributionBars,
  aggregateByBucket,
  aggregateSegment,
} = require("./mock-series");

const PORT = Number(process.env.RCA_API_PORT || 3002);
const app = express();
app.use(cors({ origin: true }));
app.use(express.json());

app.get("/health", (_req, res) => {
  res.json({ ok: true, reports: listReports().length });
});

app.get("/api/rca/reports", (_req, res) => {
  res.json(
    listReports().map((r) => ({
      id: r.id,
      title: r.title,
      created_at: r.created_at,
      status: r.status,
      metric_id: r.trigger.metric_id,
      window: r.trigger.window,
      peak_abs_z: r.trigger.peak_abs_z,
    })),
  );
});

app.get("/api/rca/reports/:id", (req, res) => {
  const report = getReport(req.params.id);
  if (!report) return res.status(404).json({ error: "report not found" });
  res.json(report);
});

app.post("/api/rca/reports/:id/global-series", async (req, res) => {
  const report = getReport(req.params.id);
  if (!report) return res.status(404).json({ error: "report not found" });
  try {
    const filters = parseFilters(req.body);
    const live = await fetchGlobalSeries(report, filters).catch((e) => {
      console.warn("global-series: agent unavailable, falling back to mock —", e.message);
      return null;
    });
    res.json(live ? aggregateByBucket(live, filters.granularity) : globalMetricSeries(report.id, filters));
  } catch (e) {
    res.status(400).json({ error: e.message });
  }
});

app.post("/api/rca/reports/:id/segment-series", async (req, res) => {
  const report = getReport(req.params.id);
  if (!report) return res.status(404).json({ error: "report not found" });
  try {
    const filters = parseFilters(req.body);
    const live = await fetchSegmentSeries(report, filters).catch((e) => {
      console.warn("segment-series: agent unavailable, falling back to mock —", e.message);
      return null;
    });
    res.json(live ? aggregateSegment(live, filters.granularity) : segmentSeries(report.id, filters));
  } catch (e) {
    res.status(400).json({ error: e.message });
  }
});

app.get("/api/rca/reports/:id/contributions", (req, res) => {
  const report = getReport(req.params.id);
  if (!report) return res.status(404).json({ error: "report not found" });
  res.json(contributionBars(report));
});

app.listen(PORT, () => {
  console.log(`RCA API listening on http://localhost:${PORT}`);
});
