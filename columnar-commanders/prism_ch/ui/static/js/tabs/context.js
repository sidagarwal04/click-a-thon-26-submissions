import { $, esc, spin } from '../core/dom.js';
import { api, streamApi } from '../core/api.js';
import { ActivityLog } from '../core/activity-log.js';
import { renderVisGraph, initGraphControls } from './context-graph.js';
import { showInsightReport } from './insights.js';

const log = new ActivityLog('c-refresh-log', 'c-refresh-logbody');

export async function loadContext() {
  const c = await api('/api/context');
  if (c.error) {
    $('#c-summary').innerHTML = `<div class="card"><span class="pill bad">error</span> ${esc(c.error)}</div>`;
    return;
  }
  const sev = s => s === 'high' ? 'bad' : s === 'medium' ? 'warn' : '';

  // summary bar
  $('#c-summary').innerHTML = `<div class="card">
    <span class="pill ok">v${c.version}</span>
    <span class="pill">${c.entries || 0} entries</span>
    ${Object.entries(c.counts || {}).map(([k, v]) => `<span class="pill">${esc(k)} ${v}</span>`).join('')}
  </div>`;

  // graph
  const allEntries = c.entry_list || [];
  const container = document.getElementById('c-graph');
  renderVisGraph(container, allEntries, c.issues || []);

  // issues card
  $('#c-issues-card').innerHTML = `<b>Contradictions &amp; gaps</b>
    ${(c.issues || []).length ? (c.issues || []).map(i => `
      <div style="margin-top:10px">
        <span class="pill ${sev(i.severity)}">${esc(i.severity)}</span>
        <span class="pill">${esc(i.kind)}</span>
        <code>${esc(i.subject)}</code>
        <div class="small muted" style="margin-top:3px">${esc(i.detail)}</div>
      </div>`).join('') : '<div class="muted small" style="margin-top:10px">None found.</div>'}`;

  // entries card with kind tabs
  const kindList = Object.keys(c.counts || {}).filter(k => k !== 'column');
  const firstKind = kindList[0] || 'metric';

  const kindLabels = {
    definition: 'definitions', metric: 'metrics', entity: 'entities',
    known_issue: 'known issues', table: 'tables', relationship: 'relationships', column: 'columns',
  };

  function renderEntries(kind) {
    const filtered = allEntries.filter(e => e.kind === kind);
    // for section-keyed entries, show cleaned key
    return filtered.length ? filtered.map(e => {
      const label = e.key.startsWith('section:') ? e.key.slice(8) : e.key;
      return `<div class="entry-row">
        <code>${esc(label)}</code>
        <span class="entry-val" title="${esc(e.value)}">${esc(e.value)}</span>
      </div>`;
    }).join('') : '<div class="muted small">No entries.</div>';
  }

  $('#c-entries-card').innerHTML = `<b>Entries</b>
    <div class="ctx-tabs" id="ctx-kind-tabs">
      ${kindList.map(k => `<button data-kind="${esc(k)}" class="${k === firstKind ? 'on' : ''}">${esc(kindLabels[k] || k)}</button>`).join('')}
    </div>
    <div id="ctx-entries-body">${renderEntries(firstKind)}</div>`;

  document.querySelectorAll('#ctx-kind-tabs button').forEach(b => b.onclick = () => {
    document.querySelectorAll('#ctx-kind-tabs button').forEach(x => x.classList.toggle('on', x === b));
    document.getElementById('ctx-entries-body').innerHTML = renderEntries(b.dataset.kind);
  });

  // changelog
  $('#c-changelog').innerHTML = c.diff ? `<div class="card"><b>Changelog — v${c.diff.from_version} → v${c.diff.to_version}</b>
    <div class="small" style="margin-top:10px">
      ${c.diff.added.map(a => `<div><span class="pill ok">+</span> ${esc(a.kind)} <code>${esc(a.key)}</code></div>`).join('')}
      ${c.diff.removed.map(a => `<div><span class="pill bad">−</span> ${esc(a.kind)} <code>${esc(a.key)}</code></div>`).join('')}
      ${c.diff.changed.map(a => `<div><span class="pill warn">~</span> ${esc(a.kind)} <code>${esc(a.key)}</code></div>`).join('')}
      ${(!c.diff.added.length && !c.diff.removed.length && !c.diff.changed.length) ? '<span class="muted">No change.</span>' : ''}
    </div></div>` : '';

  // versions
  $('#c-versions').innerHTML = `<div class="card"><b>Versions</b>
    <table><tr><th>v</th><th>when</th><th>source</th><th>entries</th><th>summary</th></tr>
    ${(c.history || []).map(h => `<tr><td>${h.version}</td><td class="muted">${esc(h.created_at)}</td>
      <td>${esc(h.source)}</td><td>${h.entry_count}</td><td class="muted">${esc(h.summary)}</td></tr>`).join('')}
    </table></div>`;
}

