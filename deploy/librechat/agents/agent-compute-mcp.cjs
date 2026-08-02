#!/usr/bin/env node
/* Sandboxed small-computation tool for agent-local JSON assembly. */
const vm = require('vm');
const { Server } = require('@modelcontextprotocol/sdk/server/index.js');
const { StdioServerTransport } = require('@modelcontextprotocol/sdk/server/stdio.js');
const { CallToolRequestSchema, ListToolsRequestSchema } = require('@modelcontextprotocol/sdk/types.js');
const server = new Server({ name: 'atlys-agent-compute', version: '1.0.0' }, { capabilities: { tools: {} } });
server.setRequestHandler(ListToolsRequestSchema, async () => ({ tools: [{
  name: 'execute_javascript', description: 'Run a short deterministic JavaScript computation over JSON input. Use it to assemble/validate final JSON and small calculations; no filesystem, network, process, or credentials are available.',
  inputSchema: { type: 'object', properties: { code: { type: 'string', maxLength: 8000 }, input: {} }, required: ['code', 'input'], additionalProperties: false },
}] }));
server.setRequestHandler(CallToolRequestSchema, async ({ params }) => {
  try {
    const { code, input } = params.arguments;
    if (typeof code !== 'string' || code.length > 8000) throw new Error('Code must be at most 8000 characters');
    const sandbox = { input: JSON.parse(JSON.stringify(input)), JSON, Math, Object, Array, String, Number, Boolean };
    const value = new vm.Script(`"use strict"; (${code})`).runInNewContext(sandbox, { timeout: 1000 });
    const text = JSON.stringify(value);
    if (text.length > 100000) throw new Error('Computation result exceeds 100 KiB');
    return { content: [{ type: 'text', text }] };
  } catch (error) { return { isError: true, content: [{ type: 'text', text: error.message }] }; }
});
server.connect(new StdioServerTransport());
