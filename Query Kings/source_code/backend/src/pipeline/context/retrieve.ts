import { ContextBundle, RelevantContextBundle } from "./types.js";
import { lexicalOverlap, tokenize } from "./utils.js";

export function retrieveRelevantContextForSpec(input: {
  context: ContextBundle;
  featureSlug: string;
  workflowType: string;
  primaryEntity: string;
  eventNames: string[];
  fieldPaths: string[];
  metricHints: string[];
}): RelevantContextBundle {
  const registry = input.context.generatedContext;
  const queryTerms = new Set(
    [
      input.featureSlug,
      input.workflowType,
      input.primaryEntity,
      ...input.eventNames,
      ...input.fieldPaths,
      ...input.metricHints,
    ]
      .flatMap(tokenize)
      .filter(Boolean),
  );

  const scoreText = (...values: Array<string | null | undefined>) =>
    values
      .flatMap((value) => tokenize(value ?? ""))
      .reduce((score, token) => score + (queryTerms.has(token) ? 1 : 0), 0);

  const similarWorkflows = registry.workflows
    .map((workflow) => ({
      item: workflow,
      score:
        scoreText(
          workflow.feature_slug,
          workflow.workflow_type,
          workflow.primary_entity,
          workflow.primary_entity_column,
          workflow.start_event,
          workflow.success_event,
          workflow.segment_columns.join(" "),
        ) + (workflow.workflow_type === input.workflowType ? 4 : 0),
    }))
    .filter((scored) => scored.score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, 8)
    .map((scored) => scored.item);

  const fieldColumnNames = new Set(
    input.fieldPaths.map((field) => field.split(".").at(-1) ?? field),
  );
  const columnPrecedents = registry.columns
    .map((column) => ({
      item: column,
      score:
        scoreText(
          column.table_name,
          column.column_name,
          column.source_path,
          column.semantic_role,
        ) +
        (fieldColumnNames.has(column.column_name) ? 5 : 0) +
        (input.fieldPaths.includes(column.source_path ?? "") ? 6 : 0),
    }))
    .filter((scored) => scored.score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, 60)
    .map((scored) => scored.item);

  const reusableMetrics = registry.metrics
    .map((metric) => ({
      item: metric,
      score:
        scoreText(
          metric.feature_slug,
          metric.metric_name,
          metric.formula_sql,
          metric.grain,
          metric.segment_columns.join(" "),
        ) +
        input.metricHints.reduce(
          (score, hint) => score + lexicalOverlap(hint, metric.metric_name),
          0,
        ),
    }))
    .filter((scored) => scored.score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, 20)
    .map((scored) => scored.item);

  const recommendedJoins = registry.joins
    .filter(
      (join) =>
        input.fieldPaths.includes(join.left_column) ||
        input.fieldPaths.includes(join.right_column) ||
        fieldColumnNames.has(join.left_column) ||
        fieldColumnNames.has(join.right_column),
    )
    .sort((a, b) => b.confidence - a.confidence)
    .slice(0, 20);

  const tableNames = new Set([
    ...similarWorkflows.map((workflow) => workflow.table_name),
    ...columnPrecedents.map((column) => column.table_name),
  ]);
  const schemaQuality = registry.schema_quality
    .filter((quality) => tableNames.has(quality.table_name))
    .slice(0, 20);

  return {
    similar_workflows: similarWorkflows,
    column_type_precedents: columnPrecedents,
    reusable_metrics: reusableMetrics,
    recommended_joins: recommendedJoins,
    schema_quality: schemaQuality,
    contradictions: registry.contradictions,
    retrieval_notes: [
      `Retrieved ${similarWorkflows.length} workflows, ${columnPrecedents.length} column precedents, ${reusableMetrics.length} metrics, and ${recommendedJoins.length} joins.`,
      "Use retrieved context as evidence, not truth; raw event profile remains source of truth.",
    ],
  };
}
