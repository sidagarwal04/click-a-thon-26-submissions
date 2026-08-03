import { $, esc, spin } from '../core/dom.js';
import { streamApi } from '../core/api.js';
import { ActivityLog } from '../core/activity-log.js';

const log = new ActivityLog('i-log', 'i-logbody');

function decisions(list) {
  if (!list || !list.length) return '';
  return `<div class="card"><b>Reasoning</b>${list.map(d => `
    <div style="margin-top:12px">
      <div>${esc(d.what)}</div>
      <div class="small muted" style="margin-top:3px">${esc(d.why)}</div>
      ${(d.rules || []).map(r => `<span class="pill" style="margin-top:6px">${esc(r)}</span>`).join('')}
      ${d.confidence != null ? `<span class="pill" style="margin-top:6px">confidence ${d.confidence}</span>` : ''}
    </div>`).join('')}</div>`;
}

// --- what actually ran ------------------------------------------------------
// The exact statements sent to ClickHouse, including the ALTERs the agent
// decided on by itself when a table already existed or a field came back
// unmapped. Those are the ones a reviewer most needs to see, so they are shown
// as SQL rather than summarised.
const KIND_LABEL = {
  create_database: 'database', create_table: 'create',
  create_view: 'view', alter_table: 'alter', other: 'sql',
};

function executedStatements(list) {
  if (!list || !list.length) return '';
  const alters = list.filter(s => s.kind === 'alter_table').length;
  return `<div class="card"><b>Executed against ClickHouse</b>
    <div class="small muted" style="margin-top:4px">
      ${list.length} statement(s)${alters ? ` — including ${alters} ALTER the agent decided on itself` : ''}</div>
    ${list.map(s => `
      <div style="margin-top:12px">
        <span class="pill ${s.ok ? 'ok' : 'bad'}">${s.ok ? 'ok' : 'failed'}</span>
        <span class="pill">${esc(KIND_LABEL[s.kind] || s.kind)}</span>
        ${s.table ? `<code>${esc(s.table)}</code>` : ''}
        <pre style="margin-top:7px">${esc(s.sql)}</pre>
        ${s.error ? `<div class="small" style="margin-top:6px;color:var(--bad)">${esc(s.error)}</div>` : ''}
      </div>`).join('')}</div>`;
}

function actionsCard(r) {
  // No split happened. Say so loudly and say why - a single table that should
  // have been five is the exact failure that looks like success.
  if (!r.actions || !r.actions.length) {
    if (r.action_source === 'none') {
      return `<div class="card">
        <span class="pill warn">no user actions found — one table for the whole feature</span>
        <div class="small" style="margin-top:10px">
          Tables come from the spec's <b>User actions (raw events emitted)</b> list, one per action.
          Nothing was found in the spec text, so the events were kept in a single table instead.</div>
        <div class="small muted" style="margin-top:8px">
          Upload <code>spec.md</code> or paste it into the spec box, then design again.</div>
      </div>`;
    }
    return '';
  }
  const warn = [];
  if (r.empty_actions && r.empty_actions.length)
    warn.push(`<div class="small" style="margin-top:9px"><span class="pill warn">no rows</span>
      declared in the spec but absent from the data: ${r.empty_actions.map(esc).join(', ')}</div>`);
  if (r.undeclared_actions && Object.keys(r.undeclared_actions).length)
    warn.push(`<div class="small" style="margin-top:9px"><span class="pill warn">undeclared</span>
      in the data but not in the spec: ${Object.entries(r.undeclared_actions)
        .map(([k, v]) => `${esc(k)} (${v})`).join(', ')}</div>`);
  return `<div class="card"><b>User actions — one table each</b>
    <div class="small muted" style="margin-top:4px">
      the spec decides the tables; the events file is correlated onto it</div>
    <table style="margin-top:9px"><tr><th>action</th><th>profiled</th><th>rows</th></tr>
    ${r.actions.map(a => `<tr>
      <td><code>${esc(a.action)}</code></td>
      <td class="muted">${a.sampled.toLocaleString()}</td>
      <td>${a.total.toLocaleString()}</td></tr>`).join('')}
    </table>${warn.join('')}</div>`;
}

function loadResults(list) {
  if (!list || !list.length) return '';
  // Every row of each action's group, not its profiling sample - an INSERT is
  // not an LLM call, so there is no cost reason to leave real events out.
  return `<div class="card"><b>Data load</b>
    <div class="small muted" style="margin-top:4px">every row of each action, not the profiling sample</div>
    ${list.map(l => `
    <div style="margin-top:10px">
      <span class="pill ${l.error ? 'bad' : 'ok'}">${esc(l.table)}</span>
      ${l.error ? `<span class="small">${esc(l.error)}</span>`
                : `<span class="small">loaded ${l.loaded.toLocaleString()}/${l.attempted.toLocaleString()}</span>`}
      ${l.columns_added.length ? `<div class="small muted" style="margin-top:4px">
        added column(s): ${l.columns_added.map(esc).join(', ')} — reported unmapped by ClickHouse, inferred and retried</div>` : ''}
    </div>`).join('')}</div>`;
}

