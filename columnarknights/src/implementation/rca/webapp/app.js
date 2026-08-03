const API = "";
const METRIC_LABELS = {
  revenue: "Revenue",
  fill_rate: "Fill rate",
  ecpm: "eCPM",
  requests: "Requests",
  ctr: "CTR",
  fills: "Fills",
  impressions: "Impressions",
  render_rate: "Render rate",
  clicks: "Clicks",
};

let state = {
  metric: "revenue",
  start: null,
  end: null,
  metrics: [],
  incidents: [],
  filterMetric: "all",
  filterSeverity: "all",
  sort: "newest",
};

function fmtNumber(v) {
  if (v === null || v === undefined) return "—";
  const abs = Math.abs(v);
  if (abs >= 1e6) return (v / 1e6).toFixed(2) + "M";
  if (abs >= 1e3) return (v / 1e3).toFixed(2) + "K";
  if (abs < 1 && abs > 0) return v.toFixed(4);
  return v.toFixed(2);
}

function fmtPct(v) {
  if (v === null || v === undefined) return "—";
  return (v * 100).toFixed(1) + "%";
}

function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
}

async function fetchJSON(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${url} -> ${res.status}`);
  return res.json();
}

// severity/confidence are computed once, server-side (web.py: _severity_for /
// _confidence_for) from real numbers -- every incident already carries them.
function confidenceRing(pct, size) {
  size = size || 26;
  const r = size / 2 - 3, c = 2 * Math.PI * r;
  if (pct === null) {
    return `<svg class="ring" width="${size}" height="${size}" viewBox="0 0 ${size} ${size}">` +
      `<circle cx="${size / 2}" cy="${size / 2}" r="${r}" fill="none" stroke="var(--gridline)" stroke-width="3"/></svg>`;
  }
  const off = c * (1 - pct / 100);
  return `<svg class="ring" width="${size}" height="${size}" viewBox="0 0 ${size} ${size}">` +
    `<circle cx="${size / 2}" cy="${size / 2}" r="${r}" fill="none" stroke="rgba(255,255,255,0.08)" stroke-width="3"/>` +
    `<circle cx="${size / 2}" cy="${size / 2}" r="${r}" fill="none" stroke="url(#chartAreaGradient)" stroke-width="3" ` +
    `stroke-linecap="round" stroke-dasharray="${c}" stroke-dashoffset="${off}" transform="rotate(-90 ${size / 2} ${size / 2})"/>` +
    `</svg>`;
}

async function init() {
  const meta = await fetchJSON(`${API}/api/meta`);
  document.getElementById("meta-sub").textContent =
    `${meta.row_count.toLocaleString()} events loaded — ${meta.min_date} to ${meta.max_date}`;

  state.metrics = meta.metrics;
  state.start = meta.min_date;
  state.end = meta.max_date;

  const startInput = document.getElementById("start-date");
  const endInput = document.getElementById("end-date");
  startInput.min = meta.min_date;
  startInput.max = meta.max_date;
  endInput.min = meta.min_date;
  endInput.max = meta.max_date;
  startInput.value = meta.min_date;
  endInput.value = meta.max_date;
  startInput.addEventListener("change", () => { state.start = startInput.value; loadChart(); });
  endInput.addEventListener("change", () => { state.end = endInput.value; loadChart(); });

  // Chart tabs: only the 3 metrics with full revenue-identity drill-down
  // support (requests/ctr still get investigated and show up as real
  // incidents in the list below -- just not offered as a chart tab, to keep
  // the demo's headline surface simple).
  const tabsEl = document.getElementById("metric-tabs");
  ["revenue", "fill_rate", "ecpm"].forEach((m) => {
    const btn = document.createElement("button");
    btn.className = "tab" + (m === state.metric ? " active" : "");
    btn.textContent = METRIC_LABELS[m] || m;
    btn.dataset.metric = m;
    btn.addEventListener("click", () => {
      state.metric = m;
      document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
      btn.classList.add("active");
      loadChart();
    });
    tabsEl.appendChild(btn);
  });

  document.getElementById("scan-btn").addEventListener("click", runScan);
  setupFilterMenus();
  setupLiveMonitor();

  await Promise.all([loadChart(), loadIncidents()]);
}

// Reflects rca/live_monitor.py's SSE state (ingest/idle/pipeline_start/
// pipeline_complete) -- this is a live push from the server's own idle
// detection, not a poll loop the frontend runs itself. "Scan for incidents"
// stays available as a manual override, not the demo's primary path.
function setupLiveMonitor() {
  const pill = document.getElementById("live-pill");
  const text = document.getElementById("live-pill-text");
  const es = new EventSource(`${API}/api/live/events`);

  es.onmessage = (e) => {
    let data;
    try { data = JSON.parse(e.data); } catch { return; }
    pill.className = "live-pill " + (data.type || "");
    if (data.type === "ingest") {
      text.textContent = `Ingesting… ${data.row_count.toLocaleString()} rows`;
    } else if (data.type === "idle") {
      text.textContent = `Idle ${data.idle_seconds.toFixed(0)}s — ${data.row_count.toLocaleString()} rows`;
    } else if (data.type === "settled") {
      text.textContent = `Up to date — ${data.row_count.toLocaleString()} rows`;
    } else if (data.type === "pipeline_start") {
      text.textContent = "Detecting & investigating…";
    } else if (data.type === "pipeline_complete") {
      const n = (data.investigation_ids || []).length;
      text.textContent = n ? `${n} new incident${n > 1 ? "s" : ""} found` : "Scan complete — nothing new";
      if (n) {
        loadIncidents();
        showToast(`${n} new incident${n > 1 ? "s" : ""} auto-detected`, "success");
      }
    } else if (data.type === "error") {
      text.textContent = "Live monitor error";
    } else if (data.type === "waiting") {
      text.textContent = "Waiting for data…";
    } else {
      text.textContent = "Connecting…";
    }
  };
  es.onerror = () => {
    pill.className = "live-pill error";
    text.textContent = "Live monitor disconnected — retrying…";
  };
}

async function loadChart() {
  const svg = document.getElementById("chart");
  const data = await fetchJSON(
    `${API}/api/timeseries?metric=${state.metric}&start=${state.start}&end=${state.end}`
  );
  renderChart(svg, data.points, state.metric);
  updateChartMeta(data.points, state.metric);
}

function updateChartMeta(points, metric) {
  const titleEl = document.getElementById("chart-title");
  const label = METRIC_LABELS[metric] || metric;
  if (!points.length) { titleEl.textContent = `${label} over time`; return; }
  const last = points[points.length - 1];
  const prev = points.length > 1 ? points[points.length - 2] : null;
  let extra = "";
  if (prev && prev.value) {
    const d = ((last.value - prev.value) / Math.abs(prev.value)) * 100;
    extra = ` · Latest ${fmtNumber(last.value)} (${d >= 0 ? "+" : ""}${d.toFixed(1)}% vs prior day)`;
  }
  titleEl.textContent = `${label} over time${extra}`;
}

function renderChart(svg, points, metric) {
  const W = svg.clientWidth || 1100;
  const H = 260;
  const padL = 46, padR = 12, padT = 14, padB = 26;
  const plotW = W - padL - padR;
  const plotH = H - padT - padB;

  const defs = svg.querySelector("defs");
  svg.innerHTML = "";
  if (defs) svg.appendChild(defs);
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);

  const legend = document.getElementById("chart-legend");
  const hasDown = points.some((p) => p.is_anomaly && p.rel_delta < 0);
  const hasUp = points.some((p) => p.is_anomaly && p.rel_delta >= 0);
  const hasBaseline = points.some((p) => p.baseline_expected !== null && p.baseline_expected !== undefined);
  legend.innerHTML = "";
  if (hasBaseline) legend.innerHTML += `<span class="legend-item"><span class="dot baseline"></span>Baseline (expected)</span>`;
  if (hasDown) legend.innerHTML += `<span class="legend-item"><span class="dot down"></span>Anomaly (drop)</span>`;
  if (hasUp) legend.innerHTML += `<span class="legend-item"><span class="dot up"></span>Anomaly (spike)</span>`;
  legend.style.display = (hasDown || hasUp || hasBaseline) ? "flex" : "none";

  if (!points.length) {
    const t = document.createElementNS("http://www.w3.org/2000/svg", "text");
    t.setAttribute("x", W / 2);
    t.setAttribute("y", H / 2);
    t.setAttribute("text-anchor", "middle");
    t.setAttribute("class", "chart-axis-text");
    t.textContent = "No data in this range";
    svg.appendChild(t);
    return;
  }

  const values = points.map((p) => p.value);
  const baselineVals = points.map((p) => p.baseline_expected).filter((v) => v !== null && v !== undefined);
  let vMin = Math.min(...values, ...baselineVals), vMax = Math.max(...values, ...baselineVals);
  const pad = (vMax - vMin) * 0.12 || Math.abs(vMax) * 0.1 || 1;
  vMin -= pad; vMax += pad;

  const xScale = (i) => padL + (points.length === 1 ? plotW / 2 : (i / (points.length - 1)) * plotW);
  const yScale = (v) => padT + plotH - ((v - vMin) / (vMax - vMin || 1)) * plotH;

  const ns = "http://www.w3.org/2000/svg";
  const g = document.createElementNS(ns, "g");

  const steps = 3;
  for (let s = 0; s <= steps; s++) {
    const v = vMin + ((vMax - vMin) * s) / steps;
    const y = yScale(v);
    const line = document.createElementNS(ns, "line");
    line.setAttribute("x1", padL); line.setAttribute("x2", W - padR);
    line.setAttribute("y1", y); line.setAttribute("y2", y);
    line.setAttribute("class", "chart-grid");
    g.appendChild(line);
    const text = document.createElementNS(ns, "text");
    text.setAttribute("x", padL - 8); text.setAttribute("y", y + 3);
    text.setAttribute("text-anchor", "end");
    text.setAttribute("class", "chart-axis-text");
    text.textContent = fmtNumber(v);
    g.appendChild(text);
  }

  let areaPath = `M ${xScale(0)} ${yScale(points[0].value)}`;
  points.forEach((p, i) => { areaPath += ` L ${xScale(i)} ${yScale(p.value)}`; });
  areaPath += ` L ${xScale(points.length - 1)} ${padT + plotH} L ${xScale(0)} ${padT + plotH} Z`;
  const area = document.createElementNS(ns, "path");
  area.setAttribute("d", areaPath);
  area.setAttribute("class", "chart-area");
  g.appendChild(area);

  // Baseline: broken into separate subpaths wherever there isn't enough
  // same-weekday history yet (baseline_expected is null for the first couple
  // of weeks in range), rather than drawing a misleading line through gaps.
  let baselinePath = "", drawingBaseline = false;
  points.forEach((p, i) => {
    if (p.baseline_expected === null || p.baseline_expected === undefined) {
      drawingBaseline = false;
      return;
    }
    baselinePath += ` ${drawingBaseline ? "L" : "M"} ${xScale(i)} ${yScale(p.baseline_expected)}`;
    drawingBaseline = true;
  });
  if (baselinePath) {
    const baseLine = document.createElementNS(ns, "path");
    baseLine.setAttribute("d", baselinePath.trim());
    baseLine.setAttribute("class", "chart-baseline");
    g.appendChild(baseLine);
  }

  let linePath = `M ${xScale(0)} ${yScale(points[0].value)}`;
  points.forEach((p, i) => { if (i > 0) linePath += ` L ${xScale(i)} ${yScale(p.value)}`; });
  const line = document.createElementNS(ns, "path");
  line.setAttribute("d", linePath);
  line.setAttribute("class", "chart-line");
  g.appendChild(line);

  points.forEach((p, i) => {
    if (!p.is_anomaly) return;
    const dot = document.createElementNS(ns, "circle");
    dot.setAttribute("cx", xScale(i));
    dot.setAttribute("cy", yScale(p.value));
    dot.setAttribute("r", 5);
    dot.setAttribute("class", "chart-dot " + (p.rel_delta >= 0 ? "anomaly-up" : "anomaly-down"));
    g.appendChild(dot);
  });

  [0, Math.floor((points.length - 1) / 2), points.length - 1].forEach((i) => {
    const text = document.createElementNS(ns, "text");
    text.setAttribute("x", xScale(i));
    text.setAttribute("y", H - 6);
    text.setAttribute("text-anchor", i === 0 ? "start" : i === points.length - 1 ? "end" : "middle");
    text.setAttribute("class", "chart-axis-text");
    text.textContent = points[i].date;
    g.appendChild(text);
  });

  const crosshair = document.createElementNS(ns, "line");
  crosshair.setAttribute("y1", padT); crosshair.setAttribute("y2", padT + plotH);
  crosshair.setAttribute("class", "chart-crosshair");
  g.appendChild(crosshair);

  const hoverDot = document.createElementNS(ns, "circle");
  hoverDot.setAttribute("r", 4);
  hoverDot.setAttribute("class", "chart-dot");
  hoverDot.style.opacity = 0;
  g.appendChild(hoverDot);

  const hit = document.createElementNS(ns, "rect");
  hit.setAttribute("x", padL); hit.setAttribute("y", padT);
  hit.setAttribute("width", plotW); hit.setAttribute("height", plotH);
  hit.setAttribute("class", "hit-target");
  g.appendChild(hit);

  svg.appendChild(g);

  const tooltip = document.getElementById("tooltip");

  function showTooltip(evt) {
    const rect = svg.getBoundingClientRect();
    const scaleX = W / rect.width;
    const mouseX = (evt.clientX - rect.left) * scaleX;
    let idx = Math.round(((mouseX - padL) / plotW) * (points.length - 1));
    idx = Math.max(0, Math.min(points.length - 1, idx));
    const p = points[idx];
    const x = xScale(idx), y = yScale(p.value);

    crosshair.setAttribute("x1", x); crosshair.setAttribute("x2", x);
    crosshair.style.opacity = 1;
    hoverDot.setAttribute("cx", x); hoverDot.setAttribute("cy", y);
    hoverDot.style.opacity = 1;

    tooltip.style.left = `${(x / W) * rect.width}px`;
    tooltip.style.top = `${(y / H) * rect.height}px`;
    tooltip.style.opacity = 1;
    tooltip.innerHTML = "";
    const dateEl = document.createElement("div");
    dateEl.className = "t-date"; dateEl.textContent = p.date;
    const valEl = document.createElement("div");
    valEl.className = "t-value"; valEl.textContent = `${METRIC_LABELS[metric] || metric}: ${fmtNumber(p.value)}`;
    tooltip.appendChild(dateEl); tooltip.appendChild(valEl);
    if (p.baseline_expected !== null && p.baseline_expected !== undefined) {
      const baseEl = document.createElement("div");
      baseEl.className = "t-baseline";
      baseEl.textContent = `Baseline: ${fmtNumber(p.baseline_expected)} (${fmtPct(p.rel_delta)})`;
      tooltip.appendChild(baseEl);
    }
    if (p.is_anomaly) {
      const noteEl = document.createElement("div");
      noteEl.className = "t-note";
      noteEl.textContent = `Anomaly: ${p.rel_delta >= 0 ? "spike" : "drop"} vs baseline`;
      tooltip.appendChild(noteEl);
    }
  }
  function hideTooltip() {
    tooltip.style.opacity = 0;
    crosshair.style.opacity = 0;
    hoverDot.style.opacity = 0;
  }
  hit.addEventListener("pointermove", showTooltip);
  hit.addEventListener("pointerleave", hideTooltip);
}

// ---------------- Incidents: KPIs, filters, list ----------------

function renderIncidentKPIs(incidents) {
  const tiles = document.getElementById("tiles");
  tiles.innerHTML = "";
  const highCount = incidents.filter((i) => i.severity === "high").length;
  const metricsAffected = new Set(incidents.map((i) => i.metric)).size;
  let biggest = null;
  incidents.forEach((i) => {
    if (i.metric_rel_delta === null || i.metric_rel_delta === undefined) return;
    if (!biggest || Math.abs(i.metric_rel_delta) > Math.abs(biggest.metric_rel_delta)) biggest = i;
  });
  const defs = [
    { label: "Incidents", value: String(incidents.length), accent: "" },
    { label: "High Severity", value: String(highCount), accent: highCount ? "accent-alert" : "accent-ok" },
    { label: "Metrics Affected", value: String(metricsAffected), accent: "" },
    {
      label: "Biggest Impact",
      value: biggest
        ? `${METRIC_LABELS[biggest.metric] || biggest.metric} ${biggest.metric_rel_delta >= 0 ? "+" : ""}${(biggest.metric_rel_delta * 100).toFixed(1)}%`
        : "—",
      accent: "impact",
    },
  ];
  defs.forEach((d) => {
    const tile = el("div", "tile" + (d.accent ? ` ${d.accent}` : ""));
    tile.appendChild(el("div", "label", d.label));
    tile.appendChild(el("div", "value", d.value));
    tiles.appendChild(tile);
  });
}

function setupFilterMenus() {
  document.getElementById("filterRow").addEventListener("click", (e) => {
    const btn = e.target.closest(".filter-btn");
    if (!btn) return;
    const name = btn.dataset.menu;
    const menu = document.getElementById("menu-" + name);
    const wasOpen = menu.classList.contains("open");
    closeAllMenus();
    if (!wasOpen) {
      menu.style.left = btn.offsetLeft + "px";
      menu.classList.add("open");
      btn.classList.add("open");
    }
  });
  document.addEventListener("click", (e) => {
    if (!e.target.closest("#filterRow")) closeAllMenus();
  });
}

function closeAllMenus() {
  document.querySelectorAll(".filter-menu").forEach((m) => m.classList.remove("open"));
  document.querySelectorAll(".filter-btn").forEach((b) => b.classList.remove("open"));
}

function fillMenu(menuId, options, current, onSelect) {
  const menu = document.getElementById(menuId);
  menu.innerHTML = "";
  options.forEach(([value, label]) => {
    const btn = el("button", value === current ? "sel" : "", label);
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      onSelect(value, label);
      closeAllMenus();
    });
    menu.appendChild(btn);
  });
}

function renderFilterMenus() {
  const metricOptions = [["all", "All Metrics"]].concat(
    Array.from(new Set(state.incidents.map((i) => i.metric))).sort().map((m) => [m, METRIC_LABELS[m] || m])
  );
  const severityOptions = [["all", "All Severities"], ["high", "High"], ["medium", "Medium"], ["low", "Low"]];
  const sortOptions = [["newest", "Newest first"], ["severity", "Highest severity"], ["confidence", "Highest confidence"]];

  fillMenu("menu-metric", metricOptions, state.filterMetric, (v, label) => {
    state.filterMetric = v; document.getElementById("metricLabel").textContent = label; renderIncidentList();
  });
  fillMenu("menu-severity", severityOptions, state.filterSeverity, (v, label) => {
    state.filterSeverity = v; document.getElementById("severityLabel").textContent = label; renderIncidentList();
  });
  fillMenu("menu-sort", sortOptions, state.sort, (v, label) => {
    state.sort = v; document.getElementById("sortLabel").textContent = label; renderIncidentList();
  });
}

function renderIncidentList() {
  const list = document.getElementById("incident-list");
  list.innerHTML = "";

  let items = state.incidents.filter((i) =>
    (state.filterMetric === "all" || i.metric === state.filterMetric) &&
    (state.filterSeverity === "all" || i.severity === state.filterSeverity)
  );
  const sevRank = { high: 0, medium: 1, low: 2 };
  if (state.sort === "severity") {
    items = items.slice().sort((a, b) => sevRank[a.severity] - sevRank[b.severity]);
  } else if (state.sort === "confidence") {
    items = items.slice().sort((a, b) => (b.confidence || 0) - (a.confidence || 0));
  }

  if (!state.incidents.length) {
    list.innerHTML = `<div class="empty">No investigations saved yet. Click "Scan for incidents" above, then investigate one.</div>`;
    return;
  }
  if (!items.length) {
    list.innerHTML = `<div class="empty">No incidents match these filters.</div>`;
    return;
  }

  items.forEach((inc) => {
    const sev = inc.severity;
    const conf = inc.confidence;
    // segment_chains holds one path per independent cause the drill-down
    // found (usually one). The strongest is chains[0] -- show that as the
    // headline and note the count if there's more than one, rather than
    // silently hiding that other causes were also found.
    const chains = inc.segment_chains || [];
    const rootCause = chains.length && chains[0].length
      ? chains[0].map((s) => `${s.dimension} = ${s.value}`).join(" → ") + (chains.length > 1 ? ` (+${chains.length - 1} more)` : "")
      : "Broad-based";
    const deltaPct = inc.metric_rel_delta === null || inc.metric_rel_delta === undefined
      ? "—" : `${inc.metric_rel_delta >= 0 ? "+" : ""}${(inc.metric_rel_delta * 100).toFixed(1)}%`;

    const a = document.createElement("a");
    a.className = `incident-card sev-${sev}`;
    a.href = `incident.html?id=${encodeURIComponent(inc.id)}`;
    a.innerHTML = `
      <div class="row1">
        <div class="row1-left">
          <span class="metric-name"></span>
          <span class="window"></span>
        </div>
        <span class="badge sev-${sev}">${sev.toUpperCase()}</span>
      </div>
      <div class="incident-metric ${inc.metric_rel_delta >= 0 ? "up" : "down"}"></div>
      <div class="incident-root">Root Cause: <b></b></div>
      <p class="narrative-snippet"></p>
      <div class="incident-bottom">
        <span class="confidence-inline">${confidenceRing(conf, 24)}<span></span></span>
        <span class="view-link">View Investigation <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4"><path d="M5 12h14"/><path d="M13 6l6 6-6 6"/></svg></span>
      </div>
    `;
    a.querySelector(".metric-name").textContent = METRIC_LABELS[inc.metric] || inc.metric;
    a.querySelector(".window").textContent = `${inc.current_window[0]} .. ${inc.current_window[1]}`;
    a.querySelector(".incident-metric").textContent = `${METRIC_LABELS[inc.metric] || inc.metric} ${deltaPct}`;
    a.querySelector(".incident-root b").textContent = rootCause;
    a.querySelector(".narrative-snippet").textContent = (inc.narrative || "").slice(0, 200) + (inc.narrative && inc.narrative.length > 200 ? "…" : "");
    a.querySelector(".confidence-inline span").textContent = conf === null ? "No localized cause" : `Confidence ${conf}%`;
    list.appendChild(a);
  });
}

async function loadIncidents() {
  const data = await fetchJSON(`${API}/api/incidents`);
  state.incidents = data.incidents;
  renderIncidentKPIs(state.incidents);
  renderFilterMenus();
  renderIncidentList();
}

function showToast(message, type) {
  const container = document.getElementById("toast-container");
  const t = document.createElement("div");
  t.className = "toast" + (type ? ` ${type}` : "");
  t.textContent = message;
  container.appendChild(t);
  setTimeout(() => {
    t.classList.add("fade-out");
    setTimeout(() => t.remove(), 200);
  }, 4000);
}

async function runScan() {
  const btn = document.getElementById("scan-btn");
  btn.disabled = true;
  btn.innerHTML = `<span class="spinner"></span>Scanning…`;
  try {
    const data = await fetchJSON(`${API}/api/scan?start=${state.start}&end=${state.end}`);
    if (!data.incidents.length) {
      showToast("No anomalies detected in this range.", "success");
      return;
    }
    btn.innerHTML = `<span class="spinner"></span>Investigating ${data.incidents.length} incident(s)…`;
    for (const inc of data.incidents) {
      const res = await fetch(
        `${API}/api/investigate?metric=${inc.metric}&start=${inc.start}&end=${inc.end}`,
        { method: "POST" }
      );
      if (!res.ok) console.error("investigate failed", inc, await res.text());
    }
    await loadIncidents();
    showToast(`Investigated ${data.incidents.length} incident(s) — see the list below.`, "success");
  } catch (e) {
    showToast("Scan failed: " + e.message, "error");
  } finally {
    btn.disabled = false;
    btn.textContent = "Scan for incidents";
  }
}

// The backend can be briefly unready (e.g. ClickHouse tables mid-reload) --
// retry instead of dying permanently and forcing a manual page refresh.
async function initWithRetry() {
  try {
    await init();
  } catch (e) {
    document.getElementById("meta-sub").textContent = "Failed to load: " + e.message + " -- retrying...";
    setTimeout(initWithRetry, 3000);
  }
}
initWithRetry();