// The overview belongs here; the detail belongs in the Insights tab.
function renderAnalyticsSummary(report, runId) {
  const el = $('#c-analytics');
  if (!runId) {
    el.innerHTML = '';
    return;
  }
  const count = (report.insights || []).length;
  el.innerHTML = `<div class="card">
    <span class="pill ok">insights updated</span>
    <span class="pill">${count} insight${count === 1 ? '' : 's'}</span>
    <span class="pill">run ${esc(runId)}</span>
    ${report.summary ? `<p style="margin:10px 0 0">${esc(report.summary)}</p>` : ''}
    <div class="actions" style="margin:12px 0 0">
      <button class="act ghost" id="c-view-insights" style="width:auto">View full insights →</button>
    </div>
  </div>`;
  $('#c-view-insights').onclick = () =>
    document.querySelector('nav button[data-tab="insights"]').click();
}

async function refreshContext(baseText) {
  const btn1 = $('#c-refresh-btn'), btn2 = $('#c-db-only-btn'), sp = $('#c-spin');
  btn1.disabled = btn2.disabled = true;
  spin(sp, true);
  log.reset();
  try {
    const body = baseText ? { base_context: baseText } : {};
    let result = null;
    await streamApi('/api/context-refresh/stream', body, evt => {
      if (evt.type === 'step_start') log.stepStart(evt.agent, evt.action);
      else if (evt.type === 'step_end') log.stepEnd(evt.agent, evt.action, evt.duration_ms, evt.ok);
      else if (evt.type === 'done') result = evt.result;
      else if (evt.type === 'error') result = { error: evt.message };
    });
    if (!result) result = { error: 'the stream ended with no result' };

    if (result.error) {
      log.line(`failed: ${String(result.error).slice(0, 160)}`, 'fail');
      $('#c-summary').innerHTML = `<div class="card"><span class="pill bad">error</span> ${esc(result.error)}</div>`;
    } else {
      log.line(`context refreshed — v${result.version}, ${result.entries} entries`, 'done');
      // ContextAgent.run() triggers the Analytics Agent itself right after
      // publishing - pre-populate the Insights tab so it's already showing
      // the fresh report by the time the user switches to it, and leave a
      // compact pointer to it here.
      if (result.analytics_run_id) {
        showInsightReport({
          ...result.analytics,
          run_id: result.analytics_run_id,
          trace_id: result.analytics_trace_id,
        });
      }
      renderAnalyticsSummary(result.analytics, result.analytics_run_id);
      await loadContext();
    }
  } catch (e) {
    log.line(`failed: ${e.message}`, 'fail');
    $('#c-summary').innerHTML = `<div class="card"><span class="pill bad">error</span> ${esc(e.message)}</div>`;
  } finally {
    btn1.disabled = btn2.disabled = false;
    spin(sp, false);
  }
}

async function searchContext() {
  const q = $('#c-search-input').value.trim();
  if (!q) { $('#c-search-input').focus(); return; }
  const btn = $('#c-search-btn'), sp = $('#c-search-spin');
  btn.disabled = true; spin(sp, true);
  try {
    const r = await api('/api/context-search', { query: q });
    if (r.error) {
      $('#c-search-results').innerHTML = `<div class="muted small" style="margin-top:10px"><span class="pill bad">error</span> ${esc(r.error)}</div>`;
      return;
    }
    if (!r.results || !r.results.length) {
      $('#c-search-results').innerHTML = `<div class="muted small" style="margin-top:10px">No matching entries found.</div>`;
      return;
    }
    $('#c-search-results').innerHTML = `<div style="margin-top:10px">
      ${r.results.map(m => `<div class="entry-row" style="margin-bottom:6px">
        <span class="pill">${esc(m.kind)}</span>
        <code>${esc(m.key)}</code>
        <span class="pill ok" style="margin-left:auto">${(m.score * 100).toFixed(0)}%</span>
        <div class="small muted" style="width:100%;margin-top:2px">${esc(m.text)}</div>
      </div>`).join('')}
    </div>`;
  } catch (e) {
    $('#c-search-results').innerHTML = `<div class="muted small" style="margin-top:10px"><span class="pill bad">error</span> ${esc(e.message)}</div>`;
  } finally {
    btn.disabled = false; spin(sp, false);
  }
}

export function initContextTab() {
  initGraphControls();
  $('#c-refresh-btn').onclick = () => {
    const text = $('#c-base-ctx').value.trim();
    if (!text) { $('#c-base-ctx').focus(); return; }
    refreshContext(text);
  };
  $('#c-db-only-btn').onclick = () => refreshContext(null);
  $('#c-search-btn').onclick = searchContext;
  $('#c-search-input').onkeydown = e => { if (e.key === 'Enter') searchContext(); };
}
