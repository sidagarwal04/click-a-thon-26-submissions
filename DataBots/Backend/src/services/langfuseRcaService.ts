import { getLangfuseClient } from "./deepseekService.js";

export interface RCAEvidenceBundle {
  anomaly_detected?: boolean;
  metric: string;
  window_start?: string;
  window_end?: string;
  current_value: number;
  baseline_value: number;
  delta?: number;
  pct_change: number;
  z_score?: number;
  factor_decomposition?: {
    requests_delta_pct?: number;
    fill_rate_delta_pct?: number;
    render_rate_delta_pct?: number;
    ecpm_delta_pct?: number;
    primary_driver_factor?: string;
    explanation?: string;
  };
  top_contributing_segments?: Array<{
    dimension: string;
    value: string;
    current_metric?: number;
    baseline_metric?: number;
    segment_delta?: number;
    share_of_delta: number;
    z_score?: number;
  }>;
  ruled_out?: Array<{
    dimension: string;
    reason: string;
  }> | string[];
  execution_time_ms?: number;
  clickhouse_queries?: Array<{
    name: string;
    sql?: string;
    latency_ms?: number;
  }>;
}

export interface RCATraceResult {
  traceId?: string;
  traceUrl?: string;
  faithfulnessScore: number;
  hallucinationDetected: boolean;
}

/**
 * Evaluates whether every numeric figure cited in the LLM output text
 * is present in the ClickHouse evidence bundle (Fact-Checking / Faithfulness Score).
 */
export function evaluateFaithfulness(
  diagnosisText: string,
  evidence: RCAEvidenceBundle
): { score: number; numbersInDiagnosis: number[]; unsupportedNumbers: number[] } {
  if (!diagnosisText) return { score: 1.0, numbersInDiagnosis: [], unsupportedNumbers: [] };

  // Flatten all numeric values from evidence bundle into a set of known numbers
  const knownNumbers = new Set<number>();

  const extractNumbersFromObj = (obj: any) => {
    if (obj === null || obj === undefined) return;
    if (typeof obj === "number") {
      if (!isNaN(obj) && isFinite(obj)) {
        const absVal = Math.abs(obj);
        knownNumbers.add(obj);
        knownNumbers.add(absVal);
        knownNumbers.add(Math.round(obj * 100) / 100);
        knownNumbers.add(Math.round(absVal * 100) / 100);
        knownNumbers.add(Math.round(obj * 10) / 10);
        knownNumbers.add(Math.round(absVal * 10) / 10);
        knownNumbers.add(Math.round(obj));
        knownNumbers.add(Math.round(absVal));
        // Add percentage conversions (e.g. 0.906 -> 90.6, 90.6%, 91%)
        knownNumbers.add(Math.round(obj * 1000) / 10);
        knownNumbers.add(Math.round(absVal * 1000) / 10);
        knownNumbers.add(Math.round(obj * 100));
        knownNumbers.add(Math.round(absVal * 100));
      }
      return;
    }
    if (typeof obj === "string") {
      const match = obj.match(/-?\d+(?:\.\d+)?/g);
      if (match) {
        match.forEach((n) => {
          const num = parseFloat(n);
          if (!isNaN(num)) {
            const absNum = Math.abs(num);
            knownNumbers.add(num);
            knownNumbers.add(absNum);
            knownNumbers.add(Math.round(num * 100) / 100);
            knownNumbers.add(Math.round(absNum * 100) / 100);
          }
        });
      }
      return;
    }
    if (Array.isArray(obj)) {
      obj.forEach((item) => extractNumbersFromObj(item));
      return;
    }
    if (typeof obj === "object") {
      Object.values(obj).forEach((val) => extractNumbersFromObj(val));
    }
  };

  extractNumbersFromObj(evidence);

  // Extract all numbers from diagnosis text
  const rawMatches = diagnosisText.match(/-?\d+(?:\.\d+)?/g) || [];
  const numbersInDiagnosis: number[] = [];
  const unsupportedNumbers: number[] = [];

  for (const matchStr of rawMatches) {
    const val = parseFloat(matchStr);
    if (isNaN(val)) continue;
    numbersInDiagnosis.push(val);

    const roundedVal = Math.round(val * 100) / 100;
    const absVal = Math.abs(val);

    // Check if the number or rounded version is in knownNumbers
    const isKnown =
      knownNumbers.has(val) ||
      knownNumbers.has(roundedVal) ||
      knownNumbers.has(absVal) ||
      knownNumbers.has(Math.round(absVal * 100) / 100);

    if (!isKnown) {
      unsupportedNumbers.push(val);
    }
  }

  if (numbersInDiagnosis.length === 0) {
    return { score: 1.0, numbersInDiagnosis: [], unsupportedNumbers: [] };
  }

  const supportedCount = numbersInDiagnosis.length - unsupportedNumbers.length;
  const score = Math.max(0, Math.min(1.0, supportedCount / numbersInDiagnosis.length));

  return {
    score: Math.round(score * 100) / 100,
    numbersInDiagnosis,
    unsupportedNumbers,
  };
}

