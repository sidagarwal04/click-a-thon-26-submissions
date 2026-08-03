/* ===== THEME ===== */
(() => {
  const root  = document.documentElement;
  const saved = localStorage.getItem('rca-theme');
  if (saved) root.setAttribute('data-theme', saved);
  document.getElementById('theme-toggle')?.addEventListener('click', () => {
    const dark = root.getAttribute('data-theme') === 'dark'
      || (!root.hasAttribute('data-theme') && matchMedia('(prefers-color-scheme: dark)').matches);
    const next = dark ? 'light' : 'dark';
    root.setAttribute('data-theme', next);
    localStorage.setItem('rca-theme', next);
  });
})();

/* ===== TRANSLATION (narration.md section 3) ===== */
const METRIC_SHORT = {
  requests: 'requests', fill_rate: 'fill rate', render_rate: 'render rate',
  ctr: 'CTR', ecpm: 'eCPM', rpr: 'RPR', revenue: 'revenue',
};
const METRIC_PLAIN = {
  requests: 'ad requests', fill_rate: 'fill rate', render_rate: 'render rate',
  ctr: 'click-through rate', ecpm: 'eCPM', rpr: 'revenue per request', revenue: 'revenue',
};
const DIM_LABEL = {
  os_version: 'OS version', device_model: 'device', region: 'region', country: 'country',
  category: 'app category', publisher_tier: 'publisher tier', ad_format: 'ad format',
  vertical: 'advertiser vertical', campaign_type: 'campaign type',
};
const DIM_PLURAL = {
  os_version: 'OS versions', device_model: 'devices', region: 'regions', country: 'countries',
  category: 'app categories', publisher_tier: 'publisher tiers', ad_format: 'ad formats',
  vertical: 'verticals', campaign_type: 'campaign types',
};
const VERDICT_COLOR = {
  confirmed: 'var(--anomaly)', weak: 'var(--warn)', intersection_descend: 'var(--warn)',
  ambiguous_no_slice_clears: 'var(--ink-3)', no_attribution: 'var(--ink-3)',
};
const VERDICT_LABEL = {
  confirmed: 'confirmed', weak: 'weak signal', intersection_descend: 'intersection',
  ambiguous_no_slice_clears: 'diffuse', no_attribution: 'no attribution',
};
const WORDS = ['zero','one','two','three','four','five','six','seven','eight','nine','ten',
               'eleven','twelve'];

