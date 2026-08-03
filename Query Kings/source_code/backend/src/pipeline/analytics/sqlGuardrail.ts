import { startActiveObservation } from "@langfuse/tracing";
import { writeStageJson } from "../instrumentation/artifacts.js";
import { recordPipelineStage } from "../tracking.js";
import { analyticsTrackingEvents } from "./trackingEvents.js";
import { GeneratedSqlQuery, SqlGuardrailResult } from "./types.js";
import {
  getClickHouseColumns,
  getKnownClickHouseTables,
  sqlReferencesKnownTable,
  stripSqlFormatting,
  tableAliases,
} from "./utils.js";

const FORBIDDEN_SQL =
  /\b(insert|update|delete|drop|alter|create|truncate|optimize|grant|revoke|attach|detach|rename)\b/i;

export async function runSqlGuardrail(input: {
  jobId: string;
  queries: GeneratedSqlQuery[];
  artifactRoot: string;
}): Promise<Array<GeneratedSqlQuery & { guardrail: SqlGuardrailResult }>> {
  const event = analyticsTrackingEvents.sqlGuardrail;
  return startActiveObservation(event.stageId, async (span) => {
    const knownTables = new Set(await getKnownClickHouseTables());
    const guarded = await Promise.all(
      input.queries.map(async (query) => {
        const repairedSql = repairSql(query.sql);
        const warnings = validateSql(repairedSql, knownTables);
        const referencedTables = Array.from(knownTables).filter((table) =>
          tableAliases(table).some((alias) =>
            new RegExp(
              `(^|[^a-zA-Z0-9_])${escapeRegExp(alias)}([^a-zA-Z0-9_]|$)`,
              "i",
            ).test(repairedSql),
          ),
        );
        const columns = await getClickHouseColumns(referencedTables);
        const missingColumnWarnings = findLikelyMissingColumns(
          repairedSql,
          columns,
          referencedTables,
        );
        return {
          ...query,
          sql: repairedSql,
          guardrail: {
            // Column warnings are soft — block only on hard SQL safety failures.
            passed: warnings.length === 0,
            repaired_sql: repairedSql,
            warnings: [...warnings, ...missingColumnWarnings],
          },
        };
      }),
    );

    await writeStageJson(
      input.artifactRoot,
      event.stageId,
      "sql_guardrail.json",
      {
        queries: guarded,
      },
    );
    await recordPipelineStage({
      jobId: input.jobId,
      stageId: event.stageId,
      stageName: event.stageName,
      status: guarded.every((query) => query.guardrail.passed)
        ? "completed"
        : "failed",
      stageInput: { query_count: input.queries.length },
      stageOutput: { queries: guarded },
    });
    span.update({ output: { queries: guarded } });
    return guarded;
  });
}

