const LIBRECHAT_URL = 'http://localhost:3080/';
const LANGFUSE_PROJECT_URL = 'http://localhost:3000/project/cmsaz3s760006s707a1nss51c';

const state = {
  currentBucket: null,
  trendChart: null,
  drilldownChart: null,
  radarChart: null,
  lastIncident: null,
  currentDimension: document.getElementById('dimension-select').value,
  currentMetric: document.getElementById('metric-select').value,
  currentFreq: '1h',
  multiTrendChart: null,
  trendLabelBuckets: [],
};

// Cycled per segment so any dimension (up to 16+ countries) stays readable.
const SEGMENT_COLORS = [
  '#4c8be2', '#4caf6e', '#e2a53c', '#a25ee2', '#3ce2c8',
  '#e2574c', '#8be24c', '#e24c9a', '#4c6be2', '#e2c84c',
  '#6ee2b0', '#e28b4c', '#8a8ee2', '#4ce2e2', '#c8a5e2', '#a5c8e2',
];

const fmtMoney = (v) => `$${Number(v).toFixed(2)}`;
const fmtPct = (v) => `${v >= 0 ? '+' : ''}${(v * 100).toFixed(1)}%`;

// pct_of_total_delta's raw sign is delta / sum(delta) — when every segment in
// a dimension moved the same direction (e.g. all declined together), that's
// negative/negative, which comes out POSITIVE even though this segment
// itself declined. Re-sign to match the segment's own delta, so the % (and
// any color derived from it) always describes what THIS segment actually did.
const signedConcentration = (r) => {
  const magnitude = Math.abs(r.pct_of_total_delta);
  return r.delta >= 0 ? magnitude : -magnitude;
};
const fmtBucket = (iso) => iso.replace('T', ' ').slice(0, 16);

