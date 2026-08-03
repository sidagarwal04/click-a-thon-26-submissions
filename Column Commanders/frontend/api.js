/* ===========================================================================
   api.js — the single place the UI talks to the backend.
   No build step: load with <script src="api.js"> before index.html's app code.
   Everything is exposed on window.RCA_API.

   Endpoint status against the Go service (internal/http/server.go):

     LIVE   POST /api/v1/detect             detect({ day })
     LIVE   POST /api/v1/detect/auto        detectAuto()
     LIVE   GET  /api/v1/incidents          listIncidents()
     LIVE   GET  /api/v1/incidents/{id}     getIncident(id)
     LIVE   POST /api/v2/detect/historical  detectHistoricalV2()
     LIVE   POST /api/v2/detect/realtime    detectRealtimeV2()
     LIVE   GET  /api/v2/episodes           listEpisodesV2()
     LIVE   GET  /health                    health()

     TODO   GET  /api/timeseries            timeseries()   -> falls back to data.js
     TODO   GET  /api/breakdown             breakdown()    -> falls back to data.js
     TODO   POST /api/investigate           investigate()  -> derived from detect()

   The TODO calls are implemented against the local rollup in data.js so the UI
   works today. Each returns `{ source: 'local' | 'api' }` so the UI can show
   where a number came from — never silently present local data as live.
   =========================================================================== */