function renderInstrument(r) {
  if (r.error) {
    $('#i-out').innerHTML = `<div class="card"><span class="pill bad">failed</span>
      <pre style="margin-top:10px">${esc(r.error)}</pre></div>`
      + executedStatements(r.executed_statements) + decisions(r.decisions);
    $('#i-execute').disabled = true;
    return;
  }
  const tables = (r.actions && r.actions.length) || (r.load_results || []).length;
  const sampleNote = r.sampled
    ? `<span class="pill">profiled ${r.events_sampled.toLocaleString()} of ${(r.events_total || 0).toLocaleString()}</span>`
    : `<span class="pill">${r.events_sampled} events</span>`;
  $('#i-out').innerHTML = `
    <div class="card">
      <span class="pill ${r.executed ? 'ok' : 'warn'}">${
        r.executed ? `${tables} table(s) created and loaded` : 'preview — nothing created'}</span>
      <span class="pill">run ${esc(r.run_id)}</span>
      ${sampleNote}
      ${r.trace_id ? `<span class="pill">trace ${esc(r.trace_id.slice(0, 12))}…</span>` : ''}
      <div class="small muted" style="margin-top:11px">${
        r.executed ? 'Statements below already ran.' : 'Proposed DDL — nothing has run yet.'}</div>
      <pre style="margin-top:7px">${esc((r.ddl || []).join(';\n\n'))};</pre>
      ${r.notes ? `<div class="small muted" style="margin-top:10px">${esc(r.notes)}</div>` : ''}
    </div>`
    + actionsCard(r)
    + executedStatements(r.executed_statements)
    + loadResults(r.load_results)
    + decisions(r.decisions);
  $('#i-execute').disabled = !!r.executed;
}

// --- upload -----------------------------------------------------------------
// Sampling now happens on the server (prism_ch.agents.sampling), not here -
// this just reads the raw file text and shows an immediate line-count note.
// Selecting a file and pasting into the textarea are two separate input
// modes: a file is sampled server-side, pasted text is used exactly as given.
let rawFileText = null, rawFileName = '';

function countRecords(text) {
  try {
    const parsed = JSON.parse(text);
    if (Array.isArray(parsed)) return parsed.length;
    return 1;
  } catch { return text.split('\n').map(l => l.trim()).filter(Boolean).length; }
}

function wireUpload() {
  $('#i-file').onchange = async e => {
    const f = e.target.files[0];
    if (!f) return;
    rawFileText = await f.text();
    rawFileName = f.name;
    const total = countRecords(rawFileText);
    const pct = Math.min(100, Math.max(1, +$('#i-pct').value || 15));
    $('#i-filenote').textContent = `${f.name} — ${total.toLocaleString()} events` +
      ($('#i-sample').checked ? `, will sample ~${pct}% server-side` : ', using all');
    $('#i-clearfile').style.display = 'inline';
    $('#i-events').value = '';
    $('#i-events').placeholder = `${f.name} attached — clear it to paste events instead`;
    $('#i-events').disabled = true;
  };

  $('#i-clearfile').onclick = () => {
    rawFileText = null; rawFileName = '';
    $('#i-file').value = '';
    $('#i-filenote').textContent = '';
    $('#i-clearfile').style.display = 'none';
    $('#i-events').disabled = false;
    $('#i-events').placeholder = 'paste events directly, or upload a file above';
  };

  // spec.md can be attached rather than pasted - the tables come from its
  // user actions either way, so it should not matter which route it took.
  $('#i-specfile').onchange = async e => {
    const f = e.target.files[0];
    if (!f) return;
    $('#i-brief').value = await f.text();
    const found = ($('#i-brief').value.match(/^\s*[-*]\s+`[A-Za-z0-9_.]+`/gm) || []).length;
    $('#i-specnote').textContent = found
      ? `${f.name} — ${found} user action(s) found`
      : `${f.name} — no "User actions" bullets found`;
  };
}

async function runInstrument(execute) {
  const btn = execute ? $('#i-execute') : $('#i-preview');
  btn.disabled = true; spin($('#i-spin'), true);
  log.reset();

  const body = { name: $('#i-name').value, brief: $('#i-brief').value, execute };
  const acts = (body.brief.match(/^\s*[-*]\s+`[A-Za-z0-9_.]+`/gm) || []).length;
  log.line(acts ? `spec declares ${acts} user action(s) — one table each`
                : 'no user actions in the spec — will fall back to a single table', acts ? 'run' : 'fail');
  if (rawFileText != null) {
    body.file_b64 = btoa(unescape(encodeURIComponent(rawFileText)));
    body.sample_pct = $('#i-sample').checked ? Math.min(100, Math.max(1, +$('#i-pct').value || 15)) : 100;
    log.line(`splitting ${rawFileName} by user action, profiling ${body.sample_pct}% of each`, 'run');
  } else {
    body.events = $('#i-events').value;
    const n = body.events.trim() ? (body.events.match(/\n/g) || []).length + 1 : 0;
    log.line(`using ${n.toLocaleString()} pasted event(s) as-is`, 'run');
  }

  try {
    let result = null;
    await streamApi('/api/instrument/stream', body, evt => {
      if (evt.type === 'step_start') log.stepStart(evt.agent, evt.action);
      else if (evt.type === 'step_end') log.stepEnd(evt.agent, evt.action, evt.duration_ms, evt.ok);
      else if (evt.type === 'done') result = evt.result;
      else if (evt.type === 'error') result = { error: evt.message };
    });
    if (!result) result = { error: 'the stream ended with no result' };

    const rows = (result.load_results || []).reduce((n, l) => n + l.loaded, 0);
    log.line(result.error ? `failed: ${String(result.error).slice(0, 160)}`
                     : (result.executed
                        ? `done — ${(result.load_results || []).length} table(s) updated, ${rows.toLocaleString()} row(s) loaded`
                        : 'preview complete — nothing created'),
             result.error ? 'fail' : 'done');
    renderInstrument(result);
  } finally {
    spin($('#i-spin'), false);
    $('#i-preview').disabled = false;
  }
}

export function initInstrumentTab() {
  wireUpload();
  $('#i-preview').onclick = () => runInstrument(false);
  $('#i-execute').onclick = () => runInstrument(true);
}
