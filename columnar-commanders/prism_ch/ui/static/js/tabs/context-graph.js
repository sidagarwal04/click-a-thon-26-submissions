import { $, esc } from '../core/dom.js';

const KIND_COLORS = {
  entity: '#4b3fe0', metric: '#12805f', table: '#9a5d00',
  relationship: '#7c3aed', definition: '#6d6d78', known_issue: '#a3352d',
  column: '#3b82f6',
};
const KIND_SHAPES = { entity: 'dot', metric: 'diamond', table: 'box', relationship: 'triangle', definition: 'square', known_issue: 'triangleDown' };
const KIND_SIZES = { entity: 18, metric: 16, table: 20, relationship: 14, definition: 12, known_issue: 14 };

let _visNetwork = null;

export function renderVisGraph(container, entries, issues) {
  const isDark = window.matchMedia('(prefers-color-scheme:dark)').matches;
  const fontColor = isDark ? '#eeeef2' : '#17171c';

  // Build nodes
  const visNodes = [];
  const visEdges = [];
  const seen = new Set();
  const graphEntries = entries.filter(e => !e.key.startsWith('section:') && e.kind !== 'column');
  const nodeData = {};

  graphEntries.forEach(e => {
    const id = `${e.kind}:${e.key}`;
    if (seen.has(id)) return;
    seen.add(id);
    nodeData[id] = e;
    const color = KIND_COLORS[e.kind] || '#6d6d78';
    visNodes.push({
      id, label: e.key, group: e.kind,
      color: { background: color + '55', border: color, highlight: { background: color + '80', border: color } },
      font: { color: fontColor, size: 11, face: 'system-ui, sans-serif' },
      shape: KIND_SHAPES[e.kind] || 'dot',
      size: KIND_SIZES[e.kind] || 14,
      title: `<b>${e.kind}: ${e.key}</b><br>${e.value.slice(0, 200)}${e.detail ? '<br><i>' + e.detail.slice(0, 100) + '</i>' : ''}`,
    });
  });

  // Metric → table edges
  const tableKeys = new Set(visNodes.filter(n => n.group === 'table').map(n => nodeData[n.id].key.toLowerCase()));
  visNodes.filter(n => n.group === 'metric').forEach(m => {
    const refs = nodeData[m.id].value.toLowerCase().match(/\b([a-z_][a-z0-9_]*)\b/g) || [];
    refs.forEach(ref => {
      if (tableKeys.has(ref)) visEdges.push({ from: m.id, to: `table:${ref}`, color: { color: KIND_COLORS.metric + '80' }, dashes: false });
    });
  });

  // Entity → table edges
  visNodes.filter(n => n.group === 'entity').forEach(ent => {
    const text = (nodeData[ent.id].value + ' ' + (nodeData[ent.id].detail || '')).toLowerCase();
    visNodes.filter(n => n.group === 'table').forEach(t => {
      if (text.includes(nodeData[t.id].key.toLowerCase())) visEdges.push({ from: ent.id, to: t.id, color: { color: KIND_COLORS.entity + '60' } });
    });
  });

  // Relationship → entity edges
  visNodes.filter(n => n.group === 'relationship').forEach(rel => {
    const text = (nodeData[rel.id].key + ' ' + nodeData[rel.id].value).toLowerCase();
    visNodes.filter(n => n.group === 'entity').forEach(ent => {
      if (text.includes(nodeData[ent.id].key.toLowerCase())) visEdges.push({ from: rel.id, to: ent.id, color: { color: KIND_COLORS.relationship + '60' } });
    });
  });

  // Table join edges
  const colEntries = entries.filter(e => e.kind === 'column');
  const colsByTable = {}, colFreq = {};
  colEntries.forEach(e => {
    const dot = e.key.indexOf('.');
    if (dot < 0) return;
    const tbl = e.key.slice(0, dot), col = e.key.slice(dot + 1).toLowerCase();
    (colsByTable[tbl] = colsByTable[tbl] || new Set()).add(col);
    colFreq[col] = (colFreq[col] || 0) + 1;
  });
  const tableNames = Object.keys(colsByTable);
  const skipCols = new Set(['timestamp', 'event_type', 'event_date']);
  const threshold = Math.max(3, Math.ceil(tableNames.length * 0.6));
  Object.entries(colFreq).forEach(([col, cnt]) => { if (cnt >= threshold) skipCols.add(col); });

  const joinCandidates = [];
  for (let i = 0; i < tableNames.length; i++) {
    for (let j = i + 1; j < tableNames.length; j++) {
      const a = tableNames[i], b = tableNames[j];
      const shared = [...colsByTable[a]].filter(c => colsByTable[b].has(c) && !skipCols.has(c));
      if (shared.length >= 2) joinCandidates.push({ a, b, shared, strength: shared.length });
    }
  }
  const edgesPerNode = {};
  joinCandidates.sort((x, y) => y.strength - x.strength);
  joinCandidates.forEach(({ a, b, shared }) => {
    const ca = edgesPerNode[a] || 0, cb = edgesPerNode[b] || 0;
    if (ca >= 3 && cb >= 3) return;
    visEdges.push({
      from: `table:${a}`, to: `table:${b}`,
      label: shared.slice(0, 2).join(', '),
      font: { size: 8, color: isDark ? '#75747f' : '#9a99a4', strokeWidth: 0 },
      color: { color: KIND_COLORS.table + '50' }, dashes: [4, 4], width: 1,
    });
    edgesPerNode[a] = ca + 1;
    edgesPerNode[b] = cb + 1;
  });

  // Issue edges
  (issues || []).forEach(iss => {
    const target = visNodes.find(n => n.id === iss.subject || n.id === `${iss.kind}:${iss.subject}`);
    if (target) {
      const issId = `issue:${iss.subject}`;
      if (!seen.has(issId)) {
        seen.add(issId);
        const color = KIND_COLORS.known_issue;
        visNodes.push({
          id: issId, label: iss.subject, group: 'issue',
          color: { background: color + '55', border: color }, shape: 'triangle', size: 12,
          font: { color: fontColor, size: 10 }, title: `<b>${iss.severity} ${iss.kind}</b><br>${iss.detail}`,
        });
        nodeData[issId] = { kind: 'issue', key: iss.subject, value: iss.detail, source: iss.severity };
      }
      visEdges.push({ from: issId, to: target.id, color: { color: KIND_COLORS.known_issue + '80' }, dashes: [6, 3], width: 1.5 });
    }
  });

  // Summary stats
  const joinCount = visEdges.filter(e => e.dashes && Array.isArray(e.dashes)).length;
  const colCount = colEntries.length;
  const summaryParts = [];
  if (tableNames.length) summaryParts.push(`<b>${tableNames.length}</b> tables (${colCount} columns)`);
  if (joinCount) summaryParts.push(`<b>${joinCount}</b> join relationships`);
  const metricCount = visNodes.filter(n => n.group === 'metric').length;
  const entityCount = visNodes.filter(n => n.group === 'entity').length;
  if (metricCount) summaryParts.push(`<b>${metricCount}</b> metrics`);
  if (entityCount) summaryParts.push(`<b>${entityCount}</b> entities`);

  const gSub = document.querySelector('.g-sub');
  if (gSub) gSub.innerHTML = summaryParts.length ? summaryParts.join(' · ') + '. Scroll to zoom, drag to pan.' : 'No context data yet.';

  if (!visNodes.length) {
    container.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:var(--muted);font-size:13px">No context data yet — run the Instrumentation Agent first, then refresh.</div>';
    return;
  }

  if (_visNetwork) { _visNetwork.destroy(); _visNetwork = null; }

  _visNetwork = new vis.Network(container, {
    nodes: new vis.DataSet(visNodes),
    edges: new vis.DataSet(visEdges),
  }, {
    physics: {
      solver: 'forceAtlas2Based',
      forceAtlas2Based: { gravitationalConstant: -60, centralGravity: 0.008, springLength: 140, springConstant: 0.04 },
      stabilization: { iterations: 80, updateInterval: 25 },
    },
    interaction: { hover: true, tooltipDelay: 200, zoomView: true, dragView: true },
    edges: { smooth: { type: 'continuous' }, width: 1.2 },
    nodes: { borderWidth: 1.5, borderWidthSelected: 2.5 },
  });

  _visNetwork.once('stabilizationIterationsDone', () => {
    _visNetwork.setOptions({ physics: false });
    _visNetwork.fit({ animation: false });
  });

  _visNetwork.on('click', params => {
    if (!params.nodes.length) { $('#c-popup').innerHTML = ''; return; }
    const id = params.nodes[0];
    const data = nodeData[id];
    if (!data) return;
    const popup = $('#c-popup');
    const kindLabel = data.kind;
    const color = KIND_COLORS[data.kind] || '#6d6d78';
    const pos = params.pointer.DOM;
    const wrap = container.getBoundingClientRect();
    popup.innerHTML = `<div class="detail-popup" style="top:${wrap.top + pos.y}px;left:${Math.min(wrap.left + pos.x + 20, window.innerWidth - 380)}px">
      <span class="dp-close" id="dp-close">&times;</span>
      <span class="pill" style="background:${color}22;color:${color}">${esc(kindLabel)}</span>
      <b style="margin-top:8px">${esc(data.key)}</b>
      <div class="dp-val">${esc(data.value)}</div>
      ${data.detail ? `<div class="dp-val small" style="margin-top:6px">${esc(data.detail)}</div>` : ''}
      <div class="small muted" style="margin-top:8px">source: ${esc(data.source)}</div>
    </div>`;
    document.getElementById('dp-close').onclick = () => { popup.innerHTML = ''; };
    setTimeout(() => document.addEventListener('click', () => { popup.innerHTML = ''; }, { once: true }), 50);
  });

  // Legend
  const usedKinds = [...new Set(visNodes.map(n => n.group))];
  const legendColors = { ...KIND_COLORS, issue: KIND_COLORS.known_issue };
  $('#c-legend').innerHTML = usedKinds.map(k =>
    `<div class="g-legend-item"><div class="g-legend-dot" style="background:${legendColors[k] || '#6d6d78'}"></div>${esc(k)}</div>`
  ).join('');

  return { nodeCount: visNodes.length, edgeCount: visEdges.length, joinCount };
}

const EXPAND_ICON = '<svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M2 6V2h4M10 2h4v4M14 10v4h-4M6 14H2v-4"/></svg> Full view';
const COLLAPSE_ICON = '<svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M6 2v4H2M10 2v4h4M14 14h-4v-4M2 14h4v-4"/></svg> Exit';

export function initGraphControls() {
  const wrap = document.getElementById('graph-wrap');
  const btn = document.getElementById('g-fullscreen-btn');

  const toggle = () => {
    const isFullscreen = wrap.classList.toggle('fullscreen');
    btn.innerHTML = isFullscreen ? COLLAPSE_ICON : EXPAND_ICON;
    if (_visNetwork) {
      setTimeout(() => { _visNetwork.redraw(); _visNetwork.fit({ animation: false }); }, 50);
    }
  };

  btn.onclick = toggle;
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && wrap.classList.contains('fullscreen')) toggle();
  });
}