async function fetchJSON(url, options) {
  const res = await fetch(url, options);
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${res.status}: ${body}`);
  }
  return res.json();
}

async function selectAnomaly(bucket) {
  state.currentBucket = bucket;
  document.getElementById('incident-view').classList.remove('hidden');

  document.getElementById('incident-bucket').textContent = fmtBucket(bucket);

  let data;
  try {
    data = await fetchJSON(`/api/incident/${encodeURIComponent(bucket)}?freq=${state.currentFreq}`);
  } catch (e) {
    document.getElementById('diagnosis-text').textContent = `Failed to load incident: ${e.message}`;
    return;
  }

  const dayClass = data.detection.is_weekend ? 'weekend' : 'weekday';
  document.getElementById('incident-bucket').innerHTML =
    `${fmtBucket(bucket)} <span class="day-badge ${dayClass}">${data.detection.day_name} · ${dayClass}</span>`;

  state.lastIncident = data;

  // A fresh incident invalidates any AI narrative generated for the previous one.
  const aiBox = document.getElementById('ai-incident-summary');
  aiBox.classList.add('hidden');
  aiBox.innerHTML = '';
  document.getElementById('ai-summary-btn').disabled = false;
  document.getElementById('ai-summary-btn').textContent = 'Generate AI summary';

  renderKPIs(data.detection);
  renderDiagnosis(data);
  renderTrend(data.trend);
  renderFactors(data.factors, data.primary_factor, data.ruled_out_factors);
  renderRadar(data.contribution);
  // 'overall' has no breakdown, so the drill-down panel always drills into
  // whatever the drill-down's OWN dropdown is set to (it never offers
  // 'overall' as an option) rather than the main trend dimension — this is
  // what lets the drill-down default to "ad_format" even while the main
  // trend chart still defaults to "Overall".
  drillDimension(document.getElementById('drilldown-dimension-select').value, { syncMainDimension: state.currentDimension !== 'overall' });

  document.getElementById('incident-view').scrollIntoView({ behavior: 'auto', block: 'start' });
}

const DIMENSION_PLAIN_LABELS = {
  ad_format: 'ad format',
  campaign_type: 'campaign type',
  category: 'app category',
  country: 'country',
  device_model: 'device model',
  os_version: 'operating system',
  publisher_tier: 'publisher quality tier',
  region: 'region',
  vertical: 'advertiser industry',
};

function buildLibreChatContext(bucket, data) {
  const d = data.detection;
  const topByDim = {};
  for (const r of data.contribution) {
    if (r.rnk === 1) topByDim[r.dimension_name] = r;
  }
  const dimLines = Object.values(topByDim)
    .sort((a, b) => Math.abs(b.pct_of_total_delta) - Math.abs(a.pct_of_total_delta))
    .map((r) => {
      const label = DIMENSION_PLAIN_LABELS[r.dimension_name] || r.dimension_name;
      return `  - By ${label}: mostly "${r.dimension_value}" — that one value explains ${fmtPct(signedConcentration(r))} of the change seen in that breakdown`;
    })
    .join('\n');

  const f = data.factors || {};
  const factorLine = (plainLabel, v) =>
    (v === null || v === undefined ? null : `  - ${plainLabel}: ${fmtPct(v)} different from a normal hour like this one`);
  const factorLines = [
    factorLine('How many people asked for an ad (volume)', f.requests_pct_change),
    factorLine('How many of those requests actually got an ad (fill rate)', f.fill_rate_pct_change),
    factorLine('The price per 1,000 ad views (eCPM)', f.ecpm_pct_change),
  ].filter(Boolean).join('\n');

  const direction = d.pct_dev >= 0 ? 'higher' : 'lower';
  const bucketSql = bucket.replace('T', ' ');
  const dateSql = bucket.slice(0, 10);

  return [
    `Hi! I'm looking at one specific hour where our ad revenue looked unusual, and I'd like your help digging deeper with more charts, in plain English.`,
    ``,
    `THE SITUATION (in plain terms):`,
    `On ${d.day_name} (a ${d.is_weekend ? 'weekend' : 'weekday'}), during the hour of ${bucket}, we made ${fmtMoney(d.revenue)}. `
    + `A normal hour like this one usually makes about ${fmtMoney(d.expected_revenue)} — so this was ${fmtPct(d.pct_dev)} ${direction} than usual. `
    + `That's a big enough gap that it's very unlikely to just be random noise (confidence score: ${d.robust_z.toFixed(1)} — anything above 3 means "this is a real change, not luck").`,
    ``,
    `WHAT OUR DASHBOARD ALREADY FIGURED OUT:`,
    data.diagnosis,
    ``,
    `WHAT CHANGED (compared to a normal hour like this one):`,
    factorLines,
    ``,
    `WHICH SPECIFIC THINGS SEEM MOST RESPONSIBLE (e.g. which country, which app, which advertiser):`,
    dimLines,
    ``,
    `WHAT I'D LIKE YOU TO DO:`,
    `Please run the exact queries below — don't improvise your own SQL, and do NOT query any table named `
    + `"ad_events" under ANY database (not quvia_hack.ad_events, not ganesh.ad_events, and not py.ad_events `
    + `either — every database has a copy of that raw 9-million-row table sitting there, but none of them `
    + `are what powers this dashboard; ignore all of them even though the name is tempting). These queries `
    + `already read the correct pre-computed tables in the "py" database, so they're fast and will match `
    + `this dashboard's numbers exactly.`,
    ``,
    `QUERY A — was it volume, fill rate, or price? (already precomputed, just read it):`,
    '```sql',
    `SELECT bucket, requests, avg_requests, z_requests, pct_requests,`,
    `       revenue, avg_revenue, z_revenue, pct_revenue,`,
    `       fill_rate, avg_fill_rate, z_fill_rate, pct_fill_rate,`,
    `       ecpm, avg_ecpm, z_ecpm, pct_ecpm`,
    `FROM py.anomaly_overall_1h`,
    `WHERE segment = 'all' AND bucket = '${bucketSql}'`,
    '```',
    ``,
    `QUERY B — every one of the 9 categories, ranked by who's most responsible. Here's the pattern, `
    + `worked out for "country" — the "expected" value is a rolling average over this exact same hour-of-`
    + `week slot in prior weeks (segment = weekend-or-not + hour-of-day), which is exactly how this `
    + `pipeline's own anomaly detection works:`,
    '```sql',
    `WITH stats AS (`,
    `    SELECT bucket, segment, revenue,`,
    `           row_number() OVER (PARTITION BY segment, toDayOfWeek(bucket) IN (6,7), toHour(bucket) ORDER BY bucket ASC) AS rn,`,
    `           avg(revenue) OVER w AS revenue_expected`,
    `    FROM py.agg_country_1h`,
    `    WINDOW w AS (PARTITION BY segment, toDayOfWeek(bucket) IN (6,7), toHour(bucket) ORDER BY bucket ASC ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING)`,
    `)`,
    `SELECT 'country' AS dimension_name, segment AS dimension_value, revenue, revenue_expected,`,
    `       (revenue - revenue_expected) AS delta`,
    `FROM stats`,
    `WHERE bucket = '${bucketSql}' AND rn > 4`,
    '```',
    `Please repeat this EXACT same query 8 more times, only swapping the table name and the `
    + `dimension_name label each time, for: py.agg_ad_format_1h ('ad_format'), py.agg_campaign_type_1h `
    + `('campaign_type'), py.agg_category_1h ('category'), py.agg_device_model_1h ('device_model'), `
    + `py.agg_os_version_1h ('os_version'), py.agg_publisher_tier_1h ('publisher_tier'), `
    + `py.agg_region_1h ('region'), py.agg_vertical_1h ('vertical'). Then, keeping each of the 9 `
    + `categories' results SEPARATE from each other (don't mix them into one shared total), rank the `
    + `values within each category by abs(delta) descending, and work out what share of that one `
    + `category's total delta each value explains.`,
    ``,
    `QUERY C — full day, hour by hour, actual vs. expected (use this to draw a LINE CHART):`,
    '```sql',
    `WITH stats AS (`,
    `    SELECT bucket, segment, revenue,`,
    `           row_number() OVER (PARTITION BY segment, toDayOfWeek(bucket) IN (6,7), toHour(bucket) ORDER BY bucket ASC) AS rn,`,
    `           avg(revenue) OVER w AS expected`,
    `    FROM py.agg_overall_1h`,
    `    WINDOW w AS (PARTITION BY segment, toDayOfWeek(bucket) IN (6,7), toHour(bucket) ORDER BY bucket ASC ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING)`,
    `)`,
    `SELECT bucket, revenue, expected`,
    `FROM stats`,
    `WHERE toDate(bucket) = '${dateSql}' AND segment = 'all' AND rn > 4`,
    `ORDER BY bucket`,
    '```',
    `Draw the result as a LINE CHART (actual vs. expected, ~24 points). Then draw a second LINE CHART the `
    + `same way for whichever 1-2 categories Query B found most responsible, using that category's `
    + `py.agg_<dim>_1h table filtered to that one segment value instead of 'all'.`,
    ``,
    `Then, pulling QUERY A, B, and C together, give me your answer in this shape:`,
    `1. A chart (you already drew two above — that counts).`,
    `2. A SHORT written answer — 3-5 sentences max, plain English, no long essay: which specific thing `
    + `is the real story here, and why. Save the detail for follow-up questions, don't front-load it.`,
    ``,
    `I'll probably ask follow-up questions after this. For every one of those too: keep answering with a `
    + `short chart + short answer in this same style, always look up the real numbers live using this `
    + `same style of query (never any ad_events table, in any database), and never answer from memory or `
    + `general knowledge.`,
  ].join('\n');
}

