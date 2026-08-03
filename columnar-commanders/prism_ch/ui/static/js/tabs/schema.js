import { $, esc } from '../core/dom.js';
import { api } from '../core/api.js';

export async function loadSchema() {
  const s = await api('/api/schema-history');
  $('#s-out').innerHTML = `
    <div class="card"><b>Tables</b>
      <div class="small muted" style="margin:6px 0 12px">
        Agent-generated tables carry the <code>${esc(s.prefix || '')}</code> prefix. Newest first.</div>
      <table><tr><th></th><th>table</th><th>engine</th><th>ORDER BY</th><th>partition</th><th>rows</th><th>modified</th></tr>
      ${(s.tables || []).map(t => `<tr>
        <td>${t.generated ? '<span class="pill ok">agent</span>' : '<span class="pill">source</span>'}</td>
        <td><code>${esc(t.name)}</code></td><td>${esc(t.engine)}</td>
        <td class="muted">${esc(t.order_by)}</td><td class="muted">${esc(t.partition_by)}</td>
        <td>${t.rows ?? ''}</td><td class="muted">${esc(t.modified)}</td></tr>`).join('')}
      </table></div>`;
}
