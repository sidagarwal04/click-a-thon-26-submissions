import { startActiveObservation } from "@langfuse/tracing";
import { ContextBundle } from "../context.js";
import {
  BASE_EVENT_TABLES,
  BASE_FUNNEL_TABLES,
  bareTableName,
  qualifyFeatureTable,
} from "../warehouseTables.js";
import { writeStageJson } from "../instrumentation/artifacts.js";
import { recordPipelineStage } from "../tracking.js";
import { analyticsTrackingEvents } from "./trackingEvents.js";
import { PmRelevantContext, QueryIntent } from "./types.js";
import { normalizeTokens, scoreAgainstTerms, unique } from "./utils.js";

export async function retrievePmContext(input: {
  jobId: string;
  question: string;
  intent: QueryIntent;
  context: ContextBundle;
  artifactRoot: string;
}): Promise<PmRelevantContext> {
  const event = analyticsTrackingEvents.contextRetrieval;
  return startActiveObservation(event.stageId, async (span) => {
    const terms = buildTerms(input.question, input.intent);
    const registry = input.context.generatedContext;
    const wantsBaseline = wantsBaselineFunnel(input.question, input.intent);
    const retrievalNotes: string[] = [];

    // Feature retrieval with alias expansion so "express checkout" hits express_checkout.
    const features = registry.features
      .map((feature) => ({
        item: {
          ...feature,
          table_name: qualifyFeatureTable(feature.table_name),
        },
        score:
          scoreAgainstTerms(
            terms,
            feature.feature_slug,
            feature.table_name,
            feature.primary_entity,
            feature.event_names,
            feature.metric_hints,
            feature.feature_slug.replace(/_/g, " "),
            ...expandAliases(feature.feature_slug),
          ) +
          // Soft match: any feature hint token contained in slug
          (input.intent.feature_hints.some((hint) =>
            feature.feature_slug.includes(
              hint.toLowerCase().replace(/[^a-z0-9]+/g, "_"),
            ),
          )
            ? 6
            : 0),
      }))
      .filter((scored) => scored.score > 0)
      .sort((a, b) => b.score - a.score)
      .slice(0, 8)
      .map((scored) => scored.item);

    // Strict: do NOT fall back to unrelated features when the named feature misses.
    // Returning wrong feature metrics is worse than saying "not instrumented".
    let resolvedFeatures = features;
    const namedButMissing =
      resolvedFeatures.length === 0 &&
      (input.intent.feature_hints.length > 0 ||
        /\b(feature|concierge|module)\b/i.test(input.question)) &&
      !/\b(express|checkout|group|family|status|abandon|forex|fx|recovery|sharing)\b/i.test(
        input.question,
      );

    if (namedButMissing) {
      retrievalNotes.push(
        `WARNING: no generated feature matched this question. Will not attribute other feature metrics to an unknown feature. Known features: ${registry.features.map((feature) => feature.feature_slug).join(", ") || "(none)"}.`,
      );
    } else if (
      resolvedFeatures.length === 0 &&
      input.intent.feature_hints.length > 0
    ) {
      retrievalNotes.push(
        `WARNING: context memory has no generated features matching ${JSON.stringify(input.intent.feature_hints)}. Run instrumentation on the feature first, or analytics will be limited to base funnel tables.`,
      );
    }

    if (registry.features.length === 0) {
      retrievalNotes.push(
        "WARNING: context.feature_registry is empty. Silver feature tables may not be registered — run `pnpm cli run <spec>` before feature-specific asks.",
      );
    }

    const featureSlugs = new Set(
      resolvedFeatures.map((feature) => feature.feature_slug),
    );
    const tableNames = new Set(
      resolvedFeatures.map((feature) => feature.table_name),
    );

    // Always include base funnel tables when the question needs baseline/uplift
    // or when no feature tables matched.
    if (wantsBaseline || resolvedFeatures.length === 0) {
      for (const table of BASE_FUNNEL_TABLES) {
        tableNames.add(table);
      }
      if (wantsBaseline) {
        for (const table of BASE_EVENT_TABLES) {
          tableNames.add(table);
        }
      }
      retrievalNotes.push(
        wantsBaseline
          ? "Included base conversion funnel tables for baseline / uplift comparison."
          : "Included base conversion funnel tables because no feature table matched.",
      );
    }

    const workflows = registry.workflows
      .map((workflow) => ({
        item: {
          ...workflow,
          table_name: normalizeTable(workflow.table_name),
        },
        score:
          scoreAgainstTerms(
            terms,
            workflow.feature_slug,
            workflow.table_name,
            workflow.workflow_type,
            workflow.primary_entity,
            workflow.segment_columns,
            workflow.start_event,
            workflow.success_event,
          ) +
          (featureSlugs.has(workflow.feature_slug) ? 5 : 0) +
          (tableNames.has(workflow.table_name) ||
          tableNames.has(qualifyFeatureTable(workflow.table_name))
            ? 5
            : 0) +
          (workflow.feature_slug === "base_conversion_funnel" && wantsBaseline
            ? 8
            : 0),
      }))
      .filter((scored) => scored.score > 0)
      .sort((a, b) => b.score - a.score)
      .slice(0, 12)
      .map((scored) => scored.item);

    for (const workflow of workflows) {
      if (!workflow.table_name.includes("|")) {
        tableNames.add(workflow.table_name);
      } else {
        for (const part of workflow.table_name.split("|")) {
          tableNames.add(part);
        }
      }
    }

    const columns = registry.columns
      .map((column) => ({
        item: {
          ...column,
          table_name: normalizeTable(column.table_name),
        },
        score:
          scoreAgainstTerms(
            terms,
            column.table_name,
            column.column_name,
            column.semantic_role,
            column.source_path,
          ) +
          (tableNames.has(column.table_name) ||
          tableNames.has(qualifyFeatureTable(column.table_name)) ||
          tableNames.has(bareTableName(column.table_name))
            ? 4
            : 0),
      }))
      .filter((scored) => scored.score > 0)
      .sort((a, b) => b.score - a.score)
      .slice(0, 160)
      .map((scored) => scored.item);

    // Ensure every selected feature/base table contributes its columns even if
    // keyword score was zero (critical for SQL grounding).
    const selectedBare = new Set(
      Array.from(tableNames).map((table) => bareTableName(table)),
    );
    for (const column of registry.columns) {
      const bare = bareTableName(column.table_name);
      if (!selectedBare.has(bare)) {
        continue;
      }
      if (
        columns.some(
          (existing) =>
            bareTableName(existing.table_name) === bare &&
            existing.column_name === column.column_name,
        )
      ) {
        continue;
      }
      columns.push({
        ...column,
        table_name: normalizeTable(column.table_name),
      });
    }

    for (const column of columns.slice(0, 80)) {
      tableNames.add(column.table_name);
    }

    const metrics = registry.metrics
      .map((metric) => ({
        item: metric,
        score:
          scoreAgainstTerms(
            terms,
            metric.feature_slug,
            metric.metric_name,
            metric.formula_sql,
            metric.grain,
            metric.segment_columns,
          ) +
          (featureSlugs.has(metric.feature_slug) ? 4 : 0) +
          (metric.feature_slug === "base_conversion_funnel" && wantsBaseline
            ? 6
            : 0),
      }))
      .filter((scored) => scored.score > 0)
      .sort((a, b) => b.score - a.score)
      .slice(0, 40)
      .map((scored) => scored.item);

    const joins = registry.joins
      .filter(
        (join) =>
          tableNames.has(join.left_table) ||
          tableNames.has(join.right_table) ||
          tableNames.has(qualifyFeatureTable(join.left_table)) ||
          tableNames.has(qualifyFeatureTable(join.right_table)) ||
          tableNames.has(bareTableName(join.left_table)) ||
          tableNames.has(bareTableName(join.right_table)) ||
          terms.has(join.left_column) ||
          terms.has(join.right_column),
      )
      .sort((a, b) => b.confidence - a.confidence)
      .slice(0, 60);

    const schemaQuality = registry.schema_quality
      .filter(
        (quality) =>
          tableNames.has(quality.table_name) ||
          tableNames.has(qualifyFeatureTable(quality.table_name)),
      )
      .slice(0, 40);

    // Surface known-issue contradictions first for PM narrative linking.
    const contradictions = [...registry.contradictions].sort((a, b) => {
      const aScore = scoreAgainstTerms(terms, a.id, a.summary, a.evidence);
      const bScore = scoreAgainstTerms(terms, b.id, b.summary, b.evidence);
      return bScore - aScore;
    });

    retrievalNotes.unshift(
      `Retrieved ${resolvedFeatures.length} features, ${workflows.length} workflows, ${columns.length} columns, ${metrics.length} metrics, ${joins.length} joins, ${contradictions.length} contradictions/known-issue links.`,
    );
    retrievalNotes.push(
      "Context is useful memory, not absolute truth. Prefer event evidence from ClickHouse query results.",
    );

    const relevant: PmRelevantContext = {
      features: resolvedFeatures,
      workflows,
      columns,
      metrics,
      joins,
      schema_quality: schemaQuality,
      contradictions,
      base_context_excerpt: input.context.baseContext.slice(0, 5000),
      retrieval_notes: retrievalNotes,
    };

    await writeStageJson(
      input.artifactRoot,
      event.stageId,
      "pm_context.json",
      relevant,
    );
    await recordPipelineStage({
      jobId: input.jobId,
      stageId: event.stageId,
      stageName: event.stageName,
      status: "completed",
      stageInput: {
        question: input.question,
        intent: input.intent,
      },
      stageOutput: {
        features: relevant.features.length,
        workflows: relevant.workflows.length,
        columns: relevant.columns.length,
        metrics: relevant.metrics.length,
        joins: relevant.joins.length,
        tables: Array.from(tableNames),
        retrieval_notes: retrievalNotes,
      },
    });
    span.update({ output: relevant });
    return relevant;
  });
}