function showToast(message, ms = 4500) {
  const el = document.getElementById('toast');
  el.textContent = message;
  el.classList.remove('hidden');
  clearTimeout(showToast._t);
  showToast._t = setTimeout(() => el.classList.add('hidden'), ms);
}

async function toggleLibreChatPanel() {
  if (!state.lastIncident || !state.currentBucket) {
    showToast('No incident loaded yet — select a flagged hour first.');
    return;
  }

  const panel = document.getElementById('librechat-panel');
  const iframe = document.getElementById('librechat-iframe');
  panel.classList.toggle('hidden');

  // Load the iframe once (no query params) — we deliberately don't reload it
  // on every incident switch; use the Copy Prompt button to hand it whichever
  // incident you want to ask about. Before the first load, silently log into
  // a shared LibreChat demo account server-side so its own sign-in screen
  // never has to appear here.
  if (!iframe.src) {
    try {
      await fetch('/api/librechat-auto-login', { method: 'POST' });
    } catch (e) {
      // Best-effort — if this fails, the iframe just falls back to showing
      // LibreChat's normal login screen instead of breaking.
    }
    iframe.src = LIBRECHAT_URL;
  }
}

function copyText(text) {
  // navigator.clipboard is only defined in secure contexts (https, or exactly
  // "localhost"/"127.0.0.1") — accessing the dashboard via a LAN IP or any
  // other hostname makes it undefined, which throws with zero visible
  // feedback. Fall back to the legacy execCommand approach in that case.
  if (navigator.clipboard && navigator.clipboard.writeText) {
    return navigator.clipboard.writeText(text);
  }
  const ta = document.createElement('textarea');
  ta.value = text;
  ta.style.position = 'fixed';
  ta.style.opacity = '0';
  document.body.appendChild(ta);
  ta.focus();
  ta.select();
  let ok = false;
  try {
    ok = document.execCommand('copy');
  } catch (e) {
    ok = false;
  }
  document.body.removeChild(ta);
  return ok ? Promise.resolve() : Promise.reject(new Error('execCommand copy failed'));
}

