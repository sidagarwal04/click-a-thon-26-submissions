/** Human-readable one-liners for MCP tool calls shown in the chat UI. */

export function bareToolName(name) {
  return String(name || 'tool').replace(/_mcp_[A-Za-z0-9_-]+$/, '')
}

function parseArgs(args) {
  if (args == null || args === '') return {}
  if (typeof args === 'object' && !Array.isArray(args)) return args
  const s = String(args).trim()
  if (!s) return {}
  try {
    const v = JSON.parse(s)
    return v && typeof v === 'object' ? v : {}
  } catch {
    return {}
  }
}

function asTableList(raw) {
  if (raw == null || raw === '') return []
  if (Array.isArray(raw)) return raw.map(String).filter(Boolean)
  const s = String(raw).trim()
  if (s.startsWith('[')) {
    try {
      const v = JSON.parse(s)
      if (Array.isArray(v)) return v.map(String).filter(Boolean)
    } catch { /* fall through */ }
  }
  return s.split(',').map(t => t.trim()).filter(Boolean)
}

function clip(s, n = 48) {
  const t = String(s || '')
  return t.length > n ? `${t.slice(0, n - 1)}…` : t
}

function metricList(metrics) {
  if (!Array.isArray(metrics) || !metrics.length) return 'metrics'
  return metrics
    .slice(0, 4)
    .map(m => {
      if (!m || typeof m !== 'object') return 'metric'
      const fn = m.fn || 'metric'
      return m.column ? `${fn}(${m.column})` : fn
    })
    .join(', ')
}

/**
 * One-line purpose string for a tool invocation.
 * @param {string} name
 * @param {string|object} args
 */
export function summarizeToolCall(name, args) {
  const bare = bareToolName(name)
  const a = parseArgs(args)

  switch (bare) {
    case 'db_schema': {
      const tables = asTableList(a.table ?? a.tables)
      if (!tables.length) return 'Listing tables in the analytics database'
      if (tables.length === 1) return `Inspecting schema for ${tables[0]}`
      return `Inspecting schema for ${tables.length} tables (${clip(tables.join(', '), 56)})`
    }
    case 'table_stats': {
      const tables = asTableList(a.table ?? a.tables)
      if (!tables.length) return 'Fetching table size statistics'
      if (tables.length === 1) return `Checking size / row count for ${tables[0]}`
      return `Checking size / row counts for ${tables.length} tables`
    }
    case 'aggregate': {
      const table = a.table || 'table'
      const parts = [metricList(a.metrics)]
      if (Array.isArray(a.group_by) && a.group_by.length) {
        parts.push(`by ${a.group_by.join(', ')}`)
      }
      if (Array.isArray(a.filters) && a.filters.length) {
        parts.push(`${a.filters.length} filter${a.filters.length > 1 ? 's' : ''}`)
      }
      return `Querying ${table}: ${parts.join(' · ')}`
    }
    case 'sample_rows': {
      const table = a.table || 'table'
      const lim = a.limit != null ? a.limit : 5
      return `Sampling up to ${lim} rows from ${table}`
    }
    case 'interrogate_spec':
      return `Reviewing spec gaps${a.spec_dir ? ` in ${clip(a.spec_dir)}` : ''}`
    case 'run_spec':
      return `Proposing schema for ${clip(a.spec_dir || 'spec')}`
    case 'approve_schema':
      return `Approving schema run ${clip(a.run_id || '', 36)}`
    case 'reject_schema':
      return `Rejecting schema run ${clip(a.run_id || '', 36)}`
    case 'get_insight':
      return `Fetching insight for ${clip(a.feature || 'feature')}`
    case 'list_insights':
      return 'Listing insight cards'
    case 'get_changelog':
      return `Reading ${a.scope || 'context'} changelog`
    case 'get_context':
      return a.version != null
        ? `Loading context snapshot v${a.version}`
        : 'Loading latest business context'
    case 'propose_context_update':
      return 'Proposing a context update'
    case 'reconcile':
      return 'Reconciling schema vs documented context'
    default:
      return `Running ${bare.replace(/_/g, ' ')}`
  }
}
