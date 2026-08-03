import assert from "node:assert/strict";
import test from "node:test";

async function render() {
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set("test", `${process.pid}-${Date.now()}`);
  const { default: worker } = await import(workerUrl.href);
  return worker.fetch(new Request("http://localhost/", { headers: { accept: "text/html" } }), { ASSETS: { fetch: async () => new Response("Not found", { status: 404 }) } }, { waitUntil() {}, passThroughOnException() {} });
}

test("renders the FeatureLens product intelligence demo", async () => {
  const response = await render();
  assert.equal(response.status, 200);
  const html = await response.text();
  const bodyStart = html.indexOf("<body");
  const visibleHtml = html.slice(bodyStart, html.indexOf("</body>", bodyStart));
  assert.match(html, /<title>FeatureLens/);
  assert.match(html, /Ask FeatureLens/);
  assert.match(html, /Decision inbox/);
  assert.match(html, /Feature releases/);
  assert.match(html, /Add feature/);
  assert.match(html, /Reset baseline/);
  assert.match(html, /Pipeline activity/);
  assert.match(html, /Context &amp; schemas/);
  assert.match(html, /Trace explorer/);
  assert.match(html, /How can I help/);
  assert.match(html, /Which cities and devices show the strongest Express Checkout completion/);
  assert.match(html, /Ask about a feature, segment, trend, or opportunity/);
  assert.match(html, /Open Power Chat/);
  assert.doesNotMatch(visibleHtml, /From feature release|Three coordinated agents|Explore intelligence for every product release|One run\. Governed handoffs|Meet the specialists behind every answer|User input → context → query → model → answer/);
  assert.doesNotMatch(html, /Evolution quality|Quality gates|Known features train the loop/);
  assert.doesNotMatch(html, /codex-preview|react-loading-skeleton/);
});