function copyLibreChatPrompt() {
  if (!state.lastIncident || !state.currentBucket) {
    showToast('No incident loaded yet — select a flagged hour first.');
    return;
  }
  const prompt = buildLibreChatContext(state.currentBucket, state.lastIncident);
  try {
    copyText(prompt).then(
      () => showToast('Prompt for this incident copied — paste it into LibreChat and hit send.'),
      (e) => showToast(`Copy failed (${e.message}) — is the page loaded from "localhost"?`)
    );
  } catch (e) {
    showToast(`Copy failed (${e.message}) — is the page loaded from "localhost"?`);
  }
}

async function generateIncidentSummary() {
  if (!state.lastIncident) {
    showToast('No incident loaded yet — select a flagged hour first.');
    return;
  }
  const btn = document.getElementById('ai-summary-btn');
  const box = document.getElementById('ai-incident-summary');
  btn.disabled = true;
  btn.textContent = 'Generating…';
  box.className = 'llm-summary loading';
  box.classList.remove('hidden');
  box.textContent = 'Generating summary…';

  const { detection, factors, contribution } = state.lastIncident;
  let data;
  try {
    data = await fetchJSON('/api/summarize-incident', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ detection, factors, contribution }),
    });
  } catch (e) {
    box.className = 'llm-summary unavailable';
    box.textContent = `Summary unavailable: ${e.message}`;
    btn.disabled = false;
    btn.textContent = 'Retry AI summary';
    return;
  }

  if (!data.available) {
    box.className = 'llm-summary unavailable';
    box.textContent = 'AI summary unavailable — ANTHROPIC_API_KEY isn\'t configured on the backend.';
    btn.disabled = false;
    btn.textContent = 'Retry AI summary';
    return;
  }

  box.className = 'llm-summary';
  box.innerHTML = `<span class="llm-label">AI summary</span>${data.summary}`;
  btn.textContent = 'Regenerate AI summary';
  btn.disabled = false;
}

document.getElementById('langfuse-btn').addEventListener('click', () => {
  window.open(LANGFUSE_PROJECT_URL, '_blank', 'noopener');
});

document.getElementById('ai-summary-btn').addEventListener('click', generateIncidentSummary);
document.getElementById('librechat-btn').addEventListener('click', toggleLibreChatPanel);
document.getElementById('librechat-copy').addEventListener('click', copyLibreChatPrompt);
document.getElementById('librechat-close').addEventListener('click', () => {
  document.getElementById('librechat-panel').classList.add('hidden');
});

function renderKPIs(d) {
  const el = document.getElementById('kpi-strip');
  const pctClass = d.pct_dev >= 0 ? 'positive' : 'negative';
  el.innerHTML = `
    <div class="kpi-tile"><div class="label">Revenue</div><div class="value">${fmtMoney(d.revenue)}</div></div>
    <div class="kpi-tile"><div class="label">Expected</div><div class="value">${fmtMoney(d.expected_revenue)}</div></div>
    <div class="kpi-tile"><div class="label">Deviation</div><div class="value pct-dev ${pctClass}">${fmtPct(d.pct_dev)}</div></div>
    <div class="kpi-tile"><div class="label">Robust Z</div><div class="value">${d.robust_z.toFixed(2)}</div></div>
  `;
}

