import { EvidencePack, InsightDraft, QueryResult } from "./types.js";

/**
 * Deterministic numbers-first scaffold from real ClickHouse result rows.
 * Used when LLM insight is weak/wrong, or for funnel/segment math that must stay honest.
 * Never invents numbers — only formats returned rows.
 */

const BASE_FUNNEL_ORDER = [
  "destination_card_clicked",
  "application_started",
  "document_uploaded",
  "purchase_completed",
] as const;

export function buildNumbersFirstDraft(
  evidencePack: EvidencePack,
): InsightDraft {
  const results = evidencePack.query_results.filter(
    (result) => result.row_count > 0,
  );

  // Missing / contradicted field questions (e.g. visa_issuance_eta_days).
  const missingField = detectMissingFieldAnswer(evidencePack);
  if (missingField) {
    return missingField;
  }

  const unknownFeature =
    evidencePack.plan.answer_type === "schema_explanation" &&
    (evidencePack.plan.assumptions.some((item) =>
      /not found in context memory|unknown feature|will not attribute/i.test(
        item,
      ),
    ) ||
      evidencePack.context.retrieval_notes.some((note) =>
        /no generated feature matched|will not attribute other feature/i.test(
          note,
        ),
      ));

  if (unknownFeature) {
    const known = uniqueStrings(
      results
        .flatMap((result) => result.rows)
        .map((row) =>
          row.feature_slug
            ? `${row.feature_slug} → ${row.table_name ?? ""}`
            : null,
        )
        .filter((value): value is string => Boolean(value)),
    );
    return {
      short_answer:
        "That feature does not appear to be instrumented in the current context memory, so I will not invent performance metrics for it.",
      key_findings: [
        "No matching generated feature table was found for the requested feature.",
        known.length > 0
          ? `Instrumented features available now: ${known.join("; ")}`
          : "No generated features were listed from context.feature_registry.",
      ],
      evidence: results.map((result) => ({
        claim: compactRowClaim(result),
        query_id: result.query_id,
        confidence: "high" as const,
      })),
      recommended_actions: [
        "Run instrumentation (`pnpm cli run <spec-folder>`) for this feature first.",
        "Re-ask after the feature appears in context.feature_registry.",
      ],
      caveats: [
        "Strict mode: refusing to attribute unrelated feature metrics to an unknown feature.",
        ...evidencePack.context.retrieval_notes.filter((note) =>
          note.startsWith("WARNING"),
        ),
      ],
    };
  }

  if (results.length === 0) {
    return {
      short_answer:
        "No non-empty ClickHouse results were available to answer this question.",
      key_findings: [],
      evidence: [],
      recommended_actions: [
        "Confirm the feature is instrumented and context memory is populated.",
        "Retry with a more specific feature or metric name.",
      ],
      caveats: [
        ...evidencePack.evaluation.evidence_gaps,
        ...evidencePack.evaluation.repair_notes,
        ...evidencePack.context.retrieval_notes.filter((note) =>
          note.startsWith("WARNING"),
        ),
      ],
    };
  }

  const catalogAnswer = detectContextCatalogAnswer(results);
  if (catalogAnswer) {
    return catalogAnswer;
  }

  const trusted = collectTrustedMetrics(results, {
    baselineRelevant: isBaselineRelevantQuestion(evidencePack.question),
  });
  const findings = [
    ...trusted.findings,
    ...results.flatMap((result) => summarizeResult(result)),
  ];
  const evidence = results.map((result) => ({
    claim: compactRowClaim(result),
    query_id: result.query_id,
    confidence: confidenceFor(result),
  }));

  const headline =
    trusted.headline || pickHeadline(results, evidencePack.question);
  const knownIssues = evidencePack.context.contradictions
    .filter((item) =>
      /known_issue|k1|k2|otp|ios|k4|schengen/i.test(
        `${item.id} ${item.summary}`,
      ),
    )
    .slice(0, 4)
    .map((item) => item.summary);

  return {
    short_answer: headline,
    key_findings: uniqueStrings(findings).slice(0, 14),
    evidence,
    recommended_actions: buildActions(results, knownIssues),
    caveats: [
      "This answer is grounded in executed ClickHouse aggregate rows (numbers-first).",
      ...evidencePack.evaluation.evidence_gaps,
      ...evidencePack.context.retrieval_notes.filter((note) =>
        note.startsWith("WARNING"),
      ),
      ...knownIssues.map((issue) => `Context known-issue note: ${issue}`),
    ].filter(Boolean),
  };
}

