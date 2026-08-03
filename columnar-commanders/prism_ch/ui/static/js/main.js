import { $, esc } from './core/dom.js';
import { api } from './core/api.js';
import { initNav } from './core/nav.js';
import { initInstrumentTab } from './tabs/instrument.js';
import { initInsightsTab } from './tabs/insights.js';
import { initContextTab, loadContext } from './tabs/context.js';
import { loadSchema } from './tabs/schema.js';

api('/api/health').then(h => {
  $('#status').innerHTML = h.ok
    ? `<span class="pill ok">connected</span> ${esc(h.database)} · ${esc(h.target)} · ${esc(h.llm || 'no LLM')}`
    : `<span class="pill bad">offline</span> ${esc(h.error)}`;
});

initInstrumentTab();
initInsightsTab();
initContextTab();

initNav(tab => {
  if (tab === 'context') loadContext();
  if (tab === 'schema') loadSchema();
});