function repairSql(sql: string) {
  let repaired = stripSqlFormatting(sql);
  repaired = repaired.replace(/\bFORMAT\s+\w+\s*$/i, "").trim();
  // Cap huge raw dumps — analytics should aggregate, not pull 100k+ entity rows.
  const limitMatch = repaired.match(/\blimit\s+(\d+)\b/i);
  if (limitMatch && Number(limitMatch[1]) > 200) {
    repaired = repaired.replace(/\blimit\s+\d+\b/i, "LIMIT 100");
  }
  if (!/\blimit\b/i.test(repaired) && !/\bcount\s*\(/i.test(repaired)) {
    repaired = `${repaired}\nLIMIT 100`;
  }
  return repaired;
}

function validateSql(sql: string, knownTables: Set<string>) {
  const warnings: string[] = [];
  const normalized = sql.trim();
  if (!/^(\s*with|\s*select)\b/i.test(normalized)) {
    warnings.push("SQL must start with SELECT or WITH.");
  }
  if (FORBIDDEN_SQL.test(normalized)) {
    warnings.push(
      "SQL contains a forbidden mutating or administrative keyword.",
    );
  }
  // Block raw row dumps that are not aggregates (burns tokens + confuses insight).
  const hasAggregate =
    /\b(count|uniq|uniqExact|uniqExactIf|sum|avg|avgIf|quantile|min|max|group by)\b/i.test(
      normalized,
    );
  const selectsStar = /select\s+\*\s+from\b/i.test(normalized);
  const selectList =
    normalized.match(/select\s+([\s\S]+?)\s+from\b/i)?.[1] ?? "";
  const selectColumns = selectList
    .split(",")
    .map((part) => part.trim())
    .filter(Boolean);
  const looksLikeWideEntitySelect =
    !hasAggregate &&
    selectColumns.length >= 5 &&
    /\b(id|user_id|application_id|timestamp|device_type|raw_json|client_ip)\b/i.test(
      selectList,
    );
  const looksLikeRawEntityDump =
    !hasAggregate &&
    /\b(user_id|application_id|raw_json|client_ip|latitude|longitude)\b/i.test(
      normalized,
    ) &&
    /\bfrom\b/i.test(normalized);
  if (selectsStar || looksLikeRawEntityDump || looksLikeWideEntitySelect) {
    warnings.push(
      "Raw row dumps are blocked; use aggregated analytics SQL (count/uniq/group by).",
    );
  }
  if (/\bfrom\s+system\./i.test(normalized)) {
    return warnings;
  }
  if (
    /\bfrom\b/i.test(normalized) &&
    !sqlReferencesKnownTable(normalized, knownTables)
  ) {
    warnings.push(
      "SQL does not reference a known base funnel, silver, gold, or context table.",
    );
  }
  warnings.push(...findMalformedAggregateIfCalls(normalized));
  return warnings;
}

function findMalformedAggregateIfCalls(sql: string) {
  const warnings: string[] = [];
  for (const functionName of ["uniqIf", "uniqExactIf"]) {
    let searchFrom = 0;
    const pattern = new RegExp(`\\b${functionName}\\s*\\(`, "i");
    let match: RegExpExecArray | null;
    while ((match = pattern.exec(sql.slice(searchFrom)))) {
      const openParen = searchFrom + match.index + match[0].lastIndexOf("(");
      const args = extractCallArguments(sql, openParen);
      if (!args) {
        break;
      }
      if (splitTopLevelArgs(args).length < 2) {
        warnings.push(
          `${functionName} requires a value expression and a condition; use ${functionName}(entity_column, condition).`,
        );
      }
      searchFrom = openParen + args.length + 2;
    }
  }
  return warnings;
}

function extractCallArguments(sql: string, openParen: number) {
  let depth = 0;
  let inString = false;
  let escaping = false;
  for (let index = openParen; index < sql.length; index += 1) {
    const char = sql[index];
    if (escaping) {
      escaping = false;
      continue;
    }
    if (char === "\\") {
      escaping = true;
      continue;
    }
    if (char === "'") {
      inString = !inString;
      continue;
    }
    if (inString) {
      continue;
    }
    if (char === "(") {
      depth += 1;
      continue;
    }
    if (char === ")") {
      depth -= 1;
      if (depth === 0) {
        return sql.slice(openParen + 1, index);
      }
    }
  }
  return null;
}

function splitTopLevelArgs(args: string) {
  const parts: string[] = [];
  let depth = 0;
  let inString = false;
  let escaping = false;
  let start = 0;
  for (let index = 0; index < args.length; index += 1) {
    const char = args[index];
    if (escaping) {
      escaping = false;
      continue;
    }
    if (char === "\\") {
      escaping = true;
      continue;
    }
    if (char === "'") {
      inString = !inString;
      continue;
    }
    if (inString) {
      continue;
    }
    if (char === "(") {
      depth += 1;
      continue;
    }
    if (char === ")") {
      depth -= 1;
      continue;
    }
    if (char === "," && depth === 0) {
      parts.push(args.slice(start, index).trim());
      start = index + 1;
    }
  }
  parts.push(args.slice(start).trim());
  return parts.filter(Boolean);
}

function findLikelyMissingColumns(
  sql: string,
  columns: Array<{ table_name: string; column_name: string; type: string }>,
  referencedTables: string[],
) {
  if (referencedTables.length === 0 || columns.length === 0) {
    return [] as string[];
  }
  const knownColumns = new Set(
    columns.map((column) => column.column_name.toLowerCase()),
  );
  // Cheap heuristic: flag bare identifiers after AS? too noisy. Only check
  // common analytics columns that often get hallucinated.
  const candidates = [
    "express_flag",
    "session_id",
    "time_to_complete",
    "visa_issuance_eta_days",
  ];
  return candidates
    .filter((column) => {
      const pattern = new RegExp(`\\b${column}\\b`, "i");
      return pattern.test(sql) && !knownColumns.has(column.toLowerCase());
    })
    .map(
      (column) =>
        `Column '${column}' was not found on referenced tables; verify schema before trusting this query.`,
    );
}

function escapeRegExp(value: string) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}