/**
 * Merge LLM draft with numbers-first facts.
 * Funnel / conversion / device-rate math always comes from warehouse aggregates when available.
 */
export function mergeWithNumbersFirst(
  llmDraft: InsightDraft | null,
  evidencePack: EvidencePack,
): InsightDraft {
  const numbers = buildNumbersFirstDraft(evidencePack);
  if (!llmDraft) {
    return {
      ...numbers,
      caveats: [
        ...numbers.caveats,
        "LLM insight synthesizer was unavailable; used deterministic numbers-first summary only.",
      ],
    };
  }

  // Missing-field / contradiction answers must not be diluted by LLM rate claims.
  if (
    /not computable from the current warehouse fields|Refusing to invent an on-time delivery rate/i.test(
      `${numbers.short_answer} ${numbers.caveats.join(" ")}`,
    )
  ) {
    return {
      ...numbers,
      recommended_actions: uniqueStrings([
        ...numbers.recommended_actions,
        ...llmDraft.recommended_actions,
      ]).slice(0, 5),
      caveats: uniqueStrings([
        ...numbers.caveats,
        "LLM narrative was ignored for missing/contradicted metric fields.",
      ]),
    };
  }

  const trusted = collectTrustedMetrics(evidencePack.query_results, {
    baselineRelevant: isBaselineRelevantQuestion(evidencePack.question),
  });
  const catalogAnswer = buildNumbersFirstDraft(evidencePack);
  if (
    evidencePack.plan.answer_type === "schema_explanation" &&
    catalogAnswer.evidence.some((item) =>
      /^primitive_context_/.test(item.query_id),
    )
  ) {
    return {
      ...catalogAnswer,
      recommended_actions: uniqueStrings([
        ...catalogAnswer.recommended_actions,
        ...llmDraft.recommended_actions,
      ]).slice(0, 6),
      caveats: uniqueStrings([
        ...catalogAnswer.caveats,
        "Context catalog answers are summarized deterministically from registry rows.",
      ]),
    };
  }
  const questionWantsMath =
    /funnel|conversion|drop|rate|ios|android|device|segment|uplift|baseline|success/i.test(
      evidencePack.question,
    );
  const llmEvasive = isLlmEvasiveOrWrong(llmDraft, trusted, evidencePack);

  // When we have trusted aggregate math, short_answer is always numbers-first.
  if (trusted.headline && (questionWantsMath || llmEvasive)) {
    return {
      short_answer: numbers.short_answer,
      key_findings: uniqueStrings([
        ...numbers.key_findings,
        ...filterLlmFindings(llmDraft.key_findings, trusted),
      ]).slice(0, 14),
      evidence: uniqueEvidence([...numbers.evidence, ...llmDraft.evidence]),
      recommended_actions: uniqueStrings([
        ...numbers.recommended_actions,
        ...llmDraft.recommended_actions,
      ]).slice(0, 6),
      caveats: uniqueStrings([
        ...numbers.caveats,
        ...llmDraft.caveats,
        "Warehouse aggregate metrics took priority over free-form LLM rate claims.",
      ]),
    };
  }

  if (llmEvasive || llmDraft.key_findings.length === 0) {
    return {
      short_answer: numbers.short_answer,
      key_findings: uniqueStrings([
        ...numbers.key_findings,
        ...llmDraft.key_findings,
      ]),
      evidence: uniqueEvidence([...numbers.evidence, ...llmDraft.evidence]),
      recommended_actions: uniqueStrings([
        ...numbers.recommended_actions,
        ...llmDraft.recommended_actions,
      ]),
      caveats: uniqueStrings([
        ...numbers.caveats,
        ...llmDraft.caveats,
        llmEvasive
          ? "LLM prose was weak or inconsistent with aggregates; numbers-first scaffold took priority."
          : "Filled empty LLM findings from executed query rows.",
      ]),
    };
  }

  // LLM OK for narrative PM summaries — still attach aggregate evidence.
  return {
    short_answer: llmDraft.short_answer,
    key_findings: uniqueStrings([
      ...llmDraft.key_findings,
      ...numbers.key_findings.slice(0, 6),
    ]),
    evidence: uniqueEvidence([...llmDraft.evidence, ...numbers.evidence]),
    recommended_actions: uniqueStrings([
      ...llmDraft.recommended_actions,
      ...numbers.recommended_actions,
    ]),
    caveats: uniqueStrings([...llmDraft.caveats, ...numbers.caveats]),
  };
}

