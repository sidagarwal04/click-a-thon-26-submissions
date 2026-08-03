import { getClickHouseConfig, queryClickHouseText } from "../clickhouse.js";
import {
  BASE_EVENT_TABLES,
  bareTableName,
  qualifyFeatureTable,
} from "../warehouseTables.js";

export function unique<T>(values: T[]): T[] {
  return Array.from(new Set(values));
}

export function normalizeTokens(value: string): Set<string> {
  return new Set(
    value
      .toLowerCase()
      .split(/[^a-z0-9_]+/)
      .filter((token) => token.length > 1),
  );
}

export function scoreAgainstTerms(
  terms: Set<string>,
  ...values: Array<string | string[] | null | undefined>
) {
  return values
    .flatMap((value) => {
      if (Array.isArray(value)) {
        return value;
      }
      return [value ?? ""];
    })
    .flatMap((value) => Array.from(normalizeTokens(value)))
    .reduce((score, token) => score + (terms.has(token) ? 1 : 0), 0);
}

export function compactJson(value: unknown, maxLength = 12000) {
  const json = JSON.stringify(value, null, 2);
  return json.length > maxLength
    ? `${json.slice(0, maxLength)}\n...truncated...`
    : json;
}

/**
 * Tables analytics may query:
 * - silver / gold generated feature tables
 * - context memory tables
 * - the 8 base Atlys event tables in the app database
 */
export async function getKnownClickHouseTables(): Promise<string[]> {
  const appDb = getClickHouseConfig().database;
  const raw = await queryClickHouseText(`
SELECT concat(database, '.', name) AS table_name
FROM system.tables
WHERE (
  database IN ('silver', 'gold', 'context')
  OR (
    database = ${sqlLiteral(appDb)}
    AND name IN (${BASE_EVENT_TABLES.map((table) => sqlLiteral(table)).join(", ")})
  )
)
ORDER BY database, name
FORMAT TabSeparated
`);

  const fromSystem = raw.trim() ? raw.trim().split("\n") : [];
  // Always include bare base table names — SQL often omits the app database prefix
  // because X-ClickHouse-Database is set on the client.
  const known = new Set<string>([
    ...fromSystem,
    ...BASE_EVENT_TABLES,
    ...BASE_EVENT_TABLES.map((table) => `${appDb}.${table}`),
  ]);

  return Array.from(known).sort();
}

export async function getClickHouseColumns(
  tables: string[],
): Promise<Array<{ table_name: string; column_name: string; type: string }>> {
  if (tables.length === 0) {
    return [];
  }
  const appDb = getClickHouseConfig().database;
  const bareNames = unique(
    tables.map((table) => bareTableName(table)).filter(Boolean),
  );
  if (bareNames.length === 0) {
    return [];
  }

  const raw = await queryClickHouseText(`
SELECT concat(database, '.', table) AS table_name, name AS column_name, type
FROM system.columns
WHERE (
  database IN ('silver', 'gold', 'context')
  OR database = ${sqlLiteral(appDb)}
)
  AND table IN (${bareNames.map((name) => sqlLiteral(name)).join(", ")})
ORDER BY database, table, position
FORMAT TabSeparated
`);
  return raw.trim()
    ? raw
        .trim()
        .split("\n")
        .map((line) => {
          const [table_name, column_name, type] = line.split("\t");
          return { table_name, column_name, type };
        })
    : [];
}

export function stripSqlFormatting(sql: string) {
  return sql
    .replace(/```sql/gi, "")
    .replace(/```/g, "")
    .trim()
    .replace(/;+\s*$/g, "");
}

/** Build the allowlist aliases a SQL string may use for a known table. */
export function tableAliases(tableName: string): string[] {
  const bare = bareTableName(tableName);
  const qualified = qualifyFeatureTable(tableName);
  const appDb = getClickHouseConfig().database;
  return unique(
    [tableName, bare, qualified, `${appDb}.${bare}`, `silver.${bare}`].filter(
      Boolean,
    ),
  );
}

/**
 * True if SQL references any known table (qualified or bare).
 * Handles silver.foo, schema_kings.bar, and bare base table names.
 */
export function sqlReferencesKnownTable(
  sql: string,
  knownTables: Iterable<string>,
): boolean {
  const normalized = sql.toLowerCase();
  for (const table of knownTables) {
    for (const alias of tableAliases(table)) {
      const pattern = new RegExp(
        `(^|[^a-z0-9_])${escapeRegExp(alias.toLowerCase())}([^a-z0-9_]|$)`,
      );
      if (pattern.test(normalized)) {
        return true;
      }
    }
  }
  return false;
}

/**
 * Rewrite common invented table names using the grounded catalog from context.
 * Maps express_checkout_logs / express_checkout → silver.express_checkout_events, etc.
 */
export function groundSqlTableNames(
  sql: string,
  catalogTables: string[],
): string {
  let grounded = sql;
  const catalog = catalogTables
    .map((table) => qualifyFeatureTable(table))
    .filter(Boolean);

  for (const table of catalog) {
    const bare = bareTableName(table);
    if (!bare || bare.includes("*") || bare.includes("|")) {
      continue;
    }
    const stem = bare.replace(/_events$/, "");
    const invented = unique([
      `${stem}_logs`,
      `${stem}_log`,
      `${stem}_sessions`,
      `${stem}_session`,
      stem,
      bare,
    ]).filter((name) => name !== table && name.length > 2);

    for (const bad of invented) {
      // Only replace identifier-like occurrences, not substrings inside longer names.
      const pattern = new RegExp(
        `(^|[^a-zA-Z0-9_.])${escapeRegExp(bad)}(?=[^a-zA-Z0-9_]|$)`,
        "gi",
      );
      grounded = grounded.replace(pattern, `$1${table}`);
    }
  }

  // Prefer fully-qualified silver.* for bare generated feature tables.
  for (const table of catalog) {
    if (!table.startsWith("silver.")) {
      continue;
    }
    const bare = bareTableName(table);
    const pattern = new RegExp(
      `(^|[^a-zA-Z0-9_.])${escapeRegExp(bare)}(?=[^a-zA-Z0-9_]|$)`,
      "g",
    );
    grounded = grounded.replace(pattern, `$1${table}`);
  }

  return grounded;
}

export function qualifyAnalyticsTable(tableName: string): string {
  return qualifyFeatureTable(tableName);
}

function sqlLiteral(value: string) {
  return `'${value.replace(/\\/g, "\\\\").replace(/'/g, "\\'")}'`;
}

function escapeRegExp(value: string) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}