/* ===== HELPERS ===== */
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const ml  = m => METRIC_SHORT[m] || m;
const mp  = m => METRIC_PLAIN[m] || m;
const dl  = d => DIM_LABEL[d] || d;
const dp  = d => DIM_PLURAL[d] || (d + 's');
const nw  = n => (n >= 0 && n < WORDS.length) ? WORDS[n] : String(n);
const cap = s => String(s).charAt(0).toUpperCase() + String(s).slice(1);
const MON = ['','Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];

function short(d) {
  if (!d) return '?';
  const p = String(d).split('-');
  return `${MON[+p[1]]} ${+p[2]}`;
}
function dateRange(a, b) { return a === b ? short(a) : `${short(a)} – ${short(b)}`; }
function daysBetween(a, b) {
  return Math.round((new Date(b) - new Date(a)) / 86400000);
}

/* narration.md section 4 */
/* Any column can arrive null from ClickHouse (Nullable, or absent from a view).
   num() returns a finite number or null; fx() formats or yields an em-dash-free
   placeholder. Nothing downstream should call .toFixed on a raw field. */
function num(v) {
  if (v === null || v === undefined || v === '') return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}
function fx(v, d = 1) {
  const n = num(v);
  return n === null ? '--' : n.toFixed(d);
}

const isRate = m => ['fill_rate','render_rate','ctr'].includes(m);

/* Enough decimals that two nearby values never collapse to the same string.
   rpr sits around 0.0019, so a flat 4 decimals would print 0.0019 for both
   sides of the exclusion test and destroy the proof. */
function decimals(v, m) {
  if (m === 'requests') return 0;
  if (m === 'revenue')  return 2;
  const a = Math.abs(v);
  if (a === 0)    return 4;
  if (a < 0.001)  return 7;
  if (a < 0.01)   return 6;
  if (a < 1)      return 4;
  return 4;
}
function fmtMetric(v, m) {
  if (v == null) return '—';
  if (m === 'requests') return Math.round(v).toLocaleString();
  return v.toFixed(decimals(v, m));
}
function fmtPretty(v, m) {
  if (v == null) return '—';
  if (isRate(m))        return (v * 100).toFixed(2) + '%';
  if (m === 'requests') return Math.round(v).toLocaleString();
  return v.toFixed(decimals(v, m));
}
function fmtPct(v, dp2 = 2) {
  if (v == null) return '—';
  return (v > 0 ? '+' : '−') + Math.abs(Number(v)).toFixed(dp2) + '%';
}
function fmtMs(ms) {
  if (ms == null) return '—';
  return ms < 1000 ? ms + 'ms' : (ms / 1000).toFixed(2) + 's';
}
function stripDashes(s) {
  return String(s || '').replace(/\s+[—–]\s+/g, '. ').replace(/\.\s*\./g, '.');
}

/* ===== SVG ===== */
const NS = 'http://www.w3.org/2000/svg';
const el = (tag, attrs = {}) => {
  const n = document.createElementNS(NS, tag);
  for (const k in attrs) n.setAttribute(k, attrs[k]);
  return n;
};
const txt = (s, attrs) => { const t = el('text', attrs); t.textContent = s; return t; };

/* ===== OVERVIEW — "Every metric, every day" ===== */
function drawOverview(incidents, rows) {
  const host = document.getElementById('timeline');
  host.textContent = '';
  if (!rows || rows.length < 2) {
    host.innerHTML = '<div class="empty-state">Time series unavailable.</div>';
    return;
  }

  const METRICS = [
    { key: 'requests',  label: 'requests'  },
    { key: 'fill_rate', label: 'fill rate' },
    { key: 'ecpm',      label: 'eCPM'      },
    { key: 'revenue',   label: 'revenue'   },
  ].filter(m => rows.some(r => r[m.key] != null));

  const dates = rows.map(r => r.d), n = dates.length;
  const W = 1160, L = 96, R = 26, T = 30, B = 30, rowH = 42;
  const H = T + METRICS.length * rowH + B;
  const X = i => L + (i / (n - 1)) * (W - L - R);

  const svg = el('svg', { viewBox: `0 0 ${W} ${H}` });

  /* incident bands + letters, behind the lines */
  incidents.forEach(inc => {
    const c  = VERDICT_COLOR[inc.verdict] || 'var(--ink-3)';
    let i0 = dates.findIndex(d => d >= inc.window_start);
    let i1 = dates.findIndex(d => d > inc.window_end);
    if (i0 < 0) return;
    if (i1 < 0) i1 = n;
    const x0 = X(i0), x1 = X(Math.min(i1, n - 1));
    svg.appendChild(el('rect', { x: x0, y: T, width: Math.max(x1 - x0, 6),
      height: H - T - B, fill: c, opacity: 0.13, rx: 2 }));
    svg.appendChild(txt(inc._letter, { x: (x0 + x1) / 2, y: T - 9,
      'text-anchor': 'middle', class: 'axis-t', fill: c, 'font-weight': '700', 'font-size': '11' }));
  });

  METRICS.forEach((m, mi) => {
    const yTop = T + mi * rowH, yMid = yTop + rowH / 2;
    const vals = rows.map(r => r[m.key]);
    const ok   = vals.filter(v => v != null);
    if (!ok.length) return;
    const lo = Math.min(...ok), hi = Math.max(...ok);
    const pad = (hi - lo) * 0.22 || Math.abs(hi) * 0.02 || 1;
    const Y = v => yTop + 6 + (1 - (v - (lo - pad)) / ((hi - lo) + 2 * pad)) * (rowH - 12);

    svg.appendChild(txt(m.label, { x: L - 12, y: yMid + 3.5,
      'text-anchor': 'end', class: 'axis-t' }));

    /* baseline-coloured full series */
    let d = '';
    vals.forEach((v, i) => { if (v != null) d += (d ? ' L' : 'M') + X(i) + ',' + Y(v); });
    svg.appendChild(el('path', { d, fill: 'none', stroke: 'var(--normal)',
      'stroke-width': 1.5, 'stroke-linejoin': 'round' }));

    /* incident-window overlay in the verdict colour */
    incidents.forEach(inc => {
      const c = VERDICT_COLOR[inc.verdict] || 'var(--ink-3)';
      let a = dates.findIndex(x => x >= inc.window_start);
      let b = dates.findIndex(x => x > inc.window_end);
      if (a < 0) return;
      a = Math.max(0, a - 1);
      if (b < 0) b = n - 1;
      let dd = '';
      for (let i = a; i <= Math.min(b, n - 1); i++) {
        if (vals[i] == null) continue;
        dd += (dd ? ' L' : 'M') + X(i) + ',' + Y(vals[i]);
      }
      if (dd) svg.appendChild(el('path', { d: dd, fill: 'none', stroke: c,
        'stroke-width': 2.2, 'stroke-linejoin': 'round' }));
    });
  });

  const step = Math.max(1, Math.round(n / 8));
  for (let i = 0; i < n; i += step)
    svg.appendChild(txt(short(dates[i]), { x: X(i), y: H - 10,
      'text-anchor': 'middle', class: 'axis-t' }));

  host.style.minWidth = '620px';
  host.appendChild(svg);
}

/* ===== LINE CHART — blended metric with median reference ===== */
function lineChart(points, o) {
  const n = points.length;
  if (n < 2) return null;
  const ok = points.map(p => p.v).filter(v => v != null);
  if (!ok.length) return null;
  const lo = Math.min(...ok), hi = Math.max(...ok);
  const pad = (hi - lo) * 0.18 || Math.abs(hi) * 0.02 || 1;

  const W = 800, H = 236, L = 74, R = 22, T = 20, B = 52;
  const X = i => L + (i / (n - 1)) * (W - L - R);
  const Y = v => T + (1 - (v - (lo - pad)) / ((hi - lo) + 2 * pad)) * (H - T - B);

  const svg = el('svg', { viewBox: `0 0 ${W} ${H}` });

  let a = points.findIndex(p => p.d >= o.w0);
  let b = points.findIndex(p => p.d > o.w1);
  if (a < 0) a = 0;
  if (b < 0) b = n; b = Math.min(b, n);

  /* incident band */
  svg.appendChild(el('rect', { x: X(a), y: T, width: Math.max(X(Math.min(b, n - 1)) - X(a), 6),
    height: H - T - B, fill: 'var(--anomaly-f)', rx: 3 }));

  /* horizontal grid + Y labels */
  [0, 0.25, 0.5, 0.75, 1].forEach(t => {
    const v = (lo - pad) + t * ((hi - lo) + 2 * pad);
    const y = Y(v);
    svg.appendChild(el('line', { x1: L, x2: W - R, y1: y, y2: y,
      stroke: 'var(--line-2)', 'stroke-width': 1 }));
    svg.appendChild(txt(fmtMetric(v, o.metric), { x: L - 8, y: y + 3.5,
      'text-anchor': 'end', class: 'axis-t' }));
  });

  /* median reference */
  if (o.ref != null) {
    const y = Y(o.ref);
    svg.appendChild(el('line', { x1: L, x2: W - R, y1: y, y2: y,
      stroke: 'var(--normal)', 'stroke-width': 1.2, 'stroke-dasharray': '5 4', opacity: 0.8 }));
  }

  /* full series */
  let d = '';
  points.forEach((p, i) => { if (p.v != null) d += (d ? ' L' : 'M') + X(i) + ',' + Y(p.v); });
  svg.appendChild(el('path', { d, fill: 'none', stroke: 'var(--normal)',
    'stroke-width': 2, 'stroke-linejoin': 'round' }));

  /* incident overlay + dots */
  let di = '';
  for (let i = Math.max(0, a - 1); i <= Math.min(b, n - 1); i++) {
    if (points[i].v == null) continue;
    di += (di ? ' L' : 'M') + X(i) + ',' + Y(points[i].v);
  }
  if (di) svg.appendChild(el('path', { d: di, fill: 'none', stroke: 'var(--anomaly)',
    'stroke-width': 2.6, 'stroke-linejoin': 'round' }));
  points.forEach((p, i) => {
    if (p.v != null && p.d >= o.w0 && p.d <= o.w1)
      svg.appendChild(el('circle', { cx: X(i), cy: Y(p.v), r: 3.4,
        fill: 'var(--anomaly)', stroke: 'var(--surface)', 'stroke-width': 1.6 }));
  });

  /* X labels */
  const step = Math.max(1, Math.round(n / 7));
  for (let i = 0; i < n; i += step)
    svg.appendChild(txt(short(points[i].d), { x: X(i), y: H - B + 20,
      'text-anchor': 'middle', class: 'axis-t' }));

  /* legend */
  const ly = H - 8;
  svg.appendChild(el('line', { x1: L, x2: L + 18, y1: ly - 3.5, y2: ly - 3.5,
    stroke: 'var(--normal)', 'stroke-width': 2 }));
  svg.appendChild(txt('observed', { x: L + 24, y: ly, class: 'axis-t' }));
  svg.appendChild(el('line', { x1: L + 92, x2: L + 110, y1: ly - 3.5, y2: ly - 3.5,
    stroke: 'var(--anomaly)', 'stroke-width': 2.6 }));
  svg.appendChild(txt('incident days', { x: L + 116, y: ly, class: 'axis-t' }));

  return svg;
}

/* ===== BREAKDOWN — one line per segment value ===== */
function breakdownChart(list, o) {
  if (!list.length) return null;
  const dates = [...new Set(list.flatMap(s => s.points.map(p => p.d)))].sort();
  const n = dates.length;
  if (n < 2) return null;

  const idx = {};
  list.forEach(s => { idx[s.val] = {}; s.points.forEach(p => { idx[s.val][p.d] = p.v; }); });

  const ok = list.flatMap(s => s.points.map(p => p.v)).filter(v => v != null);
  const lo = Math.min(...ok), hi = Math.max(...ok);
  const pad = (hi - lo) * 0.12 || 0.01;

  const W = 800, H = 252, L = 74, R = 104, T = 18, B = 52;
  const X = i => L + (i / (n - 1)) * (W - L - R);
  const Y = v => T + (1 - (v - (lo - pad)) / ((hi - lo) + 2 * pad)) * (H - T - B);

  const svg = el('svg', { viewBox: `0 0 ${W} ${H}` });

  let a = dates.findIndex(d => d >= o.w0);
  let b = dates.findIndex(d => d > o.w1);
  if (a < 0) a = 0;
  if (b < 0) b = n; b = Math.min(b, n);
  svg.appendChild(el('rect', { x: X(a), y: T, width: Math.max(X(Math.min(b, n - 1)) - X(a), 6),
    height: H - T - B, fill: 'var(--anomaly-f)', rx: 3 }));

  [0, 0.33, 0.66, 1].forEach(t => {
    const v = (lo - pad) + t * ((hi - lo) + 2 * pad), y = Y(v);
    svg.appendChild(el('line', { x1: L, x2: W - R, y1: y, y2: y,
      stroke: 'var(--line-2)', 'stroke-width': 1 }));
    svg.appendChild(txt(fmtMetric(v, o.metric), { x: L - 8, y: y + 3.5,
      'text-anchor': 'end', class: 'axis-t' }));
  });

  /* others first, culprit last so it sits on top */
  const ordered = [...list].sort((p, q) =>
    (p.val === o.culprit ? 1 : 0) - (q.val === o.culprit ? 1 : 0));

  ordered.forEach(s => {
    const isC = s.val === o.culprit;
    let d = '', run = false;
    dates.forEach((dt, i) => {
      const v = idx[s.val][dt];
      if (v == null) { run = false; return; }
      d += (run ? ' L' : (d ? ' M' : 'M')) + X(i) + ',' + Y(v);
      run = true;
    });
    svg.appendChild(el('path', { d, fill: 'none',
      stroke: isC ? 'var(--anomaly)' : 'var(--muted-s)',
      'stroke-width': isC ? 2.6 : 1.15,
      opacity: isC ? 1 : 0.55, 'stroke-linejoin': 'round' }));

    if (isC) {
      let last = -1;
      for (let j = n - 1; j >= 0; j--) if (idx[s.val][dates[j]] != null) { last = j; break; }
      if (last >= 0)
        svg.appendChild(txt(s.val, { x: X(last) + 7, y: Y(idx[s.val][dates[last]]) + 3.5,
          class: 'axis-t', fill: 'var(--anomaly)', 'font-weight': '600' }));
    }
  });

  const step = Math.max(1, Math.round(n / 7));
  for (let i = 0; i < n; i += step)
    svg.appendChild(txt(short(dates[i]), { x: X(i), y: H - B + 20,
      'text-anchor': 'middle', class: 'axis-t' }));

  const ly = H - 8;
  svg.appendChild(el('line', { x1: L, x2: L + 18, y1: ly - 3.5, y2: ly - 3.5,
    stroke: 'var(--anomaly)', 'stroke-width': 2.6 }));
  svg.appendChild(txt(`${o.dim} = ${o.culprit}`, { x: L + 24, y: ly, class: 'axis-t' }));
  const off = L + 34 + (`${o.dim} = ${o.culprit}`).length * 5.6;
  svg.appendChild(el('line', { x1: off, x2: off + 18, y1: ly - 3.5, y2: ly - 3.5,
    stroke: 'var(--muted-s)', 'stroke-width': 1.4 }));
  svg.appendChild(txt(`all other ${o.dim} values`, { x: off + 24, y: ly, class: 'axis-t' }));

  return svg;
}

/* ===== SHARE-WEIGHTED CONTRIBUTION ===== */
function attrChart(row) {
  const bars = [];
  if (row.culprit_val && num(row.explains_pct) != null)
    bars.push({ label: `${row.culprit_dim} = ${row.culprit_val}`, v: num(row.explains_pct), lead: true });
  (row.ruled_out_segments || []).forEach(s => {
    const v = num(s.explains_pct);
    if (v != null) bars.push({ label: s.key || `${s.dim} = ${s.val}`, v, lead: false });
  });
  if (!bars.length) return null;

  const maxV = Math.max(...bars.map(b => b.v), 100);
  const W = 800, L = 214, R = 66, T = 10, rowH = 30, barH = 13;
  const H = T + bars.length * rowH + 26;
  const barW = W - L - R;
  const x100 = L + (100 / maxV) * barW;

  const svg = el('svg', { viewBox: `0 0 ${W} ${H}` });

  svg.appendChild(el('line', { x1: x100, x2: x100, y1: T, y2: H - 26,
    stroke: 'var(--ink-3)', 'stroke-width': 1, 'stroke-dasharray': '4 3', opacity: 0.55 }));

  bars.forEach((b, i) => {
    const mid = T + i * rowH + rowH / 2;
    svg.appendChild(txt(b.label, { x: L - 10, y: mid + 3.5, 'text-anchor': 'end',
      class: 'axis-t', fill: b.lead ? 'var(--ink)' : 'var(--ink-3)',
      'font-weight': b.lead ? '600' : '400' }));
    const w = Math.max((b.v / maxV) * barW, 2);
    svg.appendChild(el('rect', { x: L, y: mid - barH / 2, width: w, height: barH, rx: 2,
      fill: b.lead ? 'var(--anomaly)' : 'var(--muted-s)', opacity: b.lead ? 0.92 : 0.45 }));
    svg.appendChild(txt(b.v.toFixed(1) + '%', { x: L + w + 8, y: mid + 3.5, class: 'axis-t',
      fill: b.lead ? 'var(--anomaly)' : 'var(--ink-3)', 'font-weight': b.lead ? '700' : '400' }));
  });

  svg.appendChild(el('line', { x1: L, x2: L + 16, y1: H - 12, y2: H - 12,
    stroke: 'var(--ink-3)', 'stroke-width': 1, 'stroke-dasharray': '4 3' }));
  svg.appendChild(txt('100% of the observed move', { x: L + 22, y: H - 8.5, class: 'axis-t' }));

  return svg;
}

/* ===== EXCLUSION TEST TABLE — the proof ===== */
function exclusionTable(row) {
  const rows = row.exclusion || [];
  if (!rows.length) return null;
  const wrap = document.createElement('div');
  wrap.className = 'excl-wrap';
  wrap.innerHTML = `
    <table class="excl">
      <thead><tr>
        <th>Removed</th>
        <th class="n">Global without it</th>
        <th class="n">Baseline</th>
        <th>Anomaly gone?</th>
      </tr></thead>
      <tbody>${rows.map(r => `
        <tr class="${r.clears_anomaly ? 'lead' : ''}">
          <td>${esc(r.dim)} = ${esc(r.val)}</td>
          <td class="n"${r.clears_anomaly ? ' style="color:var(--normal);font-weight:700"' : ''}>${esc(fmtMetric(r.excl_incident, row.metric))}</td>
          <td class="n">${esc(fmtMetric(r.excl_baseline, row.metric))}</td>
          <td><span class="${r.clears_anomaly ? 'yes' : 'no'}">${r.clears_anomaly ? '✓ cleared' : 'persists'}</span></td>
        </tr>`).join('')}
      </tbody>
    </table>`;
  return wrap;
}

/* ===== TRACE — what ran, in order (with real per-step timings) ===== */
function buildTrace(row) {
  const T = {};
  (row.timings || []).forEach(s => { T[s.label] = s.ms; });
  const m = row.metric;

  /* If the orchestrator recorded its own stage log, that is the real trace. */
  if (row.lifecycle && row.lifecycle.length) {
    const db = row.schema || 'rca_orch';
    const kv = (label, v, d = 4) => num(v) == null ? null : `${label} ${fx(v, d)}`;

    return row.lifecycle.map(s => {
      const d = s.details || {};
      let out;

      if (s.stage === 'error') {
        out = d.error || 'unavailable';
      } else if (s.stage === 'anomaly_detected') {
        out = [kv('value', d.value), kv('baseline', d.baseline),
               num(d.effect) != null ? `eff ${fmtPct(num(d.effect) * 100)}` : null,
               kv('z', d.z, 1),
               num(d.n) != null ? `n ${num(d.n).toLocaleString()}` : null]
               .filter(Boolean).join(' · ');
      } else if (s.stage === 'incident_created_or_updated') {
        out = [d.window_start && `window ${d.window_start} to ${d.window_end}`,
               d.baseline_start && `baseline from ${d.baseline_start}`,
               d.days != null && `${d.days} days`,
               kv('peak z', d.peak_z, 1)].filter(Boolean).join(' · ');
      } else if (s.stage === 'diagnosis') {
        const ex = num(row.explains_pct), cs = num(row.culprit_share_pct);
        out = `${s.records} candidate segments ranked by share-weighted contribution.`
            + (row.culprit_val
                ? ` Top: ${row.culprit_dim}=${row.culprit_val}`
                  + (ex != null ? ` explains ${fx(ex, 1)}%` : '')
                  + (cs != null ? ` at ${fx(cs, 1)}% of traffic` : '') + '.'
                : '');
      } else if (s.stage === 'narration') {
        out = [d.metric_change_pct != null && `${d.metric_change_pct}%`,
               d.verdict && `verdict ${d.verdict}`,
               d.culprit_val && `culprit ${d.culprit_val}`].filter(Boolean).join(' · ');
      } else {
        out = Object.entries(d).slice(0, 5)
          .map(([k, v]) => `${k} ${num(v) != null ? fx(v, 4) : v}`).join(' · ')
          || `${s.records} records`;
      }

      return {
        what: s.label,
        out,
        sql:  `${db}.incident_lifecycle_trace · stage='${s.stage}' · ${s.records} record${s.records !== 1 ? 's' : ''}`,
        ms:   null,
        at:   s.observed_at,
      };
    });
  }

  const steps = [];

  /* 1 — detection */
  const det = row.detection;
  if (det && (num(det.z) != null || num(det.effect) != null)) {
    steps.push({
      what: `Detect on the blended ${mp(m)}`,
      out:  [num(det.effect) != null ? `eff ${fmtPct(num(det.effect) * 100)}` : null,
             num(det.z) != null ? `z ${fx(det.z, 1)}` : null,
             num(det.n) != null ? `n ${num(det.n).toLocaleString()}` : null]
             .filter(Boolean).join(' · '),
      sql:  `v_detect WHERE metric='${m}' AND dim='__all__' AND d='${row.window_start}'`,
      ms:   T['detector'],
    });
  } else {
    steps.push({
      what: `Detect on the blended ${mp(m)}`,
      out:  `eff ${fmtPct(row.metric_change_pct)}`
            + (num(row.peak_z) != null ? ` · z ${fx(row.peak_z, 1)}` : ''),
      sql:  `v_detect WHERE d='${row.window_start}'`,
      ms:   T['detector'],
    });
  }

  /* 2 — revenue identity decomposition */
  const fc = row.factor;
  if (fc) {
    const p = v => num(v) == null ? null : (num(v) > 0 ? '+' : '') + fx(v, 2);
    const parts = [['requests', fc.l_requests], ['fill', fc.l_fill_rate],
                   ['render', fc.l_render_rate], ['ecpm', fc.l_ecpm]]
      .map(([k, v]) => (p(v) == null ? null : `${k} ${p(v)}`)).filter(Boolean);
    if (parts.length) steps.push({
      what: 'Decompose the revenue identity',
      out:  parts.join(' · '),
      sql:  `v_factor WHERE d='${row.window_start}'`,
      ms:   T['decomposition'],
    });
  }

  /* 3 — attribution */
  if (row.culprit_val) {
    const cs = num(row.culprit_share_pct), ex = num(row.explains_pct);
    const cb = num(row.culprit_baseline),  cv = num(row.culprit_value);
    steps.push({
      what: `Attribute within the ${mp(m)} factor`,
      out:  [`${row.culprit_dim}='${row.culprit_val}'`,
             cs != null ? `share ${fx(cs / 100, 3)}` : null,
             (cb != null && cv != null) ? `delta ${fx(cv - cb, 4)}` : null,
             ex != null ? `explains ${fx(ex / 100, 3)}` : null]
             .filter(Boolean).join(' '),
      sql:  `v_attribute(metric='${m}', b0='${row.baseline_start}', i0='${row.window_start}', i1='${row.window_end}')`,
      ms:   T['attribution'],
    });
  }

  /* 4 — uniformity */
  const ud = (row.ruled_out_dimensions || []).filter(u => u && num(u.spread) != null);
  if (ud.length && row.culprit_val) {
    const shown = ud.slice(0, 5).map(u => `${u.dim} ${fx(u.spread, 3)}`).join(' · ');
    const worst = Math.max(...ud.map(u => num(u.spread)));
    steps.push({
      what: 'Test uniformity across other dimensions',
      out:  `${shown} → max spread ${fx(worst, 3)}`,
      sql:  `v_uniformity(dim='${row.culprit_dim}', val='${row.culprit_val}')`,
      ms:   T['attribution'],
    });
  }

  /* 5 — exclusion */
  if (row.global_without_culprit != null) {
    steps.push({
      what: 'Exclusion test',
      out:  `remove ${row.culprit_val} → ${fmtMetric(row.global_without_culprit, m)} vs `
          + `${fmtMetric(row.global_without_culprit_baseline, m)} baseline; `
          + `${row.clears_anomaly ? 'anomaly gone' : 'anomaly persists'}`,
      sql:  `v_ruleout(metric='${m}', tol=0.005)`,
      ms:   T['exclusion test'],
    });
  }

  /* 6 — verdict */
  steps.push({
    what: 'Conclude',
    out:  row.culprit_val
            ? `${row.culprit_dim}=${row.culprit_val} · ${VERDICT_LABEL[row.verdict] || row.verdict}`
            : `no segment named · ${VERDICT_LABEL[row.verdict] || row.verdict}`,
    sql:  '—',
    ms:   null,
  });

  return steps;
}

/* ===== TITLE ===== */
function titleOf(row) {
  const v = row.culprit_val, m = row.metric, down = (row.metric_change_pct || 0) < 0;
  if (!v) return `Platform-wide ${mp(m)} ${down ? 'drop' : 'spike'}`;
  if (m === 'fill_rate'   && down) return `${v} stopped filling`;
  if (m === 'render_rate' && down) return `${v} stopped rendering`;
  if (m === 'ctr'         && down) return `${v} clicks collapsed`;
  if (m === 'ecpm'        && down) return `${v} pricing collapsed`;
  if (m === 'rpr'         && down) return `${v} revenue per request fell`;
  if (m === 'revenue'     && down) return `${v} revenue shortfall`;
  if (m === 'requests'    && down) return `${v} traffic loss`;
  return `${v} ${mp(m)} ${down ? 'drop' : 'spike'}`;
}

/* ===== NARRATION — plain English, numbers bolded ===== */
function narrationHTML(row) {
  const m = row.metric, chg = row.metric_change_pct || 0;
  const b = s => `<b>${esc(s)}</b>`;
  const out = [];

  /* para 1 — what moved */
  const det  = row.detection || null;
  const nStr = num(det?.n) != null ? ` across ${b(num(det.n).toLocaleString())} requests` : '';
  const zStr = num(det?.z) != null ? `, z = ${b(fx(det.z, 1))}` : '';
  if (det && (num(det.baseline) != null || num(det.value) != null)) {
    out.push(`Blended ${mp(m)} ${chg < 0 ? 'fell' : 'rose'} ${b(fmtPct(chg))} `
           + `(${b(fmtMetric(det.baseline, m))} → ${b(fmtMetric(det.value, m))}${zStr})${nStr}.`);
  } else {
    out.push(`Blended ${mp(m)} ${chg < 0 ? 'fell' : 'rose'} ${b(fmtPct(chg))} `
           + `between ${b(dateRange(row.window_start, row.window_end))}.`);
  }

  if (!row.culprit_val) {
    out.push(`No single segment accounts for the move. Every slice fell in the same proportion, `
           + `so this is a platform-wide event rather than a localised one.`);
    return out;
  }

  /* para 2 — the cause and the proof */
  const cb = num(row.culprit_baseline), cv = num(row.culprit_value);
  const cc = num(row.culprit_change_pct), cs = num(row.culprit_share_pct);
  const ex = num(row.explains_pct);

  let ptDrop = '';
  if (isRate(m) && cb != null && cv != null)
    ptDrop = `, a ${b(fx(Math.abs(cb - cv) * 100, 1) + ' percentage point')} collapse`;
  else if (cc != null)
    ptDrop = `, a ${b(fx(Math.abs(cc), 1) + '%')} collapse`;

  let p2 = `${b(row.culprit_dim + ' = ' + row.culprit_val)} accounts for `
         + `${b(ex != null ? fx(ex, 1) + '%' : 'the bulk')} of it.`;
  if (cb != null || cv != null)
    p2 += ` Its ${mp(m)} went ${b(fmtMetric(cb, m))} → ${b(fmtMetric(cv, m))}${ptDrop}`
        + (cs != null ? `, over ${b(fx(cs, 1) + '%')} of traffic.` : '.');
  else if (cs != null)
    p2 += ` It carries ${b(fx(cs, 1) + '%')} of traffic.`;

  if (row.clears_anomaly && row.global_without_culprit != null) {
    p2 += ` Remove that slice and the global ${mp(m)} is ${b(fmtMetric(row.global_without_culprit, m))} `
        + `against a ${b(fmtMetric(row.global_without_culprit_baseline, m))} baseline: the anomaly `
        + `disappears entirely. Remove any other slice and it persists.`;
  }
  out.push(p2);

  /* para 3 — uniformity. worst/best come from the uniformity table and may be
     absent if only v_narration's (dimension, spread) pairs were available. */
  const ud = (row.ruled_out_dimensions || []).filter(u => u && u.dim);
  if (ud.length) {
    const withSpread = ud.filter(u => num(u.spread) != null);
    const best = withSpread.length
      ? withSpread.reduce((a, c) => (c.spread < a.spread ? c : a))
      : ud[0];
    const cnt   = new Set(ud.map(u => u.dim)).size;
    const range = (num(best.worst) != null && num(best.best) != null)
      ? `${b(best.worst.toFixed(3))} to ${b(best.best.toFixed(3))}, `
      : '';
    const spread = num(best.spread) != null ? `spread ${b(best.spread.toFixed(3))}` : '';
    const paren  = (range || spread) ? ` (${range}${spread})` : '';
    out.push(`The drop is ${b('uniform across every ' + dl(best.dim))}${paren}, `
           + `and across ${b(nw(cnt) + ' dimensions')} tested in total. `
           + `So this is the ${dl(row.culprit_dim)} and nothing narrower.`);
  }

  /* para 4 — money */
  const rv = row.revenue;
  if (rv && num(rv.shortfall) > 0.5 && num(rv.actual) != null && num(rv.expected) != null) {
    out.push(`Revenue over the window came in at ${b(rv.actual.toFixed(2))} against an `
           + `expected ${b(rv.expected.toFixed(2))}, roughly `
           + `${b(rv.shortfall.toFixed(0))} short. That figure is a counterfactual, not a booked loss.`);
  }

  return out;
}

/* ===== PANEL WRAPPER ===== */
function panel(title, note, node) {
  const d = document.createElement('div');
  d.className = 'panel chart-box';
  d.innerHTML = `<h3>${esc(title)}</h3>` + (note ? `<p class="chart-note">${note}</p>` : '');
  const sc = document.createElement('div'); sc.className = 'scroll-x';
  const inner = document.createElement('div'); inner.style.minWidth = '540px';
  inner.appendChild(node); sc.appendChild(inner); d.appendChild(sc);
  return d;
}

/* ===== DETAIL ===== */
const CACHE = {};

async function renderDetail(summary) {
  const host = document.getElementById('detail');
  host.innerHTML = '<div class="panel empty-state">Running the investigation…</div>';

  const id = summary.incident_id;
  let row, ts;
  try {
    const [a, b] = await Promise.all([
      CACHE[id]      ? Promise.resolve(CACHE[id])      : fetch(`/api/incident/${encodeURIComponent(id)}`).then(r => r.json()),
      CACHE[id + '#ts'] ? Promise.resolve(CACHE[id + '#ts']) : fetch(`/api/incident/${encodeURIComponent(id)}/timeseries`).then(r => r.json()).catch(() => null),
    ]);
    if (a.error) throw new Error(a.error);
    row = a; ts = (b && !b.error) ? b : null;
    CACHE[id] = row; if (ts) CACHE[id + '#ts'] = ts;
  } catch (e) {
    host.innerHTML = `<div class="err-box">${esc(e.message)}</div>`;
    return;
  }

  host.textContent = '';
  const color = VERDICT_COLOR[row.verdict] || 'var(--ink-3)';
  const m = row.metric;

  /* ── verdict panel ── */
  const vp = document.createElement('div');
  vp.className = 'panel verdict';
  vp.innerHTML = `<h2>${esc(titleOf(row))}</h2>
    <div class="verdict-meta">
      <span class="chip" style="color:${color}">${esc(VERDICT_LABEL[row.verdict] || row.verdict)}</span>
      <span class="mono-big" style="color:${color}">${esc(fmtPct(row.metric_change_pct))}</span>
      <span class="meta-sub">in ${esc(mp(m))} · ${esc(dateRange(row.window_start, row.window_end))} · ${row.days} days</span>
    </div>`;

  const nd = document.createElement('div');
  nd.className = 'narration';
  const llm = stripDashes(row.narration || '').trim();
  nd.innerHTML = llm
    ? llm.split(/\n+/).filter(Boolean).map(p => `<p>${esc(p)}</p>`).join('')
    : narrationHTML(row).map(p => `<p>${p}</p>`).join('');
  vp.appendChild(nd);

  if (row.culprit_val) {
    const bad = (row.metric_change_pct || 0) < 0 ? 'red' : 'green';
    const ss = document.createElement('div'); ss.className = 'stat-strip';
    ss.innerHTML = `
      <div class="stat"><div class="sk">Normal</div><div class="sv">${esc(fmtPretty(row.culprit_baseline, m))}</div></div>
      <div class="stat"><div class="sk">During</div><div class="sv ${bad}">${esc(fmtPretty(row.culprit_value, m))}</div></div>
      <div class="stat"><div class="sk">Segment move</div><div class="sv ${bad}">${esc(fmtPct(row.culprit_change_pct, 1))}</div></div>
      <div class="stat"><div class="sk">Traffic share</div><div class="sv">${fx(row.culprit_share_pct, 1)}%</div></div>
      <div class="stat"><div class="sk">Explains</div><div class="sv ${bad}">${fx(row.explains_pct, 1)}%</div></div>
      <div class="stat"><div class="sk">Clears</div><div class="sv ${row.clears_anomaly ? 'green' : 'red'}">${row.clears_anomaly ? 'Yes' : 'No'}</div></div>
      <div class="stat"><div class="sk">Revenue at risk</div><div class="sv ${bad}">${num(row.revenue?.shortfall) != null ? '~' + fx(row.revenue.shortfall, 0) : '--'}</div></div>`;
    vp.appendChild(ss);
  }
  if (row.fetch_ms != null) {
    const badge = document.createElement('div');
    badge.className = 'timing-badge';
    badge.innerHTML = `<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" width="11" height="11">
      <circle cx="8" cy="8" r="6.5"/>
      <polyline points="8,4.5 8,8 10.5,9.5"/>
    </svg>${esc(fmtMs(row.fetch_ms))}`;
    vp.appendChild(badge);
  }
  host.appendChild(vp);

  /* ── blended line chart ── */
  if (ts?.blended?.length > 1) {
    const pts = ts.blended;
    const off = pts.filter(p => p.v != null && (p.d < row.window_start || p.d > row.window_end))
                   .map(p => p.v).sort((x, y) => x - y);
    const med = off.length ? off[Math.floor(off.length / 2)] : null;
    const lc = lineChart(pts, { w0: row.window_start, w1: row.window_end, metric: m, ref: med });
    if (lc) host.appendChild(panel(
      `${ml(m).toUpperCase()}, BLENDED`,
      `The dashed line is the median of all non-incident days (${esc(fmtMetric(med, m))}). `
      + `The shaded band is the incident window.`,
      lc));
  }

  /* ── split by culprit dimension ── */
  if (ts?.breakdown?.length && row.culprit_dim) {
    const cs  = ts.breakdown.find(s => s.val === row.culprit_val);
    const avg = s => s.points.reduce((a, p) => a + (p.v || 0), 0) / (s.points.length || 1);
    const others = ts.breakdown.filter(s => s.val !== row.culprit_val)
      .sort((a, b2) => avg(b2) - avg(a)).slice(0, 9);
    const show = cs ? [cs, ...others] : others;

    if (show.length) {
      const bc = breakdownChart(show, {
        culprit: row.culprit_val, dim: row.culprit_dim,
        w0: row.window_start, w1: row.window_end, metric: m,
      });
      if (bc) {
        /* dynamic, honest note computed from the series itself */
        let note = `One line per ${dl(row.culprit_dim)}. `;
        if (cs) {
          const inW  = cs.points.filter(p => p.d >= row.window_start && p.d <= row.window_end && p.v != null);
          const outW = others.flatMap(s => s.points
            .filter(p => p.d >= row.window_start && p.d <= row.window_end && p.v != null).map(p => p.v));
          if (inW.length && outW.length) {
            const trough = Math.min(...inW.map(p => p.v));
            const flat   = outW.sort((a, b2) => a - b2)[Math.floor(outW.length / 2)];
            const after  = cs.points.find(p => p.d > row.window_end && p.v != null);
            const rec    = after ? ` It recovers on its own ${nw(daysBetween(row.window_start, after.d))} days later.` : '';
            note = `${cap(nw(others.length))} other ${dp(row.culprit_dim)} hold a flat `
                 + `${fmtMetric(flat, m)}. ${esc(row.culprit_val)} falls to ${fmtMetric(trough, m)}.${rec}`;
          }
        }
        host.appendChild(panel(`SPLIT BY ${String(row.culprit_dim).toUpperCase()}`, note, bc));
      }
    }
  }

  /* ── share-weighted contribution ── */
  const ac = attrChart(row);
  if (ac) host.appendChild(panel(
    'SHARE-WEIGHTED CONTRIBUTION',
    `${esc(row.culprit_val)} is ${fx(row.culprit_share_pct, 1)}% of traffic and explains `
    + `${fx(row.explains_pct, 1)}%. The containers below it move only because `
    + `${esc(row.culprit_val)} traffic sits inside them.`,
    ac));

  /* ── exclusion test ── */
  const et = exclusionTable(row);
  if (et) {
    const p = document.createElement('div'); p.className = 'panel chart-box';
    p.innerHTML = `<h3>EXCLUSION TEST — THE PROOF</h3>
      <p class="chart-note">Remove one slice, recompute the global metric. Exactly one row restores
      normal; that asymmetry is what turns correlation into cause.</p>`;
    p.appendChild(et);
    host.appendChild(p);
  }

  /* ── trace ── */
  const steps = buildTrace(row);
  if (steps.length) {
    const p = document.createElement('div'); p.className = 'panel chart-box';
    p.innerHTML = `<h3>TRACE — WHAT RAN, IN ORDER</h3>
      <p class="chart-note">Every step below ran against ClickHouse just now. The timing on each row
      is how long that query actually took.</p>`;
    const box = document.createElement('div'); box.className = 'trace';
    steps.forEach((s, i) => {
      const d = document.createElement('div'); d.className = 'step';
      const badge = s.ms != null
        ? `<span class="step-ms">${esc(fmtMs(s.ms))}</span>`
        : (s.at ? `<span class="step-ms">${esc(String(s.at).replace('T', ' ').slice(0, 19))}</span>` : '');
      d.innerHTML = `<div class="step-n">${i + 1}</div>
        <div class="step-body">
          <div class="step-what">${esc(s.what)}${badge}</div>
          <div class="step-out">${esc(s.out)}</div>
          <div class="step-sql">${esc(s.sql)}</div>
        </div>`;
      box.appendChild(d);
    });
    p.appendChild(box);
    host.appendChild(p);
  }

  /* ── checked and ruled out ── */
  const ro = row.ruled_out_segments || [];
  if (ro.length) {
    const p = document.createElement('div'); p.className = 'panel chart-box';
    p.innerHTML = `<h3>CHECKED AND RULED OUT</h3>
      <p class="chart-note">Each of these looked like a candidate because it carries
      ${esc(row.culprit_val)} traffic inside it. Removing any of them leaves the anomaly in place.</p>
      <div class="ruled">${ro.map(s => `
        <div class="ruled-row">
          <span class="rn">${esc(s.key || (s.dim + ' = ' + s.val))}</span>
          <span class="rb"><i style="width:${Math.min(100, Math.max(0, num(s.explains_pct) ?? 0))}%"></i></span>
          <span class="rp">${fx(s.explains_pct, 1)}%</span>
          <span class="rv">cleared</span>
        </div>`).join('')}</div>`;
    host.appendChild(p);
  }

  /* ── validation queries ── */
  const qs = row.queries || [];
  if (qs.length) {
    const p = document.createElement('div'); p.className = 'panel chart-box';
    p.innerHTML = `<h3>VALIDATION QUERIES</h3>
      <p class="chart-note">Every number above was computed by ClickHouse. Expand any query below
      and paste it into the SQL console to reproduce the result from scratch.</p>`;
    const acc = document.createElement('div'); acc.className = 'sql-accordion';
    qs.forEach(q => {
      const item = document.createElement('details'); item.className = 'sql-item';
      item.innerHTML = `
        <summary class="sql-summary">${esc(q.label)}</summary>
        <div class="sql-body">
          <button class="sql-copy" type="button">Copy</button>
          <pre class="sql-pre"><code>${esc(q.sql)}</code></pre>
        </div>`;
      item.querySelector('.sql-copy').addEventListener('click', e => {
        e.stopPropagation();
        navigator.clipboard.writeText(q.sql).then(() => {
          const btn = item.querySelector('.sql-copy');
          btn.textContent = 'Copied!';
          setTimeout(() => { btn.textContent = 'Copy'; }, 1500);
        }).catch(() => {});
      });
      acc.appendChild(item);
    });
    p.appendChild(acc);
    host.appendChild(p);
  }
}

/* ===== LIST ===== */
function renderList(incidents) {
  const host = document.getElementById('list');
  host.textContent = '';
  if (!incidents.length) {
    host.innerHTML = '<div class="empty-state">No incidents found.</div>';
    return;
  }
  incidents.forEach((inc, i) => {
    const sev = VERDICT_COLOR[inc.verdict] || 'var(--ink-3)';
    const b = document.createElement('button');
    b.className = 'inc';
    b.style.setProperty('--sev', sev);
    b.setAttribute('role', 'tab');
    b.setAttribute('aria-current', i === 0 ? 'true' : 'false');
    b.innerHTML = `
      <div class="inc-top">
        <span class="inc-id"><b>${inc._letter}</b> · ${esc(ml(inc.metric))}</span>
        <span class="inc-eff">${esc(fmtPct(inc.metric_change_pct))}</span>
      </div>
      <div class="inc-when">${esc(dateRange(inc.window_start, inc.window_end))}</div>
      <div class="inc-cause">${inc.culprit_val
        ? `${esc(inc.culprit_dim)} = <b>${esc(inc.culprit_val)}</b>`
        : '<span class="dim">no segment · platform-wide</span>'}</div>`;
    b.addEventListener('click', () => {
      host.querySelectorAll('.inc').forEach(x => x.setAttribute('aria-current', 'false'));
      b.setAttribute('aria-current', 'true');
      renderDetail(inc);
      if (window.lcSetContext) window.lcSetContext(inc);
    });
    host.appendChild(b);
  });
}

/* ===== TILES ===== */
function renderTiles(pulse, incidents) {
  const localized = incidents.filter(i => i.culprit_val).length;
  const platform  = incidents.length - localized;
  const ev = pulse.total_events || 0;
  const evStr = ev >= 1e6 ? (ev / 1e6).toFixed(1) + 'M' : Math.round(ev).toLocaleString();

  document.getElementById('tiles').innerHTML = [
    { k: 'Window',    v: (pulse.coverage_days || 0) + 'd',
      s: `${short(pulse.coverage_start)} – ${short(pulse.coverage_end)} 2026` },
    { k: 'Events',    v: evStr, s: 'ad requests analysed' },
    { k: 'Incidents', v: incidents.length,
      s: `${localized} localised, ${platform} platform-wide` },
    { k: 'Missed by global', v: pulse.missed_by_global ?? '—',
      s: 'segment-only anomalies', cls: (pulse.missed_by_global > 0) ? 'amber' : '' },
    { k: 'Revenue at risk', v: '~' + Math.round(pulse.revenue_at_risk || 0),
      s: 'vs baseline, incident days', cls: 'red' },
  ].map(t => `<div class="tile">
      <div class="k">${t.k}</div>
      <div class="v${t.cls ? ' ' + t.cls : ''}">${t.v}</div>
      <div class="s">${t.s}</div>
    </div>`).join('');
}

/* ===== BOOT ===== */
async function load() {
  try {
    const [pulse, incRes, tsRes] = await Promise.all([
      fetch('/api/pulse').then(r => r.json()),
      fetch('/api/incidents').then(r => r.json()),
      fetch('/api/timeseries').then(r => r.json()).catch(() => ({ rows: [] })),
    ]);
    if (pulse.error)  throw new Error(pulse.error);
    if (incRes.error) throw new Error(incRes.error);

    const incidents = incRes.incidents;
    incidents.forEach((inc, i) => { inc._letter = String.fromCharCode(65 + i); });

    const n = incidents.length;
    const weeks = (pulse.coverage_start && pulse.coverage_end)
      ? Math.max(1, Math.round(daysBetween(pulse.coverage_start, pulse.coverage_end) / 7)) : 0;

    document.getElementById('h1').textContent = n === 0
      ? 'No incidents detected'
      : `${cap(nw(n))} thing${n !== 1 ? 's' : ''} went wrong in ${nw(weeks)} week${weeks !== 1 ? 's' : ''}`;

    const ev = pulse.total_events || 0;
    document.getElementById('dek').textContent = ev > 0
      ? `${Math.round(ev).toLocaleString()} ad events, `
        + `${short(pulse.coverage_start)} – ${short(pulse.coverage_end)} 2026. `
        + `Every number below was computed in ClickHouse and is reproducible from the queries `
        + `in the trace. Nothing here was written by a model.`
      : `Reading ${pulse.schema || 'rca_orch'}. Every number below is computed in ClickHouse `
        + `and reproducible from the queries in the trace.`;

    /* Say plainly when a configured source is unreachable or empty, rather than
       rendering an empty page that looks like "nothing went wrong". */
    const notes = pulse.notes || [];
    const host = document.getElementById('notes');
    if (host) {
      host.innerHTML = notes.length
        ? `<div class="err-box"><b>Source status</b><br>${notes.map(esc).join('<br>')}
           <br><br>Checked <span class="num">${esc(pulse.schema || '')}</span>,
           events from <span class="num">${esc(pulse.events_table || '')}</span>.
           Full detail at <span class="num">/api/diag</span>.</div>`
        : '';
    }

    renderTiles(pulse, incidents);
    drawOverview(incidents, tsRes.rows || []);
    renderList(incidents);
    if (n) { renderDetail(incidents[0]); if (window.lcSetContext) window.lcSetContext(incidents[0]); }
    else document.getElementById('detail').innerHTML =
      `<div class="panel empty-state">${esc(pulse.schema || 'rca_orch')}.v_narration returned no rows.</div>`;

  } catch (e) {
    document.getElementById('h1').textContent = 'Error loading data';
    document.getElementById('dek').textContent = e.message;
    document.getElementById('list').innerHTML = `<div class="err-box">${esc(e.message)}</div>`;
  }
}

load();

/* ============================ AI briefing widget ============================ */
(() => {
  const LC = {
    url:       localStorage.getItem('lc:url')   || 'https://openrouter.ai/api/v1',
    token:     localStorage.getItem('lc:token') || '',
    model:     localStorage.getItem('lc:model') || 'openai/gpt-4o',
    history:   [],    // [{role, content}] — full conversation kept client-side
    activeInc: null,
    busy:      false,
    contextMd: '',    // loaded from /api/context (ai-context.md)
  };

  // Load the AI instruction context file once at startup
  fetch('/api/context').then(r => r.text()).then(t => { LC.contextMd = t; }).catch(() => {});

  const pnl   = document.getElementById('lc-panel');
  const chat  = document.getElementById('lc-chat');
  const cfg   = document.getElementById('lc-cfg');
  const msgs  = document.getElementById('lc-msgs');
  const chips = document.getElementById('lc-chips');
  const inp   = document.getElementById('lc-input');
  const snd   = document.getElementById('lc-send');
  const subEl = document.getElementById('lc-sub');

  const isOpen  = () => pnl.getAttribute('aria-hidden') === 'false';
  const inSetup = () => cfg.style.display !== 'none';

  function openPanel() {
    pnl.setAttribute('aria-hidden', 'false');
    if (!LC.token) { showSetup(); return; }
    showChat();
    if (msgs.children.length === 0) autoGreet();
    else inp.focus();
  }
  function closePanel() { pnl.setAttribute('aria-hidden', 'true'); }

  function showChat() { cfg.style.display = 'none'; chat.style.display = ''; inp.focus(); }
  function showSetup() {
    chat.style.display = 'none'; cfg.style.display = '';
    const u = cfg.querySelector('#lc-s-url');
    const t = cfg.querySelector('#lc-s-tok');
    const m = cfg.querySelector('#lc-s-mdl');
    if (u) u.value = LC.url;
    if (t) t.value = LC.token;
    if (m) m.value = LC.model;
    if (u) u.focus();
  }

  document.getElementById('lc-btn').addEventListener('click', () => isOpen() ? closePanel() : openPanel());
  document.getElementById('lc-close').addEventListener('click', closePanel);
  document.getElementById('lc-settings').addEventListener('click', () => inSetup() ? showChat() : showSetup());

  cfg.querySelector('#lc-s-save').addEventListener('click', () => {
    const u = cfg.querySelector('#lc-s-url').value.trim().replace(/\/$/, '');
    const t = cfg.querySelector('#lc-s-tok').value.trim();
    const m = cfg.querySelector('#lc-s-mdl').value.trim() || 'gpt-4o';
    if (!u || !t) { cfg.querySelector('.lc-s-err').textContent = 'URL and token are required.'; return; }
    cfg.querySelector('.lc-s-err').textContent = '';
    LC.url = u; LC.token = t; LC.model = m;
    localStorage.setItem('lc:url', u);
    localStorage.setItem('lc:token', t);
    localStorage.setItem('lc:model', m);
    showChat();
    if (msgs.children.length === 0) autoGreet();
  });

  /* --- messages --- */
  function addMsg(role, text) {
    const d = document.createElement('div');
    d.className = `lc-m ${role}`;
    d.textContent = text;
    msgs.appendChild(d);
    msgs.scrollTop = msgs.scrollHeight;
    return d;
  }

  function setChips(labels) {
    chips.textContent = '';
    labels.forEach(lbl => {
      const b = document.createElement('button');
      b.className = 'lc-chip'; b.type = 'button'; b.textContent = lbl;
      b.addEventListener('click', () => { chips.textContent = ''; doSend(lbl); });
      chips.appendChild(b);
    });
  }

  /* --- context builder: ai-context.md instructions + live incident data --- */
  function buildSystemPrompt(inc) {
    const id = inc._letter || inc.incident_id || '?';
    const pp = (v) => v != null ? Number(v).toFixed(2) + '%' : 'n/a';
    const lines = [
      `=== ACTIVE INCIDENT: ${id} ===`,
      `Metric: ${inc.metric}  |  Period: ${inc.window_start} → ${inc.window_end}  |  Days: ${inc.days ?? '?'}`,
      `Effect: ${pp(inc.metric_change_pct)}  |  Z-score: ${inc.peak_z ?? 'n/a'}`,
      `Culprit: ${inc.culprit_val ? `${inc.culprit_dim} = ${inc.culprit_val}` : 'none — platform-wide'}`,
      `Verdict: ${inc.verdict || 'pending'}`,
    ];
    if (inc.culprit_val) {
      lines.push('', 'Attribution:',
        `  ${inc.culprit_dim} = ${inc.culprit_val}`,
        `  - Traffic share: ${inc.culprit_share_pct != null ? Number(inc.culprit_share_pct).toFixed(1) : 'n/a'}%`,
        `  - Explains: ${pp(inc.explains_pct)} of the blended move`,
        `  - Rate during incident: ${inc.culprit_value ?? 'n/a'}  (baseline: ${inc.culprit_baseline ?? 'n/a'})`,
        `  - Segment change: ${pp(inc.culprit_change_pct)}`,
      );
    }
    if (inc.clears_anomaly != null) {
      lines.push('', `Exclusion test: removing culprit ${inc.clears_anomaly ? 'CLEARS' : 'does not clear'} the anomaly`);
      if (inc.global_without_culprit != null)
        lines.push(`  Global without culprit: ${inc.global_without_culprit}  (baseline: ${inc.global_without_culprit_baseline})`);
    }
    if (Array.isArray(inc.ruled_out_segments) && inc.ruled_out_segments.length) {
      lines.push('', 'Other segments (ruled out):');
      inc.ruled_out_segments.forEach(s => lines.push(`  - ${s.dim} = ${s.val}: explains ${pp(s.explains_pct)}`));
    }
    if (Array.isArray(inc.ruled_out_dimensions) && inc.ruled_out_dimensions.length) {
      lines.push('', 'Dimensions that moved uniformly (not the cause):');
      inc.ruled_out_dimensions.forEach(d => lines.push(`  - ${d.dim}: spread ${d.spread ?? 'n/a'}`));
    }
    const incidentSection = lines.join('\n');
    return LC.contextMd ? `${LC.contextMd}\n\n---\n\n${incidentSection}` : incidentSection;
  }

  /* --- auto greet (no API call, local summary) --- */
  function autoGreet() {
    const inc = LC.activeInc;
    if (!inc) {
      addMsg('assistant', 'No incidents loaded yet — waiting for data from rca_orch.v_narration. Open an incident to start briefing.');
      return;
    }
    const id = inc._letter || inc.incident_id || '?';
    const pct = inc.metric_change_pct != null ? (inc.metric_change_pct * 100).toFixed(1) : '?';
    const severe = Math.abs(inc.peak_z || 0) > 10 || inc.metric_change_pct < -0.05;
    addMsg('system', `Incident ${id} · ${inc.window_start}${inc.window_end !== inc.window_start ? ' → ' + inc.window_end : ''}`);
    addMsg('assistant', `${severe ? '⬤ Critical' : '◎ Warning'} — ${inc.metric} ${pct}%\n${inc.verdict || 'Verdict loading from rca_orch.v_narration…'}`);
    setChips(['Explain this', 'Walk me through the evidence', 'Why this segment and not others?', 'What should we do?']);
  }

  /* --- tool definition for live ClickHouse queries --- */
  const TOOLS = [{
    type: 'function',
    function: {
      name: 'run_query',
      description: 'Execute a read-only SELECT query against the ClickHouse RCA database. Returns column names and up to 100 rows. Use for live data not already in the incident context.',
      parameters: {
        type: 'object',
        properties: { sql: { type: 'string', description: 'A SELECT SQL statement' } },
        required: ['sql'],
      },
    },
  }];

  /* --- execute a tool call and return the result as a string --- */
  async function runTool(name, argsStr) {
    if (name !== 'run_query') return `Unknown tool: ${name}`;
    let args;
    try { args = JSON.parse(argsStr); } catch { return 'Error: could not parse tool arguments'; }
    try {
      const res = await fetch('/api/run-query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sql: args.sql }),
      });
      const data = await res.json();
      if (data.error) return `Query error: ${data.error}`;
      const header = data.columns.join('\t');
      const rows = data.rows.map(r => r.join('\t')).join('\n');
      return `${header}\n${rows || '(no rows)'}`;
    } catch (e) {
      return `Error: ${e.message}`;
    }
  }

  /* --- stream one LLM turn, return {reply, toolCalls, finishReason} --- */
  async function streamTurn(thinkingEl) {
    const res = await fetch(`${LC.url}/chat/completions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${LC.token}` },
      body: JSON.stringify({ model: LC.model, messages: LC.history, stream: true, max_tokens: 800, tools: TOOLS }),
    });
    if (!res.ok) {
      const err = await res.text().catch(() => '');
      throw new Error(`HTTP ${res.status}${err ? ' — ' + err.slice(0, 160) : ''}`);
    }

    const reader = res.body.getReader();
    const dec = new TextDecoder();
    let buf = '', reply = '', finishReason = null;
    const toolCalls = [];  // {id, name, args} — accumulated from delta chunks

    outer: while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      const lines = buf.split('\n');
      buf = lines.pop();
      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        const raw = line.slice(6).trim();
        if (raw === '[DONE]') { buf = ''; break outer; }
        try {
          const chunk = JSON.parse(raw);
          const choice = chunk.choices?.[0];
          if (!choice) continue;
          if (choice.finish_reason) finishReason = choice.finish_reason;
          const delta = choice.delta;
          if (delta?.content) {
            reply += delta.content;
            thinkingEl.textContent = reply;
            msgs.scrollTop = msgs.scrollHeight;
          }
          if (delta?.tool_calls) {
            for (const tc of delta.tool_calls) {
              const i = tc.index ?? 0;
              if (!toolCalls[i]) toolCalls[i] = { id: '', name: '', args: '' };
              if (tc.id) toolCalls[i].id = tc.id;
              if (tc.function?.name)      toolCalls[i].name += tc.function.name;
              if (tc.function?.arguments) toolCalls[i].args += tc.function.arguments;
            }
          }
        } catch { /* partial chunk */ }
      }
    }
    return { reply, toolCalls: toolCalls.filter(Boolean), finishReason };
  }

  /* --- send via OpenAI-compatible /chat/completions with tool-call loop --- */
  async function doSend(text) {
    text = text.trim();
    if (!text || LC.busy) return;
    if (!LC.token) { showSetup(); return; }

    chips.textContent = '';
    addMsg('user', text);
    const thinking = addMsg('thinking', 'Thinking…');
    LC.busy = true; snd.disabled = true;

    if (LC.history.length === 0 && LC.activeInc) {
      LC.history.push({ role: 'system', content: buildSystemPrompt(LC.activeInc) });
    }
    LC.history.push({ role: 'user', content: text });

    try {
      thinking.className = 'lc-m assistant';
      thinking.textContent = '…';
      let reply = '';

      /* agentic loop: keep going until the model returns text (not a tool call) */
      for (let round = 0; round < 5; round++) {
        const { reply: r, toolCalls, finishReason } = await streamTurn(thinking);
        reply = r;

        if (finishReason === 'tool_calls' && toolCalls.length) {
          /* append the assistant's tool-call turn to history */
          LC.history.push({
            role: 'assistant',
            content: null,
            tool_calls: toolCalls.map(tc => ({
              id: tc.id,
              type: 'function',
              function: { name: tc.name, arguments: tc.args },
            })),
          });

          /* execute each tool and append results */
          for (const tc of toolCalls) {
            thinking.textContent = `Querying ClickHouse…`;
            const result = await runTool(tc.name, tc.args);
            LC.history.push({ role: 'tool', tool_call_id: tc.id, content: result });
          }
          thinking.textContent = reply || '…';
          /* loop back for the model's response to the tool result */
        } else {
          break;
        }
      }

      if (reply) LC.history.push({ role: 'assistant', content: reply });
      else thinking.textContent = '(empty response)';
    } catch (e) {
      thinking.className = 'lc-m error';
      thinking.textContent = `${e.message} — check your URL and token (⚙).`;
      LC.history.pop();
      setChips(['Open settings']);
    }

    LC.busy = false; snd.disabled = false; inp.focus();
  }

  snd.addEventListener('click', () => { const v = inp.value; inp.value = ''; inp.style.height = ''; doSend(v); });
  inp.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); const v = inp.value; inp.value = ''; inp.style.height = ''; doSend(v); }
  });
  inp.addEventListener('input', () => { inp.style.height = 'auto'; inp.style.height = Math.min(inp.scrollHeight, 90) + 'px'; });

  /* --- context update hook (called from renderList and initial load) --- */
  window.lcSetContext = function(inc) {
    LC.activeInc = inc;
    LC.history = [];
    const id = inc._letter || inc.incident_id || '?';
    if (subEl) subEl.textContent = `AI Briefing · Incident ${id}`;
    if (isOpen() && !inSetup() && msgs.children.length > 0) {
      addMsg('system', `Switched to Incident ${id} — ${inc.verdict || inc.metric}`);
      setChips(['Brief me on this', 'What caused it?', 'How does it compare?']);
    }
  };
})();