function renderDiagnosis(data) {
  document.getElementById('diagnosis-text').textContent = data.diagnosis;
  const chips = document.getElementById('ruled-out-chips');
  chips.innerHTML = '';
  const items = [
    ...(data.ruled_out_factors || []).map((f) => `ruled out: ${FACTOR_LABELS[f] || f.replace('_pct_change', '').replaceAll('_', ' ')}`),
    ...(data.ruled_out_dimensions || []).map((d) => `ruled out: ${d}`),
  ];
  for (const text of items) {
    const chip = document.createElement('span');
    chip.className = 'chip';
    chip.textContent = text;
    chips.appendChild(chip);
  }
}

function renderTrend(trend) {
  const ctx = document.getElementById('trend-chart');
  const labels = trend.map((r) => r.bucket.slice(11, 16));
  const actual = trend.map((r) => r.revenue);
  const expected = trend.map((r) => r.expected);

  if (state.trendChart) state.trendChart.destroy();
  state.trendChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [
        { label: 'Actual', data: actual, borderColor: '#4c8be2', backgroundColor: 'transparent', tension: 0.25 },
        { label: 'Expected', data: expected, borderColor: '#8b909a', borderDash: [5, 4], backgroundColor: 'transparent', tension: 0.25 },
      ],
    },
    options: {
      responsive: true,
      plugins: { legend: { labels: { color: '#e7e9ec' } } },
      scales: {
        x: { ticks: { color: '#8b909a' }, grid: { color: '#24272d' } },
        y: { ticks: { color: '#8b909a' }, grid: { color: '#24272d' } },
      },
    },
  });
}

const FACTOR_LABELS = {
  requests_pct_change: 'Request volume',
  fill_rate_pct_change: 'Fill rate',
  ecpm_pct_change: 'Price per 1,000 views (eCPM)',
};

function renderFactors(factors, primary, ruledOut) {
  const el = document.getElementById('factor-tiles');
  if (!factors) {
    el.innerHTML = '<div class="loading">No factor data for this bucket.</div>';
    return;
  }
  el.innerHTML = '';
  for (const key of Object.keys(FACTOR_LABELS)) {
    const value = factors[key];
    if (value === null || value === undefined) continue;
    const tile = document.createElement('div');
    tile.className = 'factor-tile';
    if (key === primary) tile.classList.add('primary');
    if ((ruledOut || []).includes(key)) tile.classList.add('ruled-out');
    tile.innerHTML = `<span class="name">${FACTOR_LABELS[key]}</span><span class="pct">${fmtPct(value)}</span>`;
    el.appendChild(tile);
  }
}

function renderRadar(contributionRows) {
  const topByDim = {};
  for (const r of contributionRows || []) {
    if (r.rnk === 1) topByDim[r.dimension_name] = r;
  }

  const dims = Object.keys(DIMENSION_PLAIN_LABELS);
  const values = dims.map((d) => (topByDim[d] ? signedConcentration(topByDim[d]) * 100 : 0));
  const pointColors = values.map((v) => (v >= 0 ? '#4caf6e' : '#e2574c'));

  const ctx = document.getElementById('radar-chart');
  if (state.radarChart) state.radarChart.destroy();
  state.radarChart = new Chart(ctx, {
    type: 'radar',
    data: {
      labels: dims.map((d) => d.replaceAll('_', ' ')),
      datasets: [{
        label: '% of dimension delta (top segment)',
        data: values,
        borderColor: '#8b909a',
        backgroundColor: 'rgba(139,144,154,0.12)',
        pointBackgroundColor: pointColors,
        pointBorderColor: pointColors,
        pointRadius: 4,
        borderWidth: 1.5,
      }],
    },
    options: {
      responsive: true,
      interaction: { mode: 'nearest', intersect: false },
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: (item) => `${item.raw >= 0 ? '+' : ''}${item.raw.toFixed(0)}% of ${item.label} deviation`,
          },
        },
      },
      scales: {
        r: {
          angleLines: { color: '#24272d' },
          grid: { color: '#24272d' },
          pointLabels: { color: '#e7e9ec', font: { size: 10.5 } },
          ticks: { color: '#8b909a', backdropColor: 'transparent', maxTicksLimit: 4 },
          suggestedMin: -100,
          suggestedMax: 100,
        },
      },
      onClick: (evt, elements) => {
        if (!elements.length) return;
        const dim = dims[elements[0].index];
        if (dim) setDimension(dim);
      },
    },
  });
}

