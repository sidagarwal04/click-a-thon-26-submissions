#!/usr/bin/env node
/* ClickHouse control-plane MCP. Bulk file transfer and INSERT are deliberately
 * absent: ingestion is performed only by the programmatic data-plane job. */
const { Server } = require('@modelcontextprotocol/sdk/server/index.js');
const { StdioServerTransport } = require('@modelcontextprotocol/sdk/server/stdio.js');
const { CallToolRequestSchema, ListToolsRequestSchema } = require('@modelcontextprotocol/sdk/types.js');

const endpoint = process.env.CLICKHOUSE_ENDPOINT;
const user = process.env.CLICKHOUSE_USER;
const password = process.env.CLICKHOUSE_PASSWORD;
if (!endpoint || !user || !password) throw new Error('ClickHouse MCP credentials are not configured');

const readOnly = /^(SELECT|WITH|EXPLAIN|DESCRIBE|SHOW)\b/i;
const ddl = /^(CREATE\s+(TABLE|MATERIALIZED\s+VIEW))\s+(IF\s+NOT\s+EXISTS\s+)?default\./i;
function validate(sql) {
  const normalized = sql.trim().replace(/;+\s*$/, '');
  if (!normalized || /;/.test(normalized) || /\b(INSERT|ALTER|DROP|DELETE|TRUNCATE|SYSTEM|GRANT|REVOKE|KILL)\b/i.test(normalized)) {
    throw new Error('Only one bounded read query or CREATE TABLE/MATERIALIZED VIEW in the default database is allowed');
  }
  if (!readOnly.test(normalized) && !ddl.test(normalized)) throw new Error('Statement is outside the ClickHouse control-plane allowlist');
  return normalized;
}
async function execute(sql) {
  const query = validate(sql);
  const url = new URL(endpoint);
  url.searchParams.set('default_format', 'JSONCompact');
  url.searchParams.set('max_execution_time', '30');
  url.searchParams.set('max_result_rows', '1000');
  url.searchParams.set('result_overflow_mode', 'break');
  const response = await fetch(url, { method: 'POST', headers: {
    'X-ClickHouse-User': user, 'X-ClickHouse-Key': password, 'Content-Type': 'text/plain',
  }, body: query });
  const text = await response.text();
  if (!response.ok) throw new Error(`ClickHouse ${response.status}: ${text.slice(0, 2000)}`);
  return text.slice(0, 100000);
}
const server = new Server({ name: 'atlys-clickhouse-control-plane', version: '1.0.0' }, { capabilities: { tools: {} } });
server.setRequestHandler(ListToolsRequestSchema, async () => ({ tools: [{
  name: 'clickhouse_execute',
  description: 'Execute one bounded metadata/read query or scoped CREATE TABLE/CREATE MATERIALIZED VIEW in default. Bulk INSERT, blob/file transfer, and destructive SQL are unavailable.',
  inputSchema: { type: 'object', properties: { sql: { type: 'string' } }, required: ['sql'], additionalProperties: false },
}] }));
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  try { return { content: [{ type: 'text', text: await execute(request.params.arguments.sql) }] }; }
  catch (error) { return { isError: true, content: [{ type: 'text', text: error.message }] }; }
});
server.connect(new StdioServerTransport());
