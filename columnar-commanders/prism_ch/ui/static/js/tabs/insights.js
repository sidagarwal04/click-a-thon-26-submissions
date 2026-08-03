import { $, esc, spin } from '../core/dom.js';
import { streamApi } from '../core/api.js';
import { ActivityLog } from '../core/activity-log.js';

const log = new ActivityLog('a-log', 'a-logbody');

// Exported so the Context tab can populate this tab with the report an
// auto-triggered post-refresh analytics run produced - the Insights tab is
// already showing the right thing by the time a user switches to it, no
// re-run of "Run analysis" needed.
export function showInsightReport(r) {
  if (r.error) {
    $('#a-out').innerHTML = `<div class="card"><span class="pill bad">failed</span>
      <pre style="margin-top:10px">${esc(r.error)}</pre></div>`;
    return;
  }
  const items = (r.insights || []).sort((a, b) => b.confidence - a.confidence);
  $('#a-out').innerHTML = `
    <div class="card">
      <span class="pill">context v${r.context_version}</span>
      <span class="pill">${r.queries_run} queries</span>
      <span class="pill">run ${esc(r.run_id)}</span>
      ${r.summary ? `<p style="margin:12px 0 0">${esc(r.summary)}</p>` : ''}
    </div>
    ${items.map(i => `
      <div class="card">
        <div><b>${esc(i.headline)}</b></div>
        <div class="small muted" style="margin-top:5px">${esc(i.detail)}</div>
        <div style="margin-top:10px"><b class="small">Why</b> — ${esc(i.why)}</div>
        ${i.recommendation ? `<div class="small" style="margin-top:8px"><b>Next</b> — ${esc(i.recommendation)}</div>` : ''}
        <div style="margin-top:10px">
          <span class="pill">${esc(i.cut)}</span>
          ${(i.context_refs || []).map(c => `<span class="pill warn">${esc(c)}</span>`).join('')}
          <span class="pill">confidence ${i.confidence.toFixed(2)}</span>
        </div>
        <div class="bar"><i style="width:${Math.round(i.confidence * 100)}%"></i></div>
      </div>`).join('') || '<div class="card muted">No insights — check the trace.</div>'}`;
}

async function runAnalysis() {
  $('#a-run').disabled = true; spin($('#a-spin'), true);
  log.reset();
  try {
    let result = null;
    await streamApi('/api/analyze/stream', { focus: $('#a-focus').value }, evt => {
      if (evt.type === 'step_start') log.stepStart(evt.agent, evt.action);
      else if (evt.type === 'step_end') log.stepEnd(evt.agent, evt.action, evt.duration_ms, evt.ok);
      else if (evt.type === 'done') result = evt.result;
      else if (evt.type === 'error') result = { error: evt.message };
    });
    if (!result) result = { error: 'the stream ended with no result' };
    showInsightReport(result);
  } finally {
    spin($('#a-spin'), false); $('#a-run').disabled = false;
  }
}

export function initInsightsTab() {
  $('#a-run').onclick = runAnalysis;
}
