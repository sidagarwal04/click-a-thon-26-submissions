import { useEffect, useMemo, useState, type CSSProperties, type ReactNode } from "react";
import { Title, Text, Button, Select } from "@clickhouse/click-ui";
import {
  Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { chQuery, chScalar } from "./lib/ch";

const ACCENT = "#faff69"; // ClickHouse yellow
const BG = "#1b1b1d", CARD = "#242427", LINE = "#34343a", MUTED = "#a0a0a8";
const LIBRECHAT_URL = "http://localhost:3080"; // the LibreChat + ClickHouse MCP service
const CONTENT = "sonyliv.content_raw";   // content metadata, joined on content_id
const DIM_MINUTE = "sonyliv.dim_minute"; // (dim, value, minute) marginals: total + single-dim
const CONC = "sonyliv.concurrency_1m";   // dims-first full grain: multi-dim / content combos
const OPT_LIMIT = 150; // options per dropdown, ranked by concurrency (covers all real viewership)

// ALL documented dataset filter dimensions (spec.md).
//   kind:"direct"  -> a column on hist_minute_full (equality filter)
//   kind:"content" -> a content attribute; hist stores only content_id, so we resolve it by
//                     joining content_raw. (dictGet works in SELECT but mis-evaluates to 0 as a
//                     WHERE predicate on this table — the semi-join is the correct, spec-intended path.)
const DIMS = [
  { key: "platform",          label: "Platform",   kind: "direct" },
  { key: "app_version",       label: "App version",kind: "direct" },
  { key: "country",           label: "Country",    kind: "direct" },
  { key: "audio_language",    label: "Audio",      kind: "direct" },
  { key: "subtitle_language", label: "Subtitle",   kind: "direct" },
  { key: "player_version",    label: "Player",     kind: "direct" },
  { key: "video_resolution",  label: "Resolution", kind: "direct" },
  { key: "video_type",        label: "Video type", kind: "direct" },
  { key: "title",             label: "Title",      kind: "content", col: "title" },
  { key: "show_name",         label: "Show",       kind: "content", col: "show_name" },
  { key: "category",          label: "Category",   kind: "content", col: "category" },
] as const;
type Dim = (typeof DIMS)[number];
type DimKey = Dim["key"];

const esc = (v: string) => v.replace(/'/g, "''");
// Options for a dropdown, ranked by concurrency. Content dims join content_raw.
const optionsSQL = (d: Dim) =>
  d.kind === "content"
    ? `SELECT c.${(d as any).col} v, sum(h.n_sessions) s FROM ${CONC} h
       INNER JOIN ${CONTENT} c ON h.content_id = c.content_id
       GROUP BY v HAVING v != '' ORDER BY s DESC LIMIT ${OPT_LIMIT}`
    : `SELECT value v, sum(n_sessions) s FROM ${DIM_MINUTE}
       WHERE dim = '${d.key}' GROUP BY v HAVING v != '' ORDER BY s DESC LIMIT ${OPT_LIMIT}`;
// WHERE fragment for one selected dimension. Content dims -> semi-join on content_raw.
const whereFrag = (d: Dim, val: string) =>
  d.kind === "content"
    ? ` AND content_id IN (SELECT content_id FROM ${CONTENT} WHERE ${(d as any).col} = '${esc(val)}')`
    : ` AND ${d.key} = '${esc(val)}'`;
const initStr = () => Object.fromEntries(DIMS.map((d) => [d.key, "all"])) as Record<DimKey, string>;
const initArr = () => Object.fromEntries(DIMS.map((d) => [d.key, []])) as Record<DimKey, string[]>;

export default function App() {
  const [opts, setOpts] = useState<Record<DimKey, string[]>>(initArr);
  const [sel, setSel] = useState<Record<DimKey, string>>(initStr);
  const [day0, setDay0] = useState<string | null>(null);
  const [win, setWin] = useState<{ start: string; end: string } | null>(null);
  const [curve, setCurve] = useState<{ t: string; c: number }[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  const where = useMemo(
    () =>
      DIMS.filter((d) => sel[d.key] !== "all")
        .map((d) => whereFrag(d, sel[d.key]))
        .join(""),
    [sel]
  );

  // Route to the smallest covering serving table: no filter -> dim_minute(_total);
  // one direct dim -> dim_minute(dim,value); multi-dim / content -> concurrency_1m (dims-first).
  const sql = useMemo(() => {
    if (!win) return "";
    const active = DIMS.filter((d) => sel[d.key] !== "all");
    const range = `minute >= toDateTime('${win.start}') AND minute < toDateTime('${win.end}')`;
    const head = "SELECT toStartOfMinute(minute) AS t, sum(n_sessions) AS concurrency\nFROM";
    const tail = "GROUP BY t\nORDER BY t";
    if (active.length === 0)
      return `${head} ${DIM_MINUTE}\nWHERE dim = '_total' AND ${range}\n${tail}`;
    if (active.length === 1 && active[0].kind === "direct")
      return `${head} ${DIM_MINUTE}\nWHERE dim = '${active[0].key}' AND value = '${esc(sel[active[0].key])}' AND ${range}\n${tail}`;
    return `${head} ${CONC}\nWHERE ${range}${where}\n${tail}`;
  }, [win, where, sel]);

  // bootstrap: peak day (default window) + filter options (ranked by concurrency)
  useEffect(() => {
    (async () => {
      try {
        const day = await chScalar(
          `SELECT toString(toStartOfDay(argMax(minute, c))) FROM (SELECT minute, sum(n_sessions) c FROM ${DIM_MINUTE} WHERE dim='_total' GROUP BY minute)`,
          "bootstrap"
        );
        const start = day || "2026-07-31 00:00:00";
        setDay0(start);
        setWin({ start, end: shift(start, 1440) });
        const lists = await Promise.all(
          DIMS.map((d) =>
            chQuery(optionsSQL(d), "options").then((rows) => [d.key, rows.map((r) => String(r.v))] as const)
          )
        );
        setOpts(Object.fromEntries(lists) as Record<DimKey, string[]>);
      } catch (e: any) {
        setErr(String(e.message || e));
      }
    })();
  }, []);

  useEffect(() => {
    if (!sql) return;
    setLoading(true); setErr(null);
    chQuery(sql, "curve")
      .then((rows) => setCurve(rows.map((r) => ({ t: String(r.t), c: Number(r.concurrency) }))))
      .catch((e) => setErr(String(e.message || e)))
      .finally(() => setLoading(false));
  }, [sql]);

  const peak = curve.reduce((m, p) => Math.max(m, p.c), 0);
  const avg = curve.length ? Math.round(curve.reduce((s, p) => s + p.c, 0) / curve.length) : 0;
  const peakPoint = curve.find((p) => p.c === peak)?.t;
  const peakAt = peakPoint?.slice(11, 16) ?? "—";
  const activeFilters = DIMS.filter((d) => sel[d.key] !== "all").length;

  return (
    <div style={{ background: BG, minHeight: "100vh", color: "#eee", fontFamily: "Inter, system-ui, sans-serif", padding: 24 }}>
      <div style={{ maxWidth: 1160, margin: "0 auto" }}>
        {/* header + LibreChat link */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 16 }}>
          <div>
            <Title type="h1" size="lg">SonyLIV — Foreground Concurrency</Title>
            <Text color="muted">
              Truly-active concurrent viewers per minute (backgrounded / paused / heartbeat-gap excluded).
              Source <code>{DIM_MINUTE}</code> · <code>{CONC}</code>
            </Text>
          </div>
          <a href={LIBRECHAT_URL} target="_blank" rel="noreferrer" title="Natural-language layer (LibreChat + ClickHouse MCP)"
            style={{ background: ACCENT, color: "#111", fontWeight: 600, padding: "9px 14px", borderRadius: 8, textDecoration: "none", whiteSpace: "nowrap" }}>
            💬 Ask the data ↗
          </a>
        </div>

        {/* time window */}
        <div style={{ display: "flex", gap: 12, alignItems: "flex-end", flexWrap: "wrap", marginTop: 18 }}>
          <Field label="From (UTC)">
            <input type="datetime-local" step={60} value={win ? toLocal(win.start) : ""}
              onChange={(e) => win && e.target.value && setWin({ ...win, start: fromLocal(e.target.value) })} style={inputStyle} />
          </Field>
          <Field label="To (UTC)">
            <input type="datetime-local" step={60} value={win ? toLocal(win.end) : ""}
              onChange={(e) => win && e.target.value && setWin({ ...win, end: fromLocal(e.target.value) })} style={inputStyle} />
          </Field>
          <Button type="secondary" disabled={!peakPoint}
            onClick={() => peakPoint && setWin({ start: shift(peakPoint, -60), end: shift(peakPoint, 60) })}>
            Zoom to peak
          </Button>
          <Button type="secondary" disabled={!day0}
            onClick={() => day0 && setWin({ start: day0, end: shift(day0, 1440) })}>
            Full day
          </Button>
        </div>

        {/* dimension filters — all 11 documented dataset dimensions */}
        <div style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "flex-end", margin: "18px 0 2px" }}>
          {DIMS.map((d) => (
            <div key={d.key} style={{ minWidth: 172 }}>
              <Select label={d.label} value={sel[d.key]} onSelect={(v: string) => setSel((s) => ({ ...s, [d.key]: v }))}>
                <Select.Item value="all">All</Select.Item>
                {opts[d.key].map((o) => (<Select.Item key={o} value={o}>{o}</Select.Item>))}
              </Select>
            </div>
          ))}
          <Button type={activeFilters ? "primary" : "secondary"} onClick={() => setSel(initStr())}>
            Reset{activeFilters ? ` (${activeFilters})` : ""}
          </Button>
        </div>
        <Text color="muted" size="sm">
          Title / Show / Category resolve by joining <code>content_raw</code> on <code>content_id</code>;
          each list shows the top {OPT_LIMIT} values by concurrency.
        </Text>

        {/* KPIs */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 14, margin: "16px 0 18px" }}>
          <Kpi label="Peak concurrency" value={peak.toLocaleString()} accent />
          <Kpi label="Peak at (UTC)" value={peakAt} />
          <Kpi label="Avg / minute" value={avg.toLocaleString()} />
        </div>

        {/* curve */}
        <div style={{ background: CARD, border: `1px solid ${LINE}`, borderRadius: 10, padding: 16, height: 380 }}>
          {err ? (
            <Text color="danger">{err}</Text>
          ) : loading && !curve.length ? (
            <div style={{ display: "grid", placeItems: "center", height: "100%" }}><Text color="muted">Loading…</Text></div>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={curve} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="g" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={ACCENT} stopOpacity={0.45} />
                    <stop offset="100%" stopColor={ACCENT} stopOpacity={0.02} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke={LINE} vertical={false} />
                <XAxis dataKey="t" tick={{ fill: MUTED, fontSize: 11 }} tickFormatter={(t) => String(t).slice(11, 16)} minTickGap={48} />
                <YAxis tick={{ fill: MUTED, fontSize: 11 }} width={54} tickFormatter={(v) => Intl.NumberFormat("en", { notation: "compact" }).format(v)} />
                <Tooltip
                  contentStyle={{ background: "#111", border: `1px solid ${LINE}`, borderRadius: 8, color: "#eee" }}
                  labelFormatter={(t) => `${String(t).slice(0, 16)} UTC`}
                  formatter={(v: any) => [Number(v).toLocaleString(), "concurrency"]}
                />
                <Area type="monotone" dataKey="c" stroke={ACCENT} strokeWidth={2} fill="url(#g)" isAnimationActive={false} />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* the SQL behind the curve */}
        <details style={{ marginTop: 16 }} open>
          <summary style={{ cursor: "pointer", color: MUTED, marginBottom: 8 }}>ClickHouse query</summary>
          <pre style={{ background: "#111", border: `1px solid ${LINE}`, borderRadius: 8, padding: 14, overflowX: "auto", color: ACCENT, fontSize: 12.5 }}>{sql}</pre>
        </details>
      </div>
    </div>
  );
}

function Kpi({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  return (
    <div style={{ background: CARD, border: `1px solid ${LINE}`, borderRadius: 10, padding: "14px 16px" }}>
      <Text color="muted" size="sm">{label}</Text>
      <div style={{ fontSize: 30, fontWeight: 700, color: accent ? ACCENT : "#fff", lineHeight: 1.2 }}>{value}</div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
      <span style={{ color: MUTED, fontSize: 12 }}>{label}</span>
      {children}
    </div>
  );
}

const inputStyle: CSSProperties = {
  background: CARD, color: "#eee", border: `1px solid ${LINE}`,
  borderRadius: 8, padding: "8px 10px", fontSize: 13, colorScheme: "dark",
};

const toLocal = (dt: string) => dt.slice(0, 16).replace(" ", "T");
const fromLocal = (v: string) => v.replace("T", " ") + ":00";
function shift(dt: string, minutes: number) {
  const d = new Date(dt.replace(" ", "T") + "Z");
  d.setUTCMinutes(d.getUTCMinutes() + minutes);
  return d.toISOString().slice(0, 19).replace("T", " ");
}