function clearDrilldown() {
  document.getElementById('drilldown-title').textContent = 'Drill-down';
  if (state.drilldownChart) {
    state.drilldownChart.destroy();
    state.drilldownChart = null;
  }
  document.getElementById('drilldown-table').innerHTML =
    '<p class="loading">Select a specific category above to see segment-level detail.</p>';
  renderDrilldownSummary._seq++; // invalidate any in-flight summary request
  document.getElementById('drilldown-summary').classList.add('hidden');
}

async function drillDimension(dimensionName, { syncMainDimension = true } = {}) {
  // syncMainDimension=false lets the drill-down panel load its own default
  // (ad_format) on incident open without dragging the main trend chart's
  // "Overall" selection along with it — the two dropdowns only stay synced
  // when the user actively picks a dimension via either one.
  if (syncMainDimension) {
    state.currentDimension = dimensionName;
    document.getElementById('dimension-select').value = dimensionName;
  }
  document.getElementById('drilldown-dimension-select').value = dimensionName;
  document.getElementById('drilldown-title').textContent = `Drill-down — ${dimensionName}`;

  let rows;
  try {
    rows = await fetchJSON(
      `/api/dimension/${encodeURIComponent(state.currentBucket)}/${dimensionName}?freq=${state.currentFreq}`
    );
  } catch (e) {
    document.getElementById('drilldown-table').textContent = `Failed to load: ${e.message}`;
    return;
  }

  const ctx = document.getElementById('drilldown-chart');
  const gradientFor = (color) => {
    const g = ctx.getContext('2d').createLinearGradient(0, 0, ctx.width || 400, 0);
    g.addColorStop(0, `${color}55`);
    g.addColorStop(1, color);
    return g;
  };
  if (state.drilldownChart) state.drilldownChart.destroy();
  state.drilldownChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: rows.map((r) => r.dimension_value),
      datasets: [{
        label: 'Delta vs expected ($)',
        data: rows.map((r) => r.delta),
        backgroundColor: rows.map((r) => gradientFor(r.delta >= 0 ? '#4caf6e' : '#e2574c')),
        borderRadius: 6,
        borderSkipped: false,
        barThickness: 14,
        maxBarThickness: 16,
      }],
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: '#16181c',
          borderColor: '#24272d',
          borderWidth: 1,
          titleColor: '#e7e9ec',
          bodyColor: '#e7e9ec',
          padding: 10,
          cornerRadius: 6,
          callbacks: { label: (item) => `${item.raw >= 0 ? '+' : ''}$${item.raw.toFixed(2)} vs expected` },
        },
      },
      scales: {
        x: { ticks: { color: '#8b909a' }, grid: { color: '#24272d' } },
        y: {
          ticks: { color: '#e7e9ec' },
          grid: { display: false },
          categoryPercentage: 0.5,
          barPercentage: 0.9,
        },
      },
    },
  });

  const table = document.getElementById('drilldown-table');
  table.innerHTML = `
    <table>
      <thead><tr>
        <th>${dimensionName}</th><th class="mono">Revenue</th><th class="mono">Expected</th>
        <th class="mono">Delta</th><th class="mono">% of delta</th><th class="mono">Fill rate</th><th class="mono">eCPM</th>
      </tr></thead>
      <tbody>
        ${rows.map((r) => `
          <tr>
            <td>${r.dimension_value}</td>
            <td class="mono">${fmtMoney(r.revenue_now)}</td>
            <td class="mono">${fmtMoney(r.revenue_expected)}</td>
            <td class="mono">${fmtMoney(r.delta)}</td>
            <td class="mono">${fmtPct(signedConcentration(r))}</td>
            <td class="mono">${r.fill_rate_now != null ? (r.fill_rate_now * 100).toFixed(1) + '%' : '—'}</td>
            <td class="mono">${r.ecpm_now != null ? r.ecpm_now.toFixed(2) : '—'}</td>
          </tr>`).join('')}
      </tbody>
    </table>
  `;

  renderDrilldownSummary(dimensionName, rows);
}

