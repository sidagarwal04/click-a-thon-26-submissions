// Tiny proxy: browser -> this server -> ClickHouse. Keeps creds server-side and
// enforces read-only SELECT/WITH. Also serves the built UI (dist) in production.
import express from "express";
import path from "path";
import { fileURLToPath } from "url";

const app = express();
app.use(express.json({ limit: "1mb" }));

const CH_URL = process.env.CH_URL;
const AUTH = "Basic " + Buffer.from(`${process.env.CH_USER}:${process.env.CH_PASSWORD}`).toString("base64");
const BLOCK = /\b(insert|alter|drop|truncate|create|delete|update|system|attach|detach|rename|optimize|grant|revoke|set)\b/i;
// Tags every query this proxy runs, so they're greppable in system.query_log / HyperDX:
//   log_comment = 'sonyliv-dashboard'  (or 'sonyliv-dashboard:curve' when the client sends a tag)
const LOG_COMMENT = process.env.LOG_COMMENT || "sonyliv-dashboard";

app.post("/api/query", async (req, res) => {
  const sql = String(req.body?.sql || "");
  if (!/^\s*(select|with)\b/i.test(sql) || BLOCK.test(sql))
    return res.status(400).json({ error: "read-only SELECT/WITH queries only" });
  try {
    const tag = String(req.body?.tag || "").replace(/[^\w:-]/g, "").slice(0, 40);
    const url = new URL(CH_URL);
    url.searchParams.set("log_comment", tag ? `${LOG_COMMENT}:${tag}` : LOG_COMMENT);
    const r = await fetch(url, {
      method: "POST",
      headers: { Authorization: AUTH, "Content-Type": "text/plain" },
      body: sql + "\nFORMAT JSON",
    });
    const text = await r.text();
    if (!r.ok) return res.status(502).json({ error: text.slice(0, 800) });
    res.type("application/json").send(text);
  } catch (e) {
    res.status(500).json({ error: String(e) });
  }
});

const dist = path.join(path.dirname(fileURLToPath(import.meta.url)), "dist");
app.use(express.static(dist));
app.get("*", (_req, res) => res.sendFile(path.join(dist, "index.html")));

const port = process.env.PORT || 8787;
app.listen(port, () => console.log(`clickhouse proxy + UI on :${port}`));
