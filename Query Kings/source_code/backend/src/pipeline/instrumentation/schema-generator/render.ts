import { MappingPlan, SchemaPlan } from "../types.js";

export function renderCreateTableSql(plan: SchemaPlan): string {
  const columns = plan.columns
    .map((column) => `    ${column.name} ${column.type}`)
    .join(",\n");

  return `CREATE TABLE IF NOT EXISTS ${plan.database}.${plan.table_name}
(
${columns}
)
ENGINE = ${plan.engine}
PARTITION BY ${plan.partition_by}
ORDER BY (${plan.order_by.join(", ")})
TTL ${plan.ttl};
`;
}

export function renderMaterializedViewsSql(plan: SchemaPlan): string {
  if (plan.materialized_views.length === 0) {
    return "-- No materialized views were required for this feature schema.\n";
  }

  return `${plan.materialized_views
    .map((view) => `${view.target_table_sql}\n\n${view.view_sql}`)
    .join("\n\n")}\n`;
}

export function buildMappingPlan(plan: SchemaPlan): MappingPlan {
  return {
    table_name: `${plan.database}.${plan.table_name}`,
    mappings: plan.columns.map((column) => ({
      column: column.name,
      source_path: column.source_path,
      transform:
        column.name === "job_id"
          ? "set from pipeline job_id"
          : column.name === "raw_json"
            ? "serialize original event JSON"
            : column.name === "timestamp"
              ? "parse ISO timestamp to DateTime64(3)"
              : column.name === "ingested_at"
                ? "ClickHouse DEFAULT now()"
                : "copy from raw JSON path with nullable cast",
    })),
  };
}