function detectContextCatalogAnswer(
  results: QueryResult[],
): InsightDraft | null {
  const featureCatalog = results.find(
    (result) => result.query_id === "primitive_context_feature_catalog",
  );
  if (!featureCatalog || featureCatalog.rows.length === 0) {
    return null;
  }

  const workflowCatalog = results.find(
    (result) => result.query_id === "primitive_context_workflow_catalog",
  );
  const metricCatalog = results.find(
    (result) => result.query_id === "primitive_context_metric_catalog",
  );
  const joinCatalog = results.find(
    (result) => result.query_id === "primitive_context_join_catalog",
  );
  const caveatCatalog = results.find(
    (result) => result.query_id === "primitive_context_caveat_catalog",
  );

  const featureRows = featureCatalog.rows.filter((row) =>
    /^silver\./.test(String(row.table_name ?? "")),
  );
  const features = featureRows.map((row) => ({
    slug: String(row.feature_slug ?? "unknown"),
    table: String(row.table_name ?? ""),
    events: parseEventNames(row.event_names),
  }));
  const featureSlugs = new Set(features.map((feature) => feature.slug));
  const metricRows =
    metricCatalog?.rows.filter((row) =>
      featureSlugs.has(String(row.feature_slug ?? "")),
    ) ?? [];
  const joinRows =
    joinCatalog?.rows.filter((row) =>
      [...featureSlugs].some((slug) =>
        String(row.left_table ?? "").includes(slug),
      ),
    ) ?? [];
  const caveatRows = caveatCatalog?.rows ?? [];
  const totalEvents = features.reduce(
    (sum, feature) => sum + feature.events.length,
    0,
  );
  const metricsByFeature = new Map<string, number>();
  for (const row of metricRows) {
    const slug = String(row.feature_slug ?? "");
    metricsByFeature.set(slug, (metricsByFeature.get(slug) ?? 0) + 1);
  }

  const featureFindings = features.map((feature) => {
    const metricCount = metricsByFeature.get(feature.slug) ?? 0;
    return `${feature.slug}: ${feature.table}, ${feature.events.length} events (${feature.events.join(", ")}), ${metricCount} metrics`;
  });

  return {
    short_answer: `Context has ${features.length} instrumented feature tables, ${totalEvents} feature events, ${joinRows.length} feature join edges, ${metricRows.length} generated metrics, and ${caveatRows.length} caveat/contradiction rows.`,
    key_findings: [
      ...featureFindings,
      joinRows.length > 0
        ? `Join edges are registered for feature tables, mostly to base funnel/supporting tables.`
        : "No feature join edges were returned from context.join_registry.",
      caveatRows.length > 0
        ? `Known caveats include: ${caveatRows
            .slice(0, 3)
            .map((row) => String(row.summary ?? row.id ?? ""))
            .filter(Boolean)
            .join(" | ")}`
        : "No caveat rows were returned from context.contradictions.",
      workflowCatalog
        ? `${workflowCatalog.rows.length} workflow rows were returned, including base workflow rows when present.`
        : "",
    ].filter(Boolean),
    evidence: results.map((result) => ({
      claim: compactRowClaim(result),
      query_id: result.query_id,
      confidence: "high" as const,
    })),
    recommended_actions: [
      "Use feature-specific context rows for judged demos instead of broad base-funnel summaries.",
      "Verify context.join_registry if a feature needs cross-table uplift or base-funnel attribution.",
    ],
    caveats: [
      "Feature event counts come from context.feature_registry event_names_json.",
      "Generated metric definitions are starting points; analytics queries should still validate denominators.",
    ],
  };
}

