#!/usr/bin/env node
/* Minimal, append-safe ClickStack Cloud dashboard adapter. It exposes only
 * source discovery and idempotent dashboard publication for one configured
 * service; credentials never enter model-visible tool arguments or results. */
const { Server } = require('@modelcontextprotocol/sdk/server/index.js');
const { StdioServerTransport } = require('@modelcontextprotocol/sdk/server/stdio.js');
const { CallToolRequestSchema, ListToolsRequestSchema } = require('@modelcontextprotocol/sdk/types.js');

const apiBase = (process.env.CLICKHOUSE_CLOUD_API_BASE || 'https://api.clickhouse.cloud/v1').replace(/\/$/, '');
const organizationId = process.env.CLICKHOUSE_CLOUD_ORGANIZATION_ID || '';
const serviceId = process.env.CLICKSTACK_SERVICE_ID || '';
const keyId = process.env.CLICKHOUSE_CLOUD_API_KEY_ID || '';
const keySecret = process.env.CLICKHOUSE_CLOUD_API_KEY_SECRET || '';
const appBase = (process.env.CLICKSTACK_APP_URL || '').replace(/\/$/, '');
const uuid = { type: 'string', pattern: '^[0-9a-fA-F-]{36}$' };

function configured() {
  if (!organizationId || !serviceId || !keyId || !keySecret) {
    throw new Error('ClickStack Cloud API is not configured; set organization, service, key ID, and key secret');
  }
}

async function request(path, method = 'GET', body) {
  configured();
  const response = await fetch(`${apiBase}/organizations/${organizationId}/services/${serviceId}/clickstack${path}`, {
    method,
    headers: {
      authorization: `Basic ${Buffer.from(`${keyId}:${keySecret}`).toString('base64')}`,
      'content-type': 'application/json',
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const text = await response.text();
  if (!response.ok) throw new Error(`ClickStack Cloud ${response.status}: ${text.slice(0, 1500)}`);
  return text ? JSON.parse(text) : {};
}

function records(payload) {
  if (Array.isArray(payload)) return payload;
  return payload.data || payload.items || payload.results || [];
}

const tools = [
  {
    name: 'clickstack_list_sources',
    description: 'List bounded ClickStack/HyperDX sources for the configured ClickHouse Cloud service.',
    inputSchema: { type: 'object', properties: {}, additionalProperties: false },
  },
  {
    name: 'clickstack_get_dashboard',
    description: 'Read one ClickStack/HyperDX dashboard by its stable ID.',
    inputSchema: { type: 'object', properties: { dashboard_id: { type: 'string', minLength: 1, maxLength: 200 } }, required: ['dashboard_id'], additionalProperties: false },
  },
  {
    name: 'clickstack_upsert_dashboard',
    description: 'Create or update one run-scoped ClickStack/HyperDX dashboard. Repeated calls for the same run update the same dashboard.',
    inputSchema: {
      type: 'object',
      properties: {
        run_id: uuid,
        name: { type: 'string', minLength: 1, maxLength: 160 },
        tiles: { type: 'array', minItems: 1, maxItems: 12, items: { type: 'object' } },
        filters: { type: 'array', maxItems: 12, items: { type: 'object' } },
        tags: { type: 'array', maxItems: 12, items: { type: 'string', maxLength: 80 } },
      },
      required: ['run_id', 'name', 'tiles'],
      additionalProperties: false,
    },
  },
];

const server = new Server({ name: 'atlys-clickstack-cloud', version: '1.0.0' }, { capabilities: { tools: {} } });
server.setRequestHandler(ListToolsRequestSchema, async () => ({ tools }));
server.setRequestHandler(CallToolRequestSchema, async ({ params }) => {
  try {
    if (params.name === 'clickstack_list_sources') {
      const payload = await request('/sources');
      const sources = records(payload).slice(0, 100).map(({ id, name, type, tableName, databaseName }) => ({ id, name, type, tableName, databaseName }));
      return { content: [{ type: 'text', text: JSON.stringify({ configured: true, sources }) }] };
    }
    if (params.name === 'clickstack_get_dashboard') {
      const dashboard = await request(`/dashboards/${encodeURIComponent(params.arguments.dashboard_id)}`);
      return { content: [{ type: 'text', text: JSON.stringify({ dashboard }) }] };
    }
    if (params.name === 'clickstack_upsert_dashboard') {
      const { run_id, name, tiles, filters = [], tags = [] } = params.arguments;
      const runTag = `atlys-run:${run_id}`;
      const existing = records(await request('/dashboards')).find((item) => Array.isArray(item.tags) && item.tags.includes(runTag));
      const body = { name, tiles, filters, tags: [...new Set([...tags, 'atlys-finalizer', runTag])] };
      const dashboard = existing
        ? await request(`/dashboards/${encodeURIComponent(existing.id)}`, 'PATCH', body)
        : await request('/dashboards', 'POST', body);
      const id = dashboard.id || dashboard.data?.id || existing?.id || null;
      const url = dashboard.url || dashboard.data?.url || (appBase && id ? `${appBase}/dashboards/${id}` : null);
      return { content: [{ type: 'text', text: JSON.stringify({ status: existing ? 'updated' : 'created', dashboard_id: id, dashboard_url: url }) }] };
    }
    return { isError: true, content: [{ type: 'text', text: 'Unknown ClickStack tool' }] };
  } catch (error) {
    return { isError: true, content: [{ type: 'text', text: error.message }] };
  }
});
server.connect(new StdioServerTransport());