function buildTerms(question: string, intent: QueryIntent) {
  return new Set(
    unique([
      ...normalizeTokens(question),
      ...intent.feature_hints.flatMap((hint) =>
        Array.from(normalizeTokens(hint)),
      ),
      ...intent.metric_hints.flatMap((hint) =>
        Array.from(normalizeTokens(hint)),
      ),
      ...intent.table_hints.flatMap((hint) =>
        Array.from(normalizeTokens(hint)),
      ),
      ...intent.segment_hints.flatMap((hint) =>
        Array.from(normalizeTokens(hint)),
      ),
      // Alias expansions for common product language
      ...intent.feature_hints.flatMap((hint) => expandAliases(hint)),
      ...Array.from(normalizeTokens(question)).flatMap((token) =>
        expandAliases(token),
      ),
    ]),
  );
}

function expandAliases(value: string): string[] {
  const slug = value.toLowerCase().replace(/[^a-z0-9]+/g, "_");
  const aliases = [slug, slug.replace(/_/g, "")];
  if (slug.includes("express")) {
    aliases.push("express_checkout", "express_checkout_events", "checkout");
  }
  if (slug.includes("group") || slug.includes("family")) {
    aliases.push("group_family", "group_family_events");
  }
  if (slug.includes("status") || slug.includes("sharing")) {
    aliases.push("status_sharing", "status_sharing_events");
  }
  if (slug.includes("abandon") || slug.includes("recovery")) {
    aliases.push(
      "abandoned_checkout_recovery",
      "abandoned_checkout_recovery_events",
    );
  }
  if (
    slug.includes("forex") ||
    slug.includes("fx") ||
    slug.includes("instant")
  ) {
    aliases.push("instant_forex", "instant_forex_events");
  }
  if (
    slug.includes("conversion") ||
    slug.includes("funnel") ||
    slug.includes("baseline") ||
    slug.includes("uplift")
  ) {
    aliases.push(...BASE_FUNNEL_TABLES);
  }
  return aliases;
}

function wantsBaselineFunnel(question: string, intent: QueryIntent) {
  const text = `${question} ${intent.metric_hints.join(" ")} ${intent.requested_analyses.join(" ")}`;
  return /baseline|uplift|overall|conversion|funnel|compare|vs|versus|drop|worse|better|root.?cause|iOS|android|segment|purchase|checkout performance/i.test(
    text,
  );
}

function normalizeTable(tableName: string) {
  if (!tableName || tableName.includes("|") || tableName.includes("*")) {
    return tableName;
  }
  return qualifyFeatureTable(tableName);
}