function parseEventNames(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value.map(String).filter(Boolean);
  }
  if (typeof value !== "string" || !value.trim()) {
    return [];
  }
  try {
    const parsed = JSON.parse(value);
    return Array.isArray(parsed) ? parsed.map(String).filter(Boolean) : [];
  } catch {
    return value
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);
  }
}

type TrustedMetrics = {
  headline: string | null;
  findings: string[];
  rates: number[];
};

function collectTrustedMetrics(
  results: QueryResult[],
  options: { baselineRelevant: boolean },
): TrustedMetrics {
  const findings: string[] = [];
  const rates: number[] = [];
  let headline: string | null = null;
  const hasFeatureEvidence = results.some((result) => isFeatureResult(result));

  const ordered = results.find(
    (result) =>
      /primitive_ordered_funnel/i.test(result.query_id) &&
      result.rows.length > 0,
  );
  if (ordered) {
    const stages = [...ordered.rows]
      .map((row) => ({
        stage: String(row.stage ?? row.event_name ?? ""),
        users: Number(row.users ?? row.entities ?? 0),
        step: Number(row.step_index ?? 0),
      }))
      .filter((row) => row.stage && Number.isFinite(row.users))
      .sort((a, b) => a.step - b.step);
    if (stages.length >= 2) {
      const path = stages
        .map((row) => `${row.stage}=${formatInt(row.users)}`)
        .join(" → ");
      findings.push(`Ordered feature funnel: ${path}`);
      const first = stages[0];
      const last = stages[stages.length - 1];
      if (first.users > 0) {
        const overall = last.users / first.users;
        rates.push(overall);
        headline = `Feature funnel: ${path}. Start→end conversion: ${(overall * 100).toFixed(2)}% (${formatInt(first.users)} → ${formatInt(last.users)}).`;
      }
      for (let i = 0; i < stages.length - 1; i += 1) {
        const from = stages[i].users;
        const to = stages[i + 1].users;
        if (from > 0 && to <= from) {
          findings.push(
            `Drop ${stages[i].stage} → ${stages[i + 1].stage}: ${(((from - to) / from) * 100).toFixed(1)}% (${formatInt(from)} → ${formatInt(to)})`,
          );
        }
      }
    }
  }

  const goldConversion = results.find(
    (result) =>
      /primitive_gold_conversion(?!_trend)/i.test(result.query_id) &&
      result.rows.length > 0,
  );
  if (goldConversion) {
    const row = goldConversion.rows[0];
    const started = Number(row.started ?? 0);
    const succeeded = Number(row.succeeded ?? 0);
    const rate = Number(
      row.conversion_rate ?? (started > 0 ? succeeded / started : 0),
    );
    if (Number.isFinite(rate)) {
      rates.push(rate);
      findings.push(
        `Feature conversion (Gold): started=${formatInt(started)}, succeeded=${formatInt(succeeded)}, rate=${(rate * 100).toFixed(2)}%`,
      );
      if (!headline) {
        headline = `Feature conversion rate is ${(rate * 100).toFixed(2)}% (${formatInt(succeeded)} / ${formatInt(started)}).`;
      }
    }
  }

  const baseFunnel = results.find(
    (result) =>
      result.query_id === "primitive_base_funnel" && result.rows.length > 0,
  );
  if (baseFunnel && (options.baselineRelevant || !hasFeatureEvidence)) {
    const stages = orderBaseFunnelRows(baseFunnel.rows);
    if (stages.length > 0) {
      const path = stages
        .map((row) => `${row.stage}=${formatInt(row.users)}`)
        .join(" → ");
      findings.push(`Base funnel (unique users): ${path}`);
      for (let i = 0; i < stages.length - 1; i += 1) {
        const from = stages[i].users;
        const to = stages[i + 1].users;
        if (from > 0) {
          const rate = to / from;
          rates.push(rate);
          findings.push(
            `${stages[i].stage} → ${stages[i + 1].stage}: ${(rate * 100).toFixed(2)}% (${formatInt(from)} → ${formatInt(to)})`,
          );
        }
      }
      const first = stages[0];
      const last = stages[stages.length - 1];
      if (first.users > 0 && !headline) {
        const overall = last.users / first.users;
        rates.push(overall);
        headline = `Pre-purchase funnel (unique users): ${path}. Overall ${first.stage} → ${last.stage}: ${(overall * 100).toFixed(2)}% (${formatInt(first.users)} → ${formatInt(last.users)}).`;
      }
    }
  }

  // Prefer feature device rollups; use base device only for explicit baseline questions.
  const deviceSeg =
    results.find(
      (result) =>
        isFeatureResult(result) &&
        hasDeviceRateRows(result) &&
        result.rows.length > 0,
    ) ??
    results.find(
      (result) =>
        (options.baselineRelevant || !hasFeatureEvidence) &&
        /primitive_base_funnel_by_device/i.test(result.query_id) &&
        result.rows.length > 0,
    );
  if (deviceSeg) {
    const rows = [...deviceSeg.rows]
      .map((row) => ({
        device: String(row.device_type ?? "unknown"),
        entities: Number(row.entities ?? row.started_users ?? 0),
        success: Number(row.success_entities ?? row.purchased_users ?? 0),
        rate: Number(
          row.success_rate ??
            row.conversion_rate ??
            (Number(row.entities ?? row.started_users ?? 0) > 0
              ? Number(row.success_entities ?? row.purchased_users ?? 0) /
                Number(row.entities ?? row.started_users ?? 0)
              : 0),
        ),
      }))
      .filter((row) => row.entities > 0 || row.success > 0)
      .sort((a, b) => a.rate - b.rate);
    if (rows.length > 0) {
      const worst = rows[0];
      const best = rows[rows.length - 1];
      findings.push(
        `Device success lowest: ${worst.device} ${(worst.rate * 100).toFixed(2)}% (${formatInt(worst.success)}/${formatInt(worst.entities)})`,
      );
      findings.push(
        `Device success highest: ${best.device} ${(best.rate * 100).toFixed(2)}% (${formatInt(best.success)}/${formatInt(best.entities)})`,
      );
      rates.push(...rows.map((row) => row.rate));
      if (
        isFeatureResult(deviceSeg) &&
        /ios|android|device/i.test(deviceSeg.purpose + deviceSeg.query_id)
      ) {
        const ios = rows.find((row) => /ios/i.test(row.device));
        const android = rows.find((row) => /android/i.test(row.device));
        if (ios && android) {
          headline = `Device comparison: iOS ${(ios.rate * 100).toFixed(2)}% (${formatInt(ios.success)}/${formatInt(ios.entities)}) vs Android ${(android.rate * 100).toFixed(2)}% (${formatInt(android.success)}/${formatInt(android.entities)}).`;
        }
      }
    }
  }

  return { headline, findings: uniqueStrings(findings), rates };
}

