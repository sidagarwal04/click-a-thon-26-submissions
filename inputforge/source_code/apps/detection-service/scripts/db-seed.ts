// Loads db/seed.sql into local Postgres. Usage: npm run db:seed
import { readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { getPool } from "../lib/registry/db.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

async function main() {
  const pool = getPool();
  const sql = await readFile(path.join(__dirname, "..", "db", "seed.sql"), "utf8");
  await pool.query(sql);
  console.log("seeded");
  await pool.end();
}

main();
