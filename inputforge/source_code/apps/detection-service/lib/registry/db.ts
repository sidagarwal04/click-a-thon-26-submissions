import { Pool } from "pg";

let pool: Pool | undefined;

/** Control-plane Postgres — local via docker-compose.yml for now
 * (DATABASE_URL defaults to that), a real managed instance (Vercel
 * Marketplace / Neon) later. Separate from ClickHouse, which stays the
 * analytical data-plane engine — see README's registry section. */
export function getPool(): Pool {
  if (pool) return pool;
  const connectionString =
    process.env.DATABASE_URL ?? "postgres://detection:detection@localhost:55432/detection_registry";
  pool = new Pool({ connectionString });
  return pool;
}