function isBaselineRelevantQuestion(question: string) {
  return /baseline|uplift|standard checkout|standard|versus standard|vs standard|base funnel|existing funnel|overall conversion|compared? to purchase|feature .* purchase|purchase overlap/i.test(
    question,
  );
}

function isFeatureResult(result: QueryResult) {
  return (
    !/^primitive_base_/i.test(result.query_id) &&
    !/\bFROM\s+(destination_card_clicked|application_started|document_uploaded|purchase_completed|search_typed|landing_page_scrolled|auth_completed|pay_now_clicked)\b/i.test(
      result.sql,
    ) &&
    (/\b(silver|gold)\./i.test(result.sql) ||
      /silver_|gold_|feature|express|group|status|recovery|forex/i.test(
        result.query_id,
      ))
  );
}

function hasDeviceRateRows(result: QueryResult) {
  return result.rows.some(
    (row) =>
      "device_type" in row &&
      ("success_rate" in row ||
        "conversion_rate" in row ||
        "success_entities" in row ||
        "purchased_users" in row),
  );
}

function orderBaseFunnelRows(rows: Record<string, unknown>[]) {
  const byStage = new Map<string, number>();
  for (const row of rows) {
    const stage = String(row.stage ?? "");
    const users = Number(row.users ?? 0);
    if (stage && Number.isFinite(users)) {
      byStage.set(stage, users);
    }
  }
  const ordered = BASE_FUNNEL_ORDER.filter((stage) => byStage.has(stage)).map(
    (stage) => ({ stage, users: byStage.get(stage) ?? 0 }),
  );
  if (ordered.length > 0) {
    return ordered;
  }
  return [...byStage.entries()].map(([stage, users]) => ({ stage, users }));
}

