// One-shot HyperDX provisioner (run by the hyperdx-seed compose service via mongosh).
//
// HyperDX has no official env-var provisioning for connections/sources/dashboards —
// they are plain Mongo documents, so we seed them directly (shapes validated against
// a UI-configured instance; see git history of the clickstack exploration).
//
// Waits for the first HyperDX user registration (team doc) — visit :8081, register,
// and within ~5s the connection, three sources, and the RCA Overview dashboard exist.
// Idempotent: everything is matched by name; re-runs never duplicate or clobber.

const dbh = db.getSiblingDB("hyperdx");

print("hyperdx-seed: waiting for first HyperDX user registration…");
while (dbh.teams.countDocuments() === 0) {
  sleep(5000);
}
const team = dbh.teams.findOne()._id;
const user = dbh.users.findOne() ? dbh.users.findOne()._id : team;
print("hyperdx-seed: team found, provisioning…");

// ── connection: the shared stack ClickHouse ──────────────────────────────────
const CH_HOST = process.env.HYPERDX_CH_HOST || "http://clickhouse:8123";
const CH_USER = process.env.HYPERDX_CH_USER || "rca_rw";
const CH_PASS = process.env.HYPERDX_CH_PASSWORD || "rca_rw_dev";
let conn = dbh.connections.findOne({ name: "Stack ClickHouse" });
if (!conn) {
  const r = dbh.connections.insertOne({
    team: team, name: "Stack ClickHouse",
    host: CH_HOST, username: CH_USER, password: CH_PASS,
    createdAt: new Date(), updatedAt: new Date(), __v: 0,
  });
  conn = { _id: r.insertedId };
  print("hyperdx-seed: connection created");
}

// ── sources ──────────────────────────────────────────────────────────────────
// NOTE: mongosh ObjectIds have NO .str (that was the legacy mongo shell) —
// always .toHexString(), otherwise tile source ids become undefined.
function upsertSource(name, dbName, table, tsCol, defaultSelect) {
  const found = dbh.sources.findOne({ name: name, team: team });
  if (found) return found._id;
  const r = dbh.sources.insertOne({
    kind: "log", name: name,
    from: { databaseName: dbName, tableName: table },
    timestampValueExpression: tsCol,
    defaultTableSelectExpression: defaultSelect || tsCol,
    connection: conn._id, team: team,
    querySettings: [], materializedViews: [],
    highlightedRowAttributeExpressions: [], highlightedTraceAttributeExpressions: [],
    disabled: false, createdAt: new Date(), updatedAt: new Date(), __v: 0,
  });
  print("hyperdx-seed: source " + name + " created");
  return r.insertedId;
}
const SRC_METRICS = upsertSource("Ad Metrics", "rca", "metrics_hourly_by_dim",
  "window_start", "window_start, dimension, value, requests, fills, impressions, clicks, revenue").toHexString();
const SRC_INCID = upsertSource("Incidents", "rca", "incidents",
  "window_start", "window_start, metric, scope, status").toHexString();
upsertSource("Ad Events", "rca", "ad_events_enriched",
  "event_time", "event_time, os_version, region, ad_format, is_filled, is_impression, revenue");

// Traces source (kind: trace) over the collector's output — HyperDX only creates
// its default otel sources in some onboarding paths, so we guarantee it here.
if (!dbh.sources.findOne({ name: "Traces", team: team })) {
  dbh.sources.insertOne({
    kind: "trace", name: "Traces",
    from: { databaseName: "default", tableName: "otel_traces" },
    timestampValueExpression: "Timestamp",
    durationExpression: "Duration", durationPrecision: 9,
    traceIdExpression: "TraceId", spanIdExpression: "SpanId",
    parentSpanIdExpression: "ParentSpanId", spanNameExpression: "SpanName",
    spanKindExpression: "SpanKind", statusCodeExpression: "StatusCode",
    statusMessageExpression: "StatusMessage", serviceNameExpression: "ServiceName",
    resourceAttributesExpression: "ResourceAttributes",
    eventAttributesExpression: "SpanAttributes",
    implicitColumnExpression: "SpanName",
    defaultTableSelectExpression: "Timestamp, ServiceName, StatusCode, SpanName",
    connection: conn._id, team: team,
    querySettings: [], materializedViews: [],
    highlightedRowAttributeExpressions: [], highlightedTraceAttributeExpressions: [],
    disabled: false, createdAt: new Date(), updatedAt: new Date(), __v: 0,
  });
  print("hyperdx-seed: source Traces created (kind: trace)");
}

