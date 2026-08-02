#!/usr/bin/env node
/* Runtime data-plane tools.  They stream data server-to-server and return only
 * bounded evidence to the model; no blob URI, credential, or NDJSON body is
 * exposed through the tool protocol. */
const { Server } = require('@modelcontextprotocol/sdk/server/index.js');
const { StdioServerTransport } = require('@modelcontextprotocol/sdk/server/stdio.js');
const { CallToolRequestSchema, ListToolsRequestSchema } = require('@modelcontextprotocol/sdk/types.js');

const baseUrl = process.env.INVESTIGATIONS_API_URL;
const token = process.env.INVESTIGATION_RUNTIME_TOKEN;
if (!baseUrl || !token) throw new Error('Investigation data runtime is not configured');

const id = { type: 'string', pattern: '^[0-9a-fA-F-]{36}$' };
async function request(investigationId, action, body = {}) {
  const response = await fetch(`${baseUrl}/investigations/${investigationId}/${action}`, {
    method: 'POST', headers: { authorization: `Bearer ${token}`, 'content-type': 'application/json' }, body: JSON.stringify(body),
  });
  const text = await response.text();
  if (!response.ok) throw new Error(`Investigation data ${response.status}: ${text.slice(0, 2000)}`);
  return text.slice(0, 100000);
}
const tools = [
  ['investigation_metadata', 'Return safe source names, sizes, and hashes for an investigation.', { investigation_id: id }, ['investigation_id'], 'metadata'],
  ['read_spec', 'Read at most 16 KiB of the specification; use offsets for further bounded reads.', { investigation_id: id, offset_bytes: { type: 'integer', minimum: 0 }, max_bytes: { type: 'integer', minimum: 1, maximum: 16384 } }, ['investigation_id'], 'spec'],
  ['profile_ndjson', 'Stream the source NDJSON server-side and return bounded field/type/cardinality/event statistics.', { investigation_id: id, fields: { type: 'array', items: { type: 'string' }, maxItems: 50 } }, ['investigation_id'], 'profile'],
  ['peek_ndjson', 'Return at most 20 redacted NDJSON rows matching an event value or required fields.', { investigation_id: id, event_values: { type: 'array', items: { type: 'string' }, maxItems: 20 }, contains_fields: { type: 'array', items: { type: 'string' }, maxItems: 20 }, limit: { type: 'integer', minimum: 1, maximum: 20 } }, ['investigation_id'], 'peek'],
  ['ingest_ndjson', 'Stream the complete source blob directly into an already-created default-schema table as JSONEachRow and return reconciliation counts.', { investigation_id: id, table: { type: 'string', pattern: '^default\\.[a-z][a-z0-9_]{0,62}$' } }, ['investigation_id', 'table'], 'ingest'],
  ['persist_investigation_state', 'Persist the final compact instrumentation artifact in the investigation state table before handoff.', { investigation_id: id, artifact: { type: 'object' } }, ['investigation_id', 'artifact'], 'state'],
  ['publish_finalizer_response', 'Publish the canonical Finalizer response envelope for rendering in the Input Page.', { investigation_id: id, envelope: { type: 'object' } }, ['investigation_id', 'envelope'], 'finalizer'],
];
const server = new Server({ name: 'atlys-investigation-data', version: '1.0.0' }, { capabilities: { tools: {} } });
server.setRequestHandler(ListToolsRequestSchema, async () => ({ tools: tools.map(([name, description, properties, required]) => ({ name, description, inputSchema: { type: 'object', properties, required, additionalProperties: false } })) }));
server.setRequestHandler(CallToolRequestSchema, async ({ params }) => {
  const tool = tools.find(([name]) => name === params.name);
  if (!tool) return { isError: true, content: [{ type: 'text', text: 'Unknown investigation data tool' }] };
  try {
    const [, , , , action] = tool;
    const { investigation_id, ...body } = params.arguments;
    return { content: [{ type: 'text', text: await request(investigation_id, action, body) }] };
  } catch (error) { return { isError: true, content: [{ type: 'text', text: error.message }] }; }
});
server.connect(new StdioServerTransport());