(function () {
  'use strict';

  // ── configuration ────────────────────────────────────────────────────────
  // Override without editing this file:
  //   ?api=http://host:8080   (query string, sticky via localStorage)
  //
  // When served from localhost, talk directly to the Go service.
  // When served from any other host (e.g. the ngrok domain), use the same
  // origin so nginx routes /api/* to the backend transparently.
  const _isLocal = ['localhost', '127.0.0.1'].includes(window.location.hostname);
  const DEFAULT_BASE = _isLocal ? 'http://localhost:8080' : '';

  function resolveBase() {
    const q = new URLSearchParams(location.search).get('api');
    if (q) { try { localStorage.setItem('rca_api_base', q); } catch (e) {} return q; }
    try { return localStorage.getItem('rca_api_base') || DEFAULT_BASE; } catch (e) { return DEFAULT_BASE; }
  }

  const CONFIG = {
    base: resolveBase(),
    timeoutMs: 120000,   // a segment sweep touches every dimension; allow for it
  };

  // ── transport ────────────────────────────────────────────────────────────

  async function request(method, path, { body, params } = {}) {
    let url = CONFIG.base.replace(/\/$/, '') + path;
    if (params) {
      const qs = new URLSearchParams(
        Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== '')
      ).toString();
      if (qs) url += '?' + qs;
    }

    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), CONFIG.timeoutMs);
    const started = performance.now();

    try {
      const res = await fetch(url, {
        method,
        headers: body ? { 'Content-Type': 'application/json' } : undefined,
        body: body ? JSON.stringify(body) : undefined,
        signal: ctrl.signal,
      });
      const text = await res.text();
      let data = null;
      try { data = text ? JSON.parse(text) : null; } catch (e) { /* non-JSON body */ }

      if (!res.ok) {
        const msg = (data && (data.error?.message || data.error)) || text || res.statusText;
        throw new ApiError(msg, res.status, url);
      }
      return { data, ms: Math.round(performance.now() - started) };
    } catch (err) {
      if (err.name === 'AbortError') throw new ApiError('request timed out', 0, url);
      if (err instanceof ApiError) throw err;
      // fetch() rejects on network failure and on CORS rejection alike
      throw new ApiError(
        `cannot reach ${CONFIG.base} — is the service running, and does it send CORS headers?`,
        0, url
      );
    } finally {
      clearTimeout(timer);
    }
  }

  class ApiError extends Error {
    constructor(message, status, url) {
      super(message);
      this.name = 'ApiError';
      this.status = status;
      this.url = url;
    }
  }

  // ── date helpers ─────────────────────────────────────────────────────────
  // window_end is exclusive. To analyse calendar day 2026-06-23, request the
  // complete window [2026-06-23T00:00Z, 2026-06-24T00:00Z).

  const iso = (d) => d.toISOString().slice(0, 10);
  const DAY_OFFSET = 1;

  function windowEndForDay(day) {
    const d = new Date(day + 'T00:00:00Z');
    d.setUTCDate(d.getUTCDate() + DAY_OFFSET);
    return iso(d) + 'T00:00:00Z';
  }

  // ── response normalisation ───────────────────────────────────────────────
  // The UI should not care that the backend calls it deviation_pct and returns
  // it as a preformatted string.

  function pctToNumber(v) {
    if (typeof v === 'number') return v;
    if (typeof v === 'string') {
      const n = parseFloat(v.replace('%', ''));
      return Number.isFinite(n) ? n / 100 : 0;
    }
    return 0;
  }

  // The service returns global signals only — no dimension or segment. The
  // fields are still read so a future segment-aware build needs no client change.
  function normalizeAnomaly(a) {
    return {
      metric: a.metric,
      detector: a.detector_id,
      dimension: a.dimension || null,
      segment: a.segment || null,
      isGlobal: !a.segment,
      current: a.current_value,
      baseline: a.baseline_value,
      z: a.z_score ?? 0,
      change: pctToNumber(a.deviation_pct),
      changeLabel: a.deviation_pct,
      severity: a.severity,
    };
  }

  // A signal with no z-score and a sub-1% move says nothing actionable. The
  // CUSUM detectors emit these on ordinary days (z = 0, deviation -0.0%), so
  // they are dropped here and counted, not silently discarded.
  const NOISE_Z = 1.0, NOISE_CHANGE = 0.01;
  const isNoise = (a) => Math.abs(a.z) < NOISE_Z && Math.abs(a.change) < NOISE_CHANGE;

  function normalizeDetect(payload, requestedDay) {
    const raw = (payload.anomalies || []).map(normalizeAnomaly);
    const anomalies = raw.filter((a) => !isNoise(a));
    const suppressed = raw.length - anomalies.length;
    // Strongest signal first — that is the one worth reading.
    anomalies.sort((x, y) => Math.abs(y.z) - Math.abs(x.z));
    return {
      day: requestedDay || (payload.window ? payload.window.start.slice(0, 10) : null),
      window: payload.window || null,
      anomalies,
      incidents: payload.incidents || [],
      hasAnomaly: anomalies.length > 0,
      suppressed,
      executionMs: payload.execution_time_ms ?? null,
      source: 'api',
    };
  }

  // ── LIVE endpoints ───────────────────────────────────────────────────────

  async function health() {
    const { data, ms } = await request('GET', '/health');
    return { ...data, ms };
  }

  /**
   * Run detection for one day.
   * @param {{day: string, metric?: string, windowSize?: string}} params
   *        day — 'YYYY-MM-DD', the day to analyse
   */
  async function detect(params = {}) {
    const body = {};
    if (params.day) body.window_end = windowEndForDay(params.day);
    if (params.metric) body.metric = params.metric;
    if (params.windowSize) body.window_size = params.windowSize;
    const { data } = await request('POST', '/api/v1/detect', { body });
    return normalizeDetect(data, params.day);
  }

  /** Detect on the latest complete window, resolved from the data watermark. */
  async function detectAuto() {
    const { data } = await request('POST', '/api/v1/detect/auto', { body: {} });
    return normalizeDetect(data);
  }

  function normalizeV2Run(payload) {
    const episodes = (payload.episodes || []).map((episode) => {
      let narration = episode.narration || null;
      if (typeof narration === 'string' && narration) {
        try { narration = JSON.parse(narration); } catch (e) { /* retain raw text */ }
      }
      return { ...episode, narration };
    });
    return { ...payload, episodes, source: 'api-v2' };
  }

  /** Run the dual-resolution 10-minute + hourly historical scanner. */
  async function detectHistoricalV2({ from, to, investigate = true } = {}) {
    const body = { investigate };
    if (from) body.start = new Date(from + 'T00:00:00Z').toISOString();
    if (to) {
      const exclusiveEnd = new Date(to + 'T00:00:00Z');
      exclusiveEnd.setUTCDate(exclusiveEnd.getUTCDate() + 1);
      body.end = exclusiveEnd.toISOString();
    }
    const { data } = await request('POST', '/api/v2/detect/historical', { body });
    return normalizeV2Run(data);
  }

  /** Run the latest closed 5-minute and 10-minute real-time windows. */
  async function detectRealtimeV2({ anchor, investigate = true } = {}) {
    const body = { investigate };
    if (anchor) body.anchor = anchor;
    const { data } = await request('POST', '/api/v2/detect/realtime', { body });
    return normalizeV2Run(data);
  }

  async function listEpisodesV2() {
    const { data } = await request('GET', '/api/v2/episodes');
    return { ...data, episodes: normalizeV2Run(data).episodes };
  }

  async function getEpisodeV2(id) {
    const { data } = await request('GET', `/api/v2/episodes/${encodeURIComponent(id)}`);
    return normalizeV2Run({ episodes: [data] }).episodes[0];
  }

  /**
   * Scan a date range one day at a time.
   * The service evaluates a single window per call, so a range is N calls;
   * they are issued in bounded batches to avoid opening 35 sockets at once.
   */
  async function detectRange({ from, to, metric, concurrency = 4, onProgress } = {}) {
    const days = [];
    for (let d = new Date(from + 'T00:00:00Z'); iso(d) <= to; d.setUTCDate(d.getUTCDate() + 1)) {
      days.push(iso(d));
    }
    const results = [];
    let done = 0;
    for (let i = 0; i < days.length; i += concurrency) {
      const batch = days.slice(i, i + concurrency);
      const settled = await Promise.allSettled(batch.map((day) => detect({ day, metric })));
      settled.forEach((s, j) => {
        done++;
        if (s.status === 'fulfilled') {
          if (s.value.anomalies.length) results.push(s.value);
        } else {
          results.push({ day: batch[j], anomalies: [], error: s.reason?.message, source: 'api' });
        }
      });
      if (onProgress) onProgress(done, days.length);
    }
    return groupIntoIncidents(results);
  }

  /**
   * Collapse alarming days into incident windows, independently per metric.
   *
   * Grouping on each day's single strongest signal loses whole metrics: when a
   * traffic collapse and a price drop land on the same day, only the louder one
   * survives and the other disappears from the UI entirely. Since the interface
   * is metric-first, the grouping is too — each metric gets its own timeline,
   * and a day can belong to one incident per metric.
   *
   * Within a metric, the segment shown is whichever slice moved hardest across
   * the window; the full ranked list travels alongside it.
   */
  function groupIntoIncidents(dayResults) {
    const withAlarms = dayResults
      .filter((r) => r.anomalies && r.anomalies.length)
      .sort((a, b) => (a.day < b.day ? -1 : 1));

    const DAY_MS = 86400000;
    const openByMetric = new Map();   // metric -> incident currently accepting days
    const closed = [];

    for (const r of withAlarms) {
      // Strongest signal per metric for this day.
      const leadByMetric = new Map();
      for (const a of r.anomalies) {
        const prev = leadByMetric.get(a.metric);
        if (!prev || Math.abs(a.z) > Math.abs(prev.z)) leadByMetric.set(a.metric, a);
      }

      // Retire any metric that went quiet for more than a day.
      for (const [m, inc] of [...openByMetric]) {
        if (leadByMetric.has(m)) continue;
        if ((new Date(r.day) - new Date(inc.end)) / DAY_MS > 1.5) {
          closed.push(inc);
          openByMetric.delete(m);
        }
      }

      for (const [m, lead] of leadByMetric) {
        const inc = openByMetric.get(m);
        const sameDirection = inc && Math.sign(inc.peak.change || inc.peak.z || 0) === Math.sign(lead.change || lead.z || 0);
        if (inc && sameDirection && (new Date(r.day) - new Date(inc.end)) / DAY_MS <= 1.5) {
          if (inc.end !== r.day) { inc.end = r.day; inc.days.push(r.day); }
          inc.signals.push(lead);
          mergeIncidentIDs(inc.incidentIds, incidentIDsFor(r, m, lead));
          if (Math.abs(lead.z) > Math.abs(inc.peak.z)) {
            inc.peak = lead;
            inc.segment = lead.segment;
            inc.dimension = lead.dimension;
          }
          inc.allAnomalies = r.anomalies.filter((a) => a.metric === m);
        } else {
          if (inc) closed.push(inc);
          openByMetric.set(m, {
            key: m + '|' + (lead.segment || 'GLOBAL'),
            start: r.day, end: r.day, days: [r.day],
            metric: m, segment: lead.segment, dimension: lead.dimension,
            peak: lead, signals: [lead],
            incidentIds: incidentIDsFor(r, m, lead),
            allAnomalies: r.anomalies.filter((a) => a.metric === m),
          });
        }
      }
    }

    const incidents = [...closed, ...openByMetric.values()]
      .sort((a, b) => (a.start < b.start ? -1 : (a.start > b.start ? 1 : Math.abs(b.peak.z) - Math.abs(a.peak.z))));
    return { incidents, dayResults: withAlarms, source: 'api' };
  }

  async function listIncidents(params = {}) {
    const { data } = await request('GET', '/api/v1/incidents', { params });
    return data;
  }

  async function getIncident(id) {
    const { data } = await request('GET', '/api/v1/incidents/' + encodeURIComponent(id));
    return data;
  }

  /** Fetch the complete system-generated trace for a V1 incident. */
  async function getIncidentTrace(id) {
    const { data } = await request('GET', `/api/v1/incidents/${encodeURIComponent(id)}/trace`);
    return data;
  }

  function incidentIDsFor(dayResult, metric, lead) {
    const direction = Math.sign(lead.change || lead.z || 0);
    const candidates = (dayResult.incidents || [])
      .filter((incident) => incident.metric === metric)
      .filter((incident) => {
        const incidentDirection = Math.sign(pctToNumber(incident.deviation_pct) || incident.z_score || 0);
        return direction === 0 || incidentDirection === 0 || incidentDirection === direction;
      });
    const exact = candidates.filter((incident) =>
      (incident.dimension || '') === (lead.dimension || '') &&
      (incident.segment || '') === (lead.segment || ''));
    return (exact.length ? exact : candidates.filter((incident) => !incident.dimension && !incident.segment))
      .map((incident) => incident.id);
  }

  function mergeIncidentIDs(target, additions) {
    for (const id of additions) {
      if (id && !target.includes(id)) target.push(id);
    }
  }

  const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

  /** Poll until the async v1 drilldown and narrator have reached a terminal response. */
  async function waitForIncident(id, { timeoutMs = 120000, pollIntervalMs = 750 } = {}) {
    const deadline = Date.now() + timeoutMs;
    while (Date.now() < deadline) {
      const detail = await getIncident(id);
      if (detail && detail.drilldown) return detail;
      await wait(pollIntervalMs);
    }
    throw new ApiError(`incident ${id} analysis timed out`, 0, CONFIG.base + '/api/v1/incidents/' + encodeURIComponent(id));
  }

  function normalizeV1Investigation(group, detail, analysisError) {
    const signals = group.signals || [group.peak].filter(Boolean);
    const peak = group.peak || signals[0] || {};
    const avgChange = signals.length
      ? signals.reduce((sum, signal) => sum + (signal.change || 0), 0) / signals.length
      : 0;
    const dd = detail?.drilldown || null;
    const narration = detail?.narration || null;
    const culprits = dd?.culprit_segments || [];
    const classification = dd?.classification || null;
    let winner = null;
    if (dd?.pairwise) {
      const pair = dd.pairwise;
      winner = {
        dim: `${pair.dim1} x ${pair.dim2}`,
        val: `${pair.value1} × ${pair.value2}`,
        base: pair.baseline_value,
        win: pair.current_value,
        change: pair.baseline_value ? pair.current_value / pair.baseline_value - 1 : 0,
        explained: dd.completeness_score || 0,
        volume: pair.current_n,
      };
    } else if (culprits.length) {
      const top = culprits[0];
      winner = {
        dim: top.dimension, val: top.segment,
        base: top.baseline_value, win: top.current_value,
        change: top.baseline_value ? top.current_value / top.baseline_value - 1 : 0,
        explained: Math.abs(top.contribution_pct || 0), volume: null,
      };
    }
    const ranked = culprits.map((item) => ({
      dim: item.dimension, val: item.segment,
      base: item.baseline_value, win: item.current_value,
      change: item.baseline_value ? item.current_value / item.baseline_value - 1 : 0,
      explained: Math.abs(item.contribution_pct || 0), volume: null,
    }));
    const guiltyDelta = dd?.factor_decomposition?.[dd.guilty_factor]?.delta_pct;
    const verdict = classification === 'global'
      ? 'GLOBAL'
      : (classification === 'single-segment' || classification === 'intersection')
        ? 'LOCALIZED'
        : 'UNEXPLAINED';

    return {
      ...group,
      id: detail?.incident?.id || group.incidentIds?.[0] || null,
      start: group.start,
      end: group.end,
      n: group.days?.length || 1,
      dir: Math.sign(avgChange || peak.z || 0),
      avgResid: avgChange,
      peakZ: peak.z || detail?.incident?.z_score || 0,
      worst: { v: peak.current, base: peak.baseline },
      severity: detail?.incident?.severity || peak.severity,
      drilldown: dd,
      narration,
      analysisError: analysisError || (detail && !narration ? 'LLM narration was not returned' : null),
      source: 'api-v1',
      attribution: dd ? {
        verdict, classification, winner, ranked,
        ruledOut: [],
        skippedDims: (dd.ruled_out_dimensions || []).map((dim) => ({ dim, reason: 'no qualifying contribution' })),
        uniformChange: guiltyDelta ?? avgChange,
        cv: null,
      } : null,
    };
  }

  /** Run live v1 detection and wait for its terminal drilldown/narration output. */
  async function detectRangeV1({ from, to, metric, onProgress } = {}) {
    // V1 incidents are stateful, so scan days in order rather than racing
    // updates for the same metric/direction through the incident store.
    const grouped = await detectRange({ from, to, metric, concurrency: 1, onProgress });
    const incidents = await Promise.all(grouped.incidents.map(async (group) => {
      const id = group.incidentIds?.[0];
      if (!id) return normalizeV1Investigation(group, null, 'backend returned no incident id');
      try {
        const detail = await waitForIncident(id);
        return normalizeV1Investigation(group, detail, null);
      } catch (error) {
        return normalizeV1Investigation(group, null, error.message || String(error));
      }
    }));
    return { ...grouped, incidents, source: 'api-v1' };
  }

  // ── NOT-YET-LIVE endpoints ───────────────────────────────────────────────
  // These read the local rollup in data.js. They return source:'local' so the
  // UI can label them; do not let them masquerade as live data.

  const LOCAL = {
    ready: () => typeof window.RCA_DATA !== 'undefined',
    rows() {
      if (!this._rows) {
        this._rows = (window.RCA_DATA || []).map((r) => ({
          day: r[0], dim: r[1], val: r[2],
          reqs: r[3], fills: r[4], imps: r[5], clicks: r[6], revenue: r[7],
        }));
      }
      return this._rows;
    },
  };

  const METRIC_DEF = {
    fill_rate:   { num: 'fills',   den: 'reqs',  scale: 1 },
    render_rate: { num: 'imps',    den: 'fills', scale: 1 },
    ctr:         { num: 'clicks',  den: 'imps',  scale: 1 },
    ecpm:        { num: 'revenue', den: 'imps',  scale: 1000 },
    requests:    { num: 'reqs',    den: null,    scale: 1 },
    revenue:     { num: 'revenue', den: null,    scale: 1 },
  };

  function bucketOf(day, interval) {
    if (interval === 'monthly') return day.slice(0, 7) + '-01';
    if (interval === 'weekly') {
      const d = new Date(day + 'T00:00:00Z');
      d.setUTCDate(d.getUTCDate() - ((d.getUTCDay() + 6) % 7));
      return iso(d);
    }
    return day;
  }

  /**
   * Time series for one metric and segment.
   * Returns counters alongside the value, so the caller can re-derive any
   * metric or coarser period without another round-trip — and so a ratio is
   * never computed by averaging per-bucket ratios, which does not aggregate.
   */
  async function timeseries({ metric = 'fill_rate', dim = '__global__', val = 'all',
                              interval = 'daily', from, to } = {}) {
    if (!LOCAL.ready()) throw new ApiError('data.js not loaded and /api/timeseries is not implemented', 0, '');
    const def = METRIC_DEF[metric];
    if (!def) throw new ApiError('unknown metric ' + metric, 400, '');

    const acc = new Map();
    for (const r of LOCAL.rows()) {
      if (r.dim !== dim || r.val !== val) continue;
      if (from && r.day < from) continue;
      if (to && r.day > to) continue;
      const b = bucketOf(r.day, interval);
      let a = acc.get(b);
      if (!a) { a = { bucket: b, reqs: 0, fills: 0, imps: 0, clicks: 0, revenue: 0 }; acc.set(b, a); }
      a.reqs += r.reqs; a.fills += r.fills; a.imps += r.imps;
      a.clicks += r.clicks; a.revenue += r.revenue;
    }

    const points = [...acc.values()].sort((a, b) => (a.bucket < b.bucket ? -1 : 1)).map((a) => {
      const n = a[def.num], d = def.den ? a[def.den] : 1;
      return { ...a, value: d > 0 ? (n / d) * def.scale : null, den: def.den ? d : a.reqs };
    });

    return { metric, interval, segment: { dim, val }, points, source: 'local' };
  }

  /** Every value of one dimension, aggregated over a range. */
  async function breakdown({ dim = 'os_version', from, to } = {}) {
    if (!LOCAL.ready()) throw new ApiError('data.js not loaded and /api/breakdown is not implemented', 0, '');
    const acc = new Map();
    for (const r of LOCAL.rows()) {
      if (r.dim !== dim) continue;
      if (from && r.day < from) continue;
      if (to && r.day > to) continue;
      let a = acc.get(r.val);
      if (!a) { a = { val: r.val, reqs: 0, fills: 0, imps: 0, clicks: 0, revenue: 0 }; acc.set(r.val, a); }
      a.reqs += r.reqs; a.fills += r.fills; a.imps += r.imps;
      a.clicks += r.clicks; a.revenue += r.revenue;
    }
    const rows = [...acc.values()].map((a) => ({
      ...a,
      fill_rate:   a.reqs ? a.fills / a.reqs : null,
      render_rate: a.fills ? a.imps / a.fills : null,
      ctr:         a.imps ? a.clicks / a.imps : null,
      ecpm:        a.imps ? (a.revenue / a.imps) * 1000 : null,
    })).sort((x, y) => y.revenue - x.revenue);
    return { dim, rows, source: 'local' };
  }

  /**
   * Attribution for one detected day.
   *
   * There is no /api/investigate yet, so this derives what it can from the
   * detect response: the segment signals ARE the attribution, ranked by how
   * far each moved. Segment-level signals outrank global ones — a global
   * signal says something moved, a segment signal says where.
   */
  async function investigate({ day, metric } = {}) {
    const res = await detect({ day });
    let signals = res.anomalies;
    if (metric) signals = signals.filter((s) => s.metric === metric);

    const segments = signals.filter((s) => s.segment);
    const globals = signals.filter((s) => !s.segment);

    // Uniform movement across many segments means no single segment is
    // responsible — reporting the largest one would be a fabrication.
    let verdict = 'UNEXPLAINED';
    if (segments.length) {
      const changes = segments.map((s) => s.change);
      const mean = changes.reduce((a, b) => a + b, 0) / changes.length;
      const sd = Math.sqrt(changes.reduce((a, b) => a + (b - mean) ** 2, 0) / changes.length);
      const cv = Math.abs(mean) > 1e-9 ? sd / Math.abs(mean) : Infinity;
      verdict = (segments.length >= 4 && cv < 0.10) ? 'GLOBAL' : 'LOCALIZED';
    } else if (globals.length) {
      verdict = 'GLOBAL';
    }

    return {
      day, verdict,
      culprit: verdict === 'LOCALIZED' ? segments[0] || null : null,
      segments, globals,
      ruledOut: signals.slice(1, 9),
      executionMs: res.executionMs,
      source: 'api-derived',
    };
  }

  // ── connectivity probe ───────────────────────────────────────────────────
  // Lets the UI decide up-front whether to run live or from data.js, instead
  // of failing on the first user click.

  async function probe() {
    try {
      const h = await health();
      return { online: true, base: CONFIG.base, ms: h.ms };
    } catch (err) {
      return { online: false, base: CONFIG.base, error: err.message };
    }
  }

  window.RCA_API = {
    CONFIG,
    ApiError,
    setBase(url) {
      CONFIG.base = url;
      try { localStorage.setItem('rca_api_base', url); } catch (e) {}
    },
    probe, health,
    detect, detectAuto, detectRange, detectRangeV1, waitForIncident,
    detectHistoricalV2, detectRealtimeV2, listEpisodesV2, getEpisodeV2,
    listIncidents, getIncident, getIncidentTrace,
    investigate,
    timeseries, breakdown,
    _helpers: { windowEndForDay, groupIntoIncidents, pctToNumber, bucketOf },
  };
})();