// ── dashboard: RCA Overview (insert once; never clobber user edits) ──────────
if (!dbh.dashboards.findOne({ name: "RCA Overview", team: team })) {
  const G = "dimension = 'global' AND value = 'all'";
  function tile(id, x, y, w, h, name, expr, where, groupBy) {
    const cfg = {
      name: name,
      select: [{ aggFn: "none", aggCondition: "", aggConditionLanguage: "lucene", valueExpression: expr }],
      where: where, whereLanguage: "sql",
      displayType: "line", granularity: "auto", alignDateRangeToGranularity: true,
      source: SRC_METRICS,
    };
    if (groupBy) cfg.groupBy = groupBy;
    return { id: id, x: x, y: y, w: w, h: h, config: cfg };
  }
  const tiles = [
    tile("rq01requests",  0,  0, 12, 9, "Requests",                "sum(requests)", G, null),
    tile("rq02fillrate", 12,  0, 12, 9, "Fill rate",               "sum(fills)/sum(requests)", G, null),
    tile("rq03revenue",   0,  9,  6, 8, "Revenue",                 "sum(revenue)", G, null),
    tile("rq10rpr",       6,  9,  6, 8, "RPR (rev/request) — monetization", "sum(revenue)/sum(requests)", G, null),
    tile("rq04ecpm",     12,  9,  6, 8, "eCPM",                    "sum(revenue)/sum(impressions)*1000", G, null),
    tile("rq05ctr",      18,  9,  6, 8, "CTR",                     "sum(clicks)/sum(impressions)", G, null),
    tile("rq06fillos",    0, 17, 12, 9, "Fill rate by os_version", "sum(fills)/sum(requests)", "dimension = 'os_version'", "value"),
    tile("rq07reqreg",   12, 17, 12, 9, "Requests by region",      "sum(requests)", "dimension = 'region'", "value"),
    tile("rq08ecpmct",    0, 26, 12, 9, "eCPM by campaign_type",   "sum(revenue)/sum(impressions)*1000", "dimension = 'campaign_type' AND value != '(none)'", "value"),
    tile("rq09render",   12, 26, 12, 9, "Render rate",             "sum(impressions)/sum(fills)", G, null),
    // bottom row: what the system concluded (rca.incidents, written by sweep/runner)
    {
      id: "inc01timeline", x: 0, y: 35, w: 10, h: 9,
      config: {
        name: "Incidents over time (by status)",
        select: [{ aggFn: "count", aggCondition: "", aggConditionLanguage: "lucene", valueExpression: "" }],
        where: "", whereLanguage: "sql",
        displayType: "line", granularity: "1 day", alignDateRangeToGranularity: true,
        groupBy: "status", source: SRC_INCID,
      },
    },
  ];
  dbh.dashboards.insertOne({
    name: "RCA Overview", tiles: tiles, team: team,
    tags: [], filters: [], savedFilterValues: [], containers: [],
    createdBy: user, updatedBy: user, provisioned: false,
    createdAt: new Date(), updatedAt: new Date(), __v: 0,
  });
  print("hyperdx-seed: RCA Overview dashboard created (" + tiles.length + " tiles)");
}

print("hyperdx-seed: done — open the dashboard and set the time range to the data window");