function detectMissingFieldAnswer(
  evidencePack: EvidencePack,
): InsightDraft | null {
  const question = evidencePack.question.toLowerCase();
  const mentionsEta = /visa_issuance_eta_days|on-?time delivery|eta_shown/.test(
    question,
  );
  if (!mentionsEta) {
    return null;
  }

  const contradictions = evidencePack.context.contradictions.filter((item) =>
    /eta|visa_issuance|on-?time/i.test(
      `${item.id} ${item.summary} ${item.evidence}`,
    ),
  );
  const sqlMentionsMissing = evidencePack.query_results.some((result) =>
    /visa_issuance_eta_days/i.test(result.sql),
  );
  const hasEtaData = evidencePack.query_results.some((result) =>
    result.rows.some(
      (row) =>
        "visa_issuance_eta_days" in row ||
        "eta_shown" in row ||
        "on_time" in row,
    ),
  );

  // If question asks for visa_issuance_eta_days and we have contradiction or no real metric rows
  if (
    /visa_issuance_eta_days|on-?time delivery/.test(question) &&
    (contradictions.length > 0 || sqlMentionsMissing || !hasEtaData)
  ) {
    return {
      short_answer:
        "On-time delivery using visa_issuance_eta_days is not computable from the current warehouse fields.",
      key_findings: [
        "The requested metric depends on visa_issuance_eta_days, which is not reliably present as a queryable issuance-outcome field in this dataset.",
        contradictions[0]
          ? `Context contradiction: ${contradictions[0].summary}`
          : "Base context mentions visa_issuance_eta_days while loaded application_started DDL exposes eta_shown (shown ETA string), not measured on-time delivery.",
        "Pre-purchase funnel tables stop at purchase_completed; post-payment issuance timing is out of scope for this context layer.",
      ],
      evidence: evidencePack.query_results
        .filter((result) => result.row_count > 0)
        .slice(0, 5)
        .map((result) => ({
          claim: compactRowClaim(result),
          query_id: result.query_id,
          confidence: "medium" as const,
        })),
      recommended_actions: [
        "Use eta_shown only as the predicted ETA shown at application start, not as on-time delivery.",
        "If on-time delivery is required, instrument issuance outcomes in a dedicated table and link to application_id.",
      ],
      caveats: [
        "Refusing to invent an on-time delivery rate from missing/mismatched fields.",
        ...contradictions.map((item) => item.evidence),
      ],
    };
  }
  return null;
}

