/**
 * Reads persisted RCA reports from the shared directory RCA/app/report_store.py writes
 * to (docs/RCA_UI_TEMPLATE.md Step 2, Option A — JSON files, no ClickHouse client added
 * to this Node process). Falls back to the bundled sample reports only when the store
 * is empty, so the UI has something to show before any real alert has fired.
 */
const fs = require("fs");
const path = require("path");
const { REPORTS: SAMPLE_REPORTS } = require("./sample-reports");

const REPORTS_DIR =
  process.env.RCA_REPORTS_DIR || path.join(__dirname, "..", "data", "rca_reports");

function listReports() {
  let files = [];
  try {
    files = fs.readdirSync(REPORTS_DIR).filter((f) => f.endsWith(".json"));
  } catch (e) {
    if (e.code !== "ENOENT") throw e;
  }
  const persisted = files.map((f) =>
    JSON.parse(fs.readFileSync(path.join(REPORTS_DIR, f), "utf8")),
  );
  const all = persisted.length > 0 ? persisted : SAMPLE_REPORTS;
  return [...all].sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
}

function getReport(id) {
  return listReports().find((r) => r.id === id);
}

module.exports = { listReports, getReport, REPORTS_DIR };
