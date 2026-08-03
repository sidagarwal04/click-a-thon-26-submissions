import type { AgentEvent, ToolFamily } from './types';

// Strip MCP server suffix: run_query_mcp_atlys_data → run_query
export function cleanToolName(step: string): string {
  return step
    .replace(/_mcp_atlys_(data|context|clickhouse)$/, '')
    .replace(/^analytics_tool\[\d+\]_/, '')
    .replace(/^propose_tool\[\d+\]_/, '')
    .replace(/^review_tool\[\d+\]_/, '')
    .replace(/^chronicle_tool\[\d+\]_/, '');
}

export function classifyTool(step: string): ToolFamily {
  const s = step.toLowerCase();
  if (s.includes('run_query'))            return 'sql_query';
  if (s.includes('describe_table'))       return 'schema';
  if (s.includes('list_tables'))          return 'tables';
  if (s.includes('lookup_context'))       return 'context_lookup';
  if (s.includes('list_context_sections'))return 'context_index';
  if (s.includes('read_skill_file'))      return 'skill_file';
  if (s.includes('list_skill_files'))     return 'skill_list';
  if (s.includes('execute_python'))       return 'python';
  if (s.includes('grep_scratch') || s.includes('read_scratch')) return 'scratch';
  return 'other';
}

export function getEventFamily(ev: AgentEvent): ToolFamily {
  if (ev.kind === 'generation') return 'generation';
  if (ev.kind === 'span_start' || ev.kind === 'span_end') return 'span';
  if (ev.kind === 'tool_call' || ev.step?.includes('_tool[')) return classifyTool(ev.step);
  return 'other';
}

export function elapsed(ts: number): string {
  const s = (Date.now() - ts) / 1000;
  if (s < 2)  return 'just now';
  if (s < 60) return `${Math.floor(s)}s ago`;
  return `${Math.floor(s / 60)}m ago`;
}

export function fmtMs(ms: number | undefined): string {
  if (ms == null) return '';
  return ms < 1000 ? `${ms.toFixed(0)}ms` : `${(ms / 1000).toFixed(1)}s`;
}

// ── Simple syntax highlighters (no external library) ─────────────────────────

const SQL_KW = /\b(SELECT|FROM|WHERE|GROUP BY|ORDER BY|LIMIT|LEFT|RIGHT|INNER|JOIN|ON|HAVING|UNION ALL|UNION|WITH|AS|AND|OR|NOT|IN|IS|NULL|DISTINCT|CASE|WHEN|THEN|ELSE|END|BY|ASC|DESC|USING|IF|ROUND|COUNT|SUM|AVG|MAX|MIN|COALESCE|NULLIF|UNIQEXACT|UNIQEXACTIF|COUNTIF|QUANTILE|WINDOWFUNNEL|SEQUENCEMATCH|TODATE|TOYYYYMM|FORMATDATETIME)\b/gi;
const SQL_FN  = /\b(uniqExact|uniqExactIf|countIf|quantile|windowFunnel|sequenceMatch|toDate|toYYYYMM|formatDateTime|multiIf|arrayStringConcat|argMax|arrayJoin|toLower|toString)\b/g;
const SQL_NUM = /\b(\d+(?:\.\d+)?)\b/g;
const SQL_STR = /'([^']*)'/g;

export function highlightSQL(sql: string): string {
  const escaped = sql
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
  return escaped
    .replace(SQL_STR,  (_m, g) => `<span style="color:#22c55e">'${g}'</span>`)
    .replace(SQL_KW,   m  => `<span style="color:#f59e0b;font-weight:600">${m}</span>`)
    .replace(SQL_FN,   m  => `<span style="color:#fb923c">${m}</span>`)
    .replace(SQL_NUM,  m  => `<span style="color:#60a5fa">${m}</span>`);
}

const PY_KW  = /\b(import|from|def|class|return|for|in|if|else|elif|with|as|and|or|not|True|False|None|print|len|range|lambda|yield|try|except|finally|raise|pass|break|continue)\b/g;
const PY_STR = /("""[\s\S]*?"""|'''[\s\S]*?'''|"[^"]*"|'[^']*')/g;
const PY_CMT = /(#[^\n]*)/g;

export function highlightPython(code: string): string {
  const escaped = code
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
  return escaped
    .replace(PY_CMT, m  => `<span style="color:#6b7280;font-style:italic">${m}</span>`)
    .replace(PY_STR, m  => `<span style="color:#22c55e">${m}</span>`)
    .replace(PY_KW,  m  => `<span style="color:#a78bfa;font-weight:600">${m}</span>`);
}

// Truncate long strings for preview
export function truncate(s: string, n = 120): string {
  if (!s) return '';
  return s.length > n ? s.slice(0, n) + '…' : s;
}

export function prettyJSON(v: unknown): string {
  try { return JSON.stringify(v, null, 2); } catch { return String(v); }
}