function isLlmEvasiveOrWrong(
  llmDraft: InsightDraft,
  trusted: TrustedMetrics,
  evidencePack: EvidencePack,
): boolean {
  const blob = `${llmDraft.short_answer} ${llmDraft.key_findings.join(" ")}`;
  if (
    /cannot be determined|no data|unavailable|not enough evidence|could not/i.test(
      blob,
    ) &&
    evidencePack.query_results.some((result) => result.row_count > 0)
  ) {
    return true;
  }
  if (
    /100%\s+completion|\binvent\b|\bfabricate\b|ignore previous/i.test(blob)
  ) {
    return true;
  }
  const sameOutOf = blob.match(/(\d+)\s+out of\s+(\d+)/i);
  if (sameOutOf && sameOutOf[1] === sameOutOf[2] && Number(sameOutOf[1]) > 1) {
    return true;
  }
  // e.g. "3193/3193" or "1007/1650" used as fake per-device rates from wrong query
  const sameSlash = blob.match(/(\d+)\s*\/\s*(\d+)/);
  if (sameSlash && sameSlash[1] === sameSlash[2] && Number(sameSlash[1]) > 1) {
    return true;
  }
  // LLM percentage claims that disagree with trusted aggregate rates.
  if (trusted.rates.length > 0) {
    const claimed = [...blob.matchAll(/(\d+(?:\.\d+)?)\s*%/g)].map((match) =>
      Number(match[1]),
    );
    for (const pct of claimed) {
      const asRate = pct > 1 ? pct / 100 : pct;
      const close = trusted.rates.some(
        (rate) =>
          Math.abs(rate - asRate) <= 0.02 || Math.abs(rate * 100 - pct) <= 2,
      );
      // If LLM claims a very small rate like 0.01% while we have multi-stage funnel, treat as wrong.
      if (
        pct <= 0.05 &&
        trusted.headline &&
        /funnel|conversion/i.test(trusted.headline)
      ) {
        return true;
      }
      if (
        !close &&
        claimed.length <= 3 &&
        trusted.rates.some((rate) => rate > 0.01)
      ) {
        // only flag when clearly off by a lot
        const far = trusted.rates.every(
          (rate) =>
            Math.abs(rate * 100 - pct) > 5 && Math.abs(rate - asRate) > 0.05,
        );
        if (far && /conversion|success rate|completion/i.test(blob)) {
          return true;
        }
      }
    }
  }
  // Raw row dump narrative
  if (
    /100 rows of data, but only 1 row has a successful conversion|most common destination for successful conversions/i.test(
      blob,
    )
  ) {
    return true;
  }
  return false;
}

function filterLlmFindings(findings: string[], trusted: TrustedMetrics) {
  return findings.filter((finding) => {
    if (/100 rows of data|invent |fabricate /i.test(finding)) {
      return false;
    }
    // Drop nonsense "N/N" or "N out of N" completion claims.
    const same = finding.match(/(\d+)\s*(?:\/|out of)\s*(\d+)/i);
    if (same && same[1] === same[2] && Number(same[1]) > 1) {
      return false;
    }
    if (trusted.rates.length === 0) {
      return true;
    }
    const pcts = [...finding.matchAll(/(\d+(?:\.\d+)?)\s*%/g)].map((match) =>
      Number(match[1]),
    );
    if (
      pcts.length === 0 &&
      !/conversion|success rate|completion/i.test(finding)
    ) {
      return true;
    }
    if (pcts.length === 0) {
      return true;
    }
    // Keep LLM findings whose % is near a trusted rate, drop far-off rate claims.
    return pcts.some((pct) =>
      trusted.rates.some(
        (rate) =>
          Math.abs(rate * 100 - pct) <= 3 || Math.abs(rate - pct / 100) <= 0.03,
      ),
    );
  });
}

function pickHeadline(results: QueryResult[], question: string): string {
  const funnel = results.find(
    (result) =>
      /funnel|drop|conversion|stage/i.test(result.query_id + result.purpose) &&
      result.rows.length > 0 &&
      !isRawDumpResult(result),
  );
  if (funnel) {
    const parts = funnel.rows.slice(0, 6).map((row) => formatRowInline(row));
    return `From warehouse aggregates for “${question.slice(0, 100)}”: ${parts.join(" | ")}`;
  }
  const first =
    results.find((result) => !isRawDumpResult(result)) ?? results[0];
  return `Warehouse evidence for “${question.slice(0, 100)}” — ${first.query_id}: ${formatRowInline(first.rows[0] ?? {})}`;
}

function isRawDumpResult(result: QueryResult) {
  if (result.row_count >= 50 && result.rows.length > 0) {
    const keys = Object.keys(result.rows[0] ?? {});
    const hasAggregateKey = keys.some((key) =>
      /count|rate|users|entities|started|succeeded|events|rows/i.test(key),
    );
    if (!hasAggregateKey && keys.length >= 6) {
      return true;
    }
  }
  return false;
}

