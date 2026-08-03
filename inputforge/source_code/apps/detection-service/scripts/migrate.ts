// Runs db/migrations/*.sql against local Postgres, in filename order.
// Usage: npm run db:migrate
import { readFile, readdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { getPool } from "../lib/registry/db.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const MIGRATIONS_DIR = path.join(__dirname, "..", "db", "migrations");

async function main() {
  const pool = getPool();
  const files = (await readdir(MIGRATIONS_DIR)).filter((f) => f.endsWith(".sql")).sort();
  for (const f of files) {
    const sql = await readFile(path.join(MIGRATIONS_DIR, f), "utf8");
    await pool.query(sql);
    console.log(`applied ${f}`);
  }
  await pool.end();
}

main();