async function renderDrilldownSummary(dimensionName, rows) {
  const el = document.getElementById('drilldown-summary');
  const requestId = ++renderDrilldownSummary._seq | 0;
  el.className = 'llm-summary loading';
  el.classList.remove('hidden');
  el.textContent = 'Generating summary…';

  let data;
  try {
    data = await fetchJSON('/api/summarize-dimension', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ dimension_name: dimensionName, rows }),
    });
  } catch (e) {
    if (requestId !== renderDrilldownSummary._seq) return; // a newer dimension was selected meanwhile
    el.className = 'llm-summary unavailable';
    el.textContent = `Summary unavailable: ${e.message}`;
    return;
  }
  if (requestId !== renderDrilldownSummary._seq) return;

  if (!data.available) {
    el.className = 'llm-summary unavailable';
    el.textContent = 'AI summary unavailable — ANTHROPIC_API_KEY isn\'t configured on the backend.';
    return;
  }
  el.className = 'llm-summary';
  el.innerHTML = `<span class="llm-label">AI summary</span>${data.summary}`;
}
renderDrilldownSummary._seq = 0;

function getRangeParams() {
  const startDate = document.getElementById('range-start').value;
  const endDate = document.getElementById('range-end').value;
  if (!startDate || !endDate) return null;
  // start-of-day through end-of-day so the selected end date is fully included.
  return { start: `${startDate}T00:00:00`, end: `${endDate}T23:00:00`, freq: state.currentFreq };
}

async function loadDimensionTrend() {
  const range = getRangeParams();
  if (!state.currentDimension || !range) return;
  document.getElementById('trend-title').textContent = `Trend — ${state.currentDimension} (${state.currentMetric})`;
  const url = `/api/dimension-trend/${state.currentDimension}`
    + `?start=${encodeURIComponent(range.start)}&end=${encodeURIComponent(range.end)}&freq=${range.freq}`
    + `&metric=${state.currentMetric}`;
  let data;
  try {
    data = await fetchJSON(url);
  } catch (e) {
    console.error('dimension-trend failed', e);
    showToast(`Failed to load category trend: ${e.message}`);
    return;
  }
  renderMultiTrendChart(data.series, data.anomalies);
}

// 3-tier color scale, anchored on the same z=3 line the backend already uses
// to flag an hour as anomalous (see baseline_1h / anomaly_<dim>_<freq> — the
// "robust_z > 3" rule from CLAUDE.md). |z| below half that is a mild, barely-
// there deviation (yellow); up to the threshold it's a real but not extreme
// one (orange-red); at or past it, it's the same magnitude that would flag
// the whole hour on its own (darkest red).
const Z_FLAG_THRESHOLD = 3;
const ANOMALY_YELLOW = '#e2c23c';
const ANOMALY_ORANGE_RED = '#c2453c';
const ANOMALY_DARK_RED = '#7a1410';
function colorForZ(absZ) {
  if (absZ >= Z_FLAG_THRESHOLD) return ANOMALY_DARK_RED;
  if (absZ >= Z_FLAG_THRESHOLD * 0.5) return ANOMALY_ORANGE_RED;
  return ANOMALY_YELLOW;
}

function renderMultiTrendChart(series, anomalies) {
  // Only negative deviations (value below expected) get highlighted — a
  // negative-only set, since the green (positive) highlight was removed.
  // Keyed by z-score magnitude so the point color can scale with severity.
  const negativeAnomalies = new Map(
    anomalies
      .filter((a) => a.value < a.avg_value)
      .map((a) => [`${a.bucket}|${a.segment}`, Math.abs(a.z_value)])
  );

  const bySegment = {};
  const labelsSet = new Set();
  for (const row of series) {
    if (!bySegment[row.segment]) bySegment[row.segment] = {};
    bySegment[row.segment][row.bucket] = row.value;
    labelsSet.add(row.bucket);
  }
  const labels = Array.from(labelsSet).sort();
  const segments = Object.keys(bySegment).sort();
  state.trendLabelBuckets = labels; // full ISO buckets, aligned by index with the (truncated) display labels

  const datasets = segments.map((seg, i) => {
    const color = SEGMENT_COLORS[i % SEGMENT_COLORS.length];
    const values = labels.map((b) => (bySegment[seg][b] !== undefined ? bySegment[seg][b] : null));
    const pointRadius = labels.map((b) => (negativeAnomalies.has(`${b}|${seg}`) ? 6 : 0));
    const pointColor = labels.map((b) => {
      const absZ = negativeAnomalies.get(`${b}|${seg}`);
      return absZ !== undefined ? colorForZ(absZ) : color;
    });
    return {
      label: seg,
      data: values,
      borderColor: color,
      backgroundColor: 'transparent',
      borderWidth: 1.5,
      pointRadius,
      pointHoverRadius: 7,
      pointBackgroundColor: pointColor,
      pointBorderColor: pointColor,
      tension: 0.2,
      spanGaps: true,
    };
  });

  const ctx = document.getElementById('trend-chart-multi');
  if (state.multiTrendChart) state.multiTrendChart.destroy();
  state.multiTrendChart = new Chart(ctx, {
    type: 'line',
    data: { labels: labels.map((b) => fmtBucket(b).slice(5)), datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'nearest', intersect: false },
      plugins: {
        legend: {
          labels: { color: '#e7e9ec', boxWidth: 10, font: { size: 10 } },
          title: { display: true, text: 'Category', color: '#8b909a', font: { size: 11 } },
        },
      },
      scales: {
        x: { ticks: { color: '#8b909a', maxTicksLimit: 14 }, grid: { color: '#24272d' } },
        y: { ticks: { color: '#8b909a' }, grid: { color: '#24272d' } },
      },
      onClick: (evt, elements) => {
        if (!elements.length) return;
        const bucket = state.trendLabelBuckets[elements[0].index];
        if (bucket) selectAnomaly(bucket);
      },
    },
  });
}

