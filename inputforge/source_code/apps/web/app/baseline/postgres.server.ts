import "server-only";

import { Pool } from "pg";

const globalForPostgres = globalThis as typeof globalThis & {
  baselinePostgresPool?: Pool;
};

export function getPostgresPool(): Pool {
  if (globalForPostgres.baselinePostgresPool) {
    return globalForPostgres.baselinePostgresPool;
  }
  const connectionString =
    process.env.DATABASE_URL ??
    "postgres://detection:detection@localhost:55432/detection_registry";
  const pool = new Pool({
    connectionString,
    max: 5,
    connectionTimeoutMillis: 1_500,
  });
  globalForPostgres.baselinePostgresPool = pool;
  return pool;
}
