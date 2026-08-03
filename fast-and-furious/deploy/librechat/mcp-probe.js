// Probe the MCP server the way LibreChat will: from inside the api container, over the
// Docker bridge, with the bearer token.
//
// Run as:  sudo docker compose exec -T api node < mcp-probe.js
//
// Piped into `node` on stdin rather than passed with `-e`, because this ends up nested
// inside an ssh command string and a heredoc, and every layer of that would need its own
// round of quoting. stdin has no quoting.
//
// Node rather than curl: neither the LibreChat image nor the LiteLLM image ships curl.
// Node 18+ has global fetch, and this image is on 24.
//
// Exits 0 only if the server answers AND its answer carries the operating rules, which is
// what proves `serverInstructions: true` will have something to inject. A 200 with an
// empty capability set would otherwise read as success.

const url = process.env.MCP_URL || 'http://host.docker.internal:8848/mcp';
const token = process.env.SONYLIV_MCP_TOKEN || '';

const body = {
  jsonrpc: '2.0',
  id: 1,
  method: 'initialize',
  params: {
    protocolVersion: '2024-11-05',
    capabilities: {},
    clientInfo: { name: 'deploy-check', version: '1' },
  },
};

const fail = (msg) => {
  console.error(`  ${msg}`);
  process.exit(1);
};

const timeout = AbortSignal.timeout(15000);

fetch(url, {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    Accept: 'application/json, text/event-stream',
    Authorization: `Bearer ${token}`,
  },
  body: JSON.stringify(body),
  signal: timeout,
})
  .then(async (r) => {
    const text = await r.text();
    if (r.status === 401) {
      fail('401 — SONYLIV_MCP_TOKEN differs between mcp.env and librechat.env');
    }
    if (!r.ok) fail(`HTTP ${r.status}: ${text.slice(0, 200)}`);

    let parsed;
    try {
      parsed = JSON.parse(text);
    } catch {
      fail(`not JSON: ${text.slice(0, 200)}`);
    }
    const instructions = parsed?.result?.instructions ?? '';
    if (!instructions.includes('NEVER SUM OR AVERAGE A PEAK')) {
      fail(`answered, but returned no operating rules: ${text.slice(0, 200)}`);
    }
    const name = parsed?.result?.serverInfo?.name ?? '?';
    console.log(`  ok  ${name} reachable, returning its operating rules`);
  })
  .catch((e) => fail(`unreachable: ${e.message}`));