document.getElementById('range-start').addEventListener('change', loadDimensionTrend);
document.getElementById('range-end').addEventListener('change', loadDimensionTrend);

document.querySelectorAll('#freq-toggle .toggle-btn').forEach((btn) => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('#freq-toggle .toggle-btn').forEach((b) => b.classList.remove('active'));
    btn.classList.add('active');
    state.currentFreq = btn.dataset.freq;
    loadDimensionTrend();
    // The Contribution strip and its drill-down are keyed off the incident's
    // exact time, snapped to this agg level — not the calendar range — so
    // changing it means reloading the currently-open incident, if any.
    if (!document.getElementById('incident-view').classList.contains('hidden')) {
      selectAnomaly(state.currentBucket);
    }
  });
});

function setDimension(newDim) {
  state.currentDimension = newDim;
  document.getElementById('dimension-select').value = newDim;
  // 'overall' has no breakdown, so it isn't an option in the drill-down's
  // own dropdown — leave that selector showing whatever real dimension it
  // last had.
  if (newDim !== 'overall') document.getElementById('drilldown-dimension-select').value = newDim;
  loadDimensionTrend();
  const incidentLoaded = !document.getElementById('incident-view').classList.contains('hidden');
  if (incidentLoaded) {
    if (newDim !== 'overall') drillDimension(newDim);
    else clearDrilldown();
  }
}

document.getElementById('dimension-select').addEventListener('change', (e) => setDimension(e.target.value));
document.getElementById('drilldown-dimension-select').addEventListener('change', (e) => setDimension(e.target.value));

document.getElementById('metric-select').addEventListener('change', (e) => {
  state.currentMetric = e.target.value;
  loadDimensionTrend();
});

function addDaysToDateStr(dateStr, days) {
  const d = new Date(`${dateStr}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}

async function checkHealth() {
  const badge = document.getElementById('health-badge');
  const label = document.getElementById('health-label');
  try {
    const res = await fetch('/api/health');
    if (!res.ok) throw new Error(`${res.status}`);
    await res.json();
    badge.classList.add('healthy');
    label.textContent = 'Pipeline healthy';
  } catch (e) {
    badge.classList.add('unhealthy');
    label.textContent = 'Pipeline unreachable';
  }
}

async function init() {
  checkHealth();

  let range;
  try {
    range = await fetchJSON('/api/data-range');
  } catch (e) {
    showToast(`Failed to load data range: ${e.message}`);
    return;
  }

  const startInput = document.getElementById('range-start');
  const endInput = document.getElementById('range-end');
  // Deliberately no min/max clamp on the pickers — the native date input
  // was disabling every day outside the known dataset window (2026-06-01 to
  // 2026-07-05), which blocked picking a date to check whether new data has
  // landed there. A date with no data just renders an empty chart, which is
  // fine.

  // Default to the last 7 days of available data.
  endInput.value = range.max;
  startInput.value = addDaysToDateStr(range.max, -7);

  loadDimensionTrend();
}

init();