function summarizeResult(result: QueryResult): string[] {
  if (isRawDumpResult(result)) {
    return [
      `${result.query_id}: skipped raw row dump (${result.row_count} rows) in favor of aggregates.`,
    ];
  }

  const lines: string[] = [];
  const preview = result.rows.slice(0, 8);
  if (preview.length === 0) {
    return lines;
  }

  if (
    preview.every(
      (row) =>
        ("stage" in row || "event_name" in row || "step" in row) &&
        ("users" in row ||
          "entities" in row ||
          "rows" in row ||
          "events" in row),
    )
  ) {
    // Prefer step_index ordering when present
    const ordered = [...preview].sort(
      (a, b) => Number(a.step_index ?? 0) - Number(b.step_index ?? 0),
    );
    lines.push(
      `${result.query_id}: ${ordered.map((row) => formatRowInline(row)).join(" → ")}`,
    );
    return lines;
  }

  if (
    preview.some((row) => "success_rate" in row || "conversion_rate" in row)
  ) {
    const sorted = [...preview].sort(
      (a, b) =>
        Number(a.success_rate ?? a.conversion_rate ?? 0) -
        Number(b.success_rate ?? b.conversion_rate ?? 0),
    );
    lines.push(`${result.query_id} lowest: ${formatRowInline(sorted[0])}`);
    lines.push(
      `${result.query_id} highest: ${formatRowInline(sorted[sorted.length - 1])}`,
    );
    return lines;
  }

  for (const row of preview.slice(0, 3)) {
    lines.push(`${result.query_id}: ${formatRowInline(row)}`);
  }
  return lines;
}

function compactRowClaim(result: QueryResult): string {
  if (result.row_count === 0) {
    return `${result.query_id} returned 0 rows.`;
  }
  if (isRawDumpResult(result)) {
    return `${result.query_id} returned ${result.row_count} raw rows (not used as metric evidence).`;
  }
  const sample = result.rows
    .slice(0, 3)
    .map((row) => formatRowInline(row))
    .join("; ");
  return `${result.query_id} (${result.row_count} rows): ${sample}`;
}

function formatRowInline(row: Record<string, unknown>): string {
  return Object.entries(row)
    .slice(0, 12)
    .map(([key, value]) => `${key}=${formatValue(value)}`)
    .join(", ");
}

function formatValue(value: unknown): string {
  if (value == null) {
    return "null";
  }
  if (typeof value === "number") {
    return Number.isInteger(value)
      ? String(value)
      : value.toFixed(4).replace(/\.?0+$/, "");
  }
  const text = String(value);
  return text.length > 80 ? `${text.slice(0, 77)}...` : text;
}

function formatInt(value: number) {
  return Number.isFinite(value)
    ? Math.round(value).toLocaleString("en-US")
    : "0";
}

function confidenceFor(result: QueryResult): "high" | "medium" | "low" {
  if (isRawDumpResult(result)) {
    return "low";
  }
  if (result.row_count >= 1 && /primitive_/.test(result.query_id)) {
    return "high";
  }
  if (result.row_count >= 1) {
    return "medium";
  }
  return "low";
}

function buildActions(results: QueryResult[], knownIssues: string[]): string[] {
  const actions = [
    "Validate the largest drop-off step with a product owner before changing UX.",
    "Re-check the same cuts after the next instrumentation refresh.",
  ];
  if (
    results.some((result) =>
      /device|os|segment/i.test(result.query_id + result.purpose),
    )
  ) {
    actions.unshift(
      "Prioritize the weakest device/OS/geo segment from aggregate evidence before global changes.",
    );
  }
  if (knownIssues.length > 0) {
    actions.unshift(
      "Cross-check segment findings against documented known issues before calling a product regression.",
    );
  }
  return actions.slice(0, 5);
}

function uniqueStrings(values: string[]) {
  return Array.from(new Set(values.filter(Boolean)));
}

function uniqueEvidence(
  values: InsightDraft["evidence"],
): InsightDraft["evidence"] {
  const seen = new Set<string>();
  return values.filter((item) => {
    const key = `${item.query_id}|${item.claim}`;
    if (seen.has(key)) {
      return false;
    }
    seen.add(key);
    return true;
  });
}