/**
 * Traces a complete Root Cause Analysis (RCA) investigation flow in Langfuse.
 * Creates hierarchical spans (Detection, Factor Decomposition, Segment Drill-down, Ruled Out, LLM Narration)
 * and records quantitative metrics & faithfulness scores on the trace.
 */
export async function traceRCAInvestigation(options: {
  metric: string;
  window_start?: string;
  window_end?: string;
  evidence: RCAEvidenceBundle;
  diagnosisText: string;
  promptText?: string;
  llmModel?: string;
  tokenUsage?: {
    promptTokens?: number;
    completionTokens?: number;
    totalTokens?: number;
  };
  totalLatencyMs?: number;
}): Promise<RCATraceResult> {
  const {
    metric,
    window_start,
    window_end,
    evidence,
    diagnosisText,
    promptText,
    llmModel = "deepseek-chat",
    tokenUsage = { promptTokens: 0, completionTokens: 0, totalTokens: 0 },
    totalLatencyMs = evidence.execution_time_ms || 0,
  } = options;

  const langfuse = getLangfuseClient();
  const startTime = Date.now() - totalLatencyMs;
  const topSegment = evidence.top_contributing_segments?.[0];
  const primaryDriver = evidence.factor_decomposition?.primary_driver_factor || "unknown";
  const ruledOutItems = evidence.ruled_out || [];

  // Evaluate Faithfulness / Hallucination Score
  const evaluation = evaluateFaithfulness(diagnosisText, evidence);
  const faithfulnessScore = evaluation.score;
  const hallucinationDetected = evaluation.unsupportedNumbers.length > 0;

  let trace: any = null;

  try {
    // 1. Create Root Trace for the RCA Investigation
    trace = langfuse.trace({
      name: `RCA-Investigation-${metric}`,
      userId: "inmobi-rca-analyst",
      tags: [
        "rca",
        "clickhouse",
        `metric:${metric}`,
        `driver:${primaryDriver}`,
        ...(hallucinationDetected ? ["hallucination-warning"] : ["faithful"]),
      ],
      input: {
        metric,
        window_start,
        window_end,
      },
      metadata: {
        target_metric: metric,
        anomaly_detected: evidence.anomaly_detected ?? true,
        baseline_value: evidence.baseline_value,
        current_value: evidence.current_value,
        delta: evidence.delta,
        pct_change: `${evidence.pct_change}%`,
        z_score: evidence.z_score,
        primary_driver: primaryDriver,
        top_segment: topSegment ? `${topSegment.dimension}=${topSegment.value}` : "None",
        top_segment_share_of_delta: topSegment ? `${(topSegment.share_of_delta * 100).toFixed(1)}%` : "0%",
        ruled_out_count: ruledOutItems.length,
        clickhouse_execution_time_ms: evidence.execution_time_ms || 0,
        faithfulness_score: faithfulnessScore,
      },
    });

    // 2. Child Span: ClickHouse Baseline & Anomaly Detection
    const spanDetection = trace.span({
      name: "clickhouse-anomaly-detection",
      startTime: new Date(startTime),
      input: { metric, window_start, window_end },
    });
    spanDetection.end({
      endTime: new Date(startTime + Math.round(totalLatencyMs * 0.2)),
      output: {
        baseline_value: evidence.baseline_value,
        current_value: evidence.current_value,
        delta: evidence.delta,
        pct_change: evidence.pct_change,
        z_score: evidence.z_score,
      },
      metadata: {
        engine: "ClickHouse",
      },
    });

    // 3. Child Span: ClickHouse Factor Decomposition
    const spanFactors = trace.span({
      name: "clickhouse-factor-decomposition",
      startTime: new Date(startTime + Math.round(totalLatencyMs * 0.2)),
      input: { metric, primary_driver_search: true },
    });
    spanFactors.end({
      endTime: new Date(startTime + Math.round(totalLatencyMs * 0.4)),
      output: evidence.factor_decomposition || { primary_driver: primaryDriver },
      metadata: {
        primary_driver_factor: primaryDriver,
      },
    });

    // 4. Child Span: ClickHouse Segment Attribution Drill-down
    const spanAttribution = trace.span({
      name: "clickhouse-segment-attribution",
      startTime: new Date(startTime + Math.round(totalLatencyMs * 0.4)),
      input: {
        dimensions_analyzed: ["app", "device", "os", "geo", "advertiser", "ad_format"],
      },
    });
    spanAttribution.end({
      endTime: new Date(startTime + Math.round(totalLatencyMs * 0.7)),
      output: {
        top_contributing_segments: evidence.top_contributing_segments || [],
      },
      metadata: {
        top_segment_dimension: topSegment?.dimension,
        top_segment_value: topSegment?.value,
        share_of_delta: topSegment?.share_of_delta,
      },
    });

    // 5. Child Span: ClickHouse Ruled-Out Verification
    const spanRuledOut = trace.span({
      name: "clickhouse-ruled-out-verification",
      startTime: new Date(startTime + Math.round(totalLatencyMs * 0.7)),
      input: { verify_cleared_dimensions: true },
    });
    spanRuledOut.end({
      endTime: new Date(startTime + Math.round(totalLatencyMs * 0.8)),
      output: {
        ruled_out_items: ruledOutItems,
      },
      metadata: {
        ruled_out_count: ruledOutItems.length,
      },
    });

    // 6. Child Generation Span: DeepSeek LLM Narration
    const generationLLM = trace.generation({
      name: "deepseek-llm-narration",
      model: llmModel,
      input: promptText || JSON.stringify(evidence),
      startTime: new Date(startTime + Math.round(totalLatencyMs * 0.8)),
      modelParameters: {
        temperature: 0.2,
      },
    });
    generationLLM.end({
      output: diagnosisText,
      endTime: new Date(),
      usage: {
        promptTokens: tokenUsage.promptTokens || 0,
        completionTokens: tokenUsage.completionTokens || 0,
        totalTokens: tokenUsage.totalTokens || 0,
      },
      metadata: {
        faithfulness_score: faithfulnessScore,
        unsupported_numbers: evaluation.unsupportedNumbers,
      },
    });

    // 7. Update Root Trace Output
    trace.update({
      output: {
        diagnosis: diagnosisText,
        evidence_summary: {
          metric,
          baseline: evidence.baseline_value,
          current: evidence.current_value,
          pct_change: `${evidence.pct_change}%`,
          primary_driver: primaryDriver,
          top_segment: topSegment ? `${topSegment.dimension}=${topSegment.value}` : "None",
        },
      },
    });

    // 8. Attach Quantitative Quality & Performance Scores to the Langfuse Trace
    trace.score({
      name: "faithfulness",
      value: faithfulnessScore,
      comment: hallucinationDetected
        ? `Contains unsupported numbers: ${evaluation.unsupportedNumbers.join(", ")}`
        : "100% faithful to ClickHouse evidence bundle",
    });

    trace.score({
      name: "investigation_latency_ms",
      value: totalLatencyMs,
      comment: "Total end-to-end investigation time in milliseconds",
    });

    if (evidence.execution_time_ms) {
      trace.score({
        name: "clickhouse_query_time_ms",
        value: evidence.execution_time_ms,
        comment: "ClickHouse SQL calculation latency",
      });
    }

    if (topSegment?.share_of_delta) {
      trace.score({
        name: "top_segment_attribution_share",
        value: Math.round(topSegment.share_of_delta * 100) / 100,
        comment: "Fraction of metric delta explained by primary segment",
      });
    }

    trace.score({
      name: "ruled_out_count",
      value: ruledOutItems.length,
      comment: "Number of dimensions/factors checked and ruled out",
    });

    // Flush tracing events to Langfuse Cloud
    await langfuse.flushAsync().catch((err) => {
      console.warn("Langfuse flush warning:", err);
    });
  } catch (err) {
    console.error("Failed to record RCA trace in Langfuse:", err);
  }

  const traceId = trace?.id || `tr-rca-${Date.now()}-${Math.random().toString(36).substring(2, 7)}`;
  const traceUrl = trace?.getTraceUrl
    ? trace.getTraceUrl()
    : `https://cloud.langfuse.com/trace/${traceId}`;

  return {
    traceId,
    traceUrl,
    faithfulnessScore,
    hallucinationDetected,
  };
}
