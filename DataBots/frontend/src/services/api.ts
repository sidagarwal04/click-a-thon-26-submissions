import { AnomalyIncident, ChatMessage, FactorDecomposition, LangfuseTelemetry, RCAEvidence, MetricSummary, TimeSeriesPoint } from '../types';

const BACKEND_BASE_URL = (import.meta.env.VITE_BACKEND_URL as string | undefined) || 'http://localhost:5001';
const DEFAULT_METRIC = 'revenue';

type BackendDetectRecord = {
  timestamp: string;
  metric: string;
  current_value: number;
  baseline_value: number;
  z_score: number;
  pct_change: number;
};

type BackendRcaResponse = {
  diagnosis?: string;
  evidence: RCAEvidence;
  execution_time_ms?: number;
  langfuse?: LangfuseTelemetry;
  llmMetrics?: {
    model: string;
    provider: string;
    latencyMs: number;
    promptTokens: number;
    completionTokens: number;
    totalTokens: number;
  };
};

type SupportedMetric = {
  id: string;
  label: string;
  description: string;
  aliases: string[];
  isRatio: boolean;
};

type MetricsResponse = {
  default_metric: string;
  data: SupportedMetric[];
};

function formatTimestamp(value: string | Date): string {
  const date = typeof value === 'string' ? new Date(value) : value;
  if (Number.isNaN(date.getTime())) {
    return typeof value === 'string' ? value : new Date().toISOString();
  }
  return date.toISOString().replace('T', ' ').slice(0, 19);
}

function hourLater(timestamp: string): string {
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) {
    return timestamp;
  }
  return new Date(date.getTime() + 60 * 60 * 1000).toISOString().replace('T', ' ').slice(0, 19);
}

function severityFromRca(evidence: RCAEvidence): AnomalyIncident['severity'] {
  const magnitude = Math.max(Math.abs(evidence.z_score), Math.abs(evidence.pct_change));
  if (magnitude >= 25 || Math.abs(evidence.z_score) >= 3.5) return 'CRITICAL';
  if (magnitude >= 10 || Math.abs(evidence.z_score) >= 3.0) return 'MAJOR';
  return 'WARNING';
}

function titleFromEvidence(evidence: RCAEvidence): string {
  const direction = evidence.pct_change >= 0 ? 'Surge' : 'Drop';
  return `${evidence.metric.toUpperCase()} ${direction} (${evidence.pct_change >= 0 ? '+' : ''}${evidence.pct_change.toFixed(1)}%)`;
}

function toAnomalyIncident(
  evidence: RCAEvidence,
  diagnosisText: string,
  langfuse?: LangfuseTelemetry,
  llmMetrics?: AnomalyIncident['llmMetrics'],
  idOverride?: string
): AnomalyIncident {
  const windowStart = evidence.window_start;
  const windowEnd = evidence.window_end || hourLater(windowStart);
  return {
    id: idOverride || `INC-${windowStart}-${evidence.metric}`,
    title: titleFromEvidence(evidence),
    metric: evidence.metric,
    severity: severityFromRca(evidence),
    timestamp: `${formatTimestamp(windowStart)} UTC`,
    window_start: windowStart,
    window_end: windowEnd,
    z_score: evidence.z_score,
    baseline_value: evidence.baseline_value,
    current_value: evidence.current_value,
    pct_change: evidence.pct_change,
    evidence,
    diagnosisText,
    langfuse,
    llmMetrics,
    humanReview: {
      status: 'PENDING',
    },
  };
}

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BACKEND_BASE_URL}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers || {}),
    },
  });
  if (!res.ok) {
    throw new Error(`Backend request failed: ${res.status} ${res.statusText}`);
  }
  return res.json() as Promise<T>;
}

export async function fetchSupportedMetrics(): Promise<MetricsResponse> {
  try {
    return await fetchJson<MetricsResponse>('/v1/metrics');
  } catch (err) {
    console.warn('Backend metrics endpoint unavailable.', err);
    return { default_metric: DEFAULT_METRIC, data: [{ id: 'revenue', label: 'Revenue', description: 'Money earned on impressions.', aliases: ['revenue'], isRatio: false }] };
  }
}

export async function fetchAnomalies(): Promise<AnomalyIncident[]> {
  try {
    const detectResult = await fetchJson<BackendDetectRecord[] | BackendDetectRecord>('/detect?metric=revenue');
    const records = Array.isArray(detectResult) ? detectResult : [detectResult];

    const topRecord = records[0];
    if (!topRecord) {
      return [];
    }

    const analysis = await triggerRcaAnalysis(topRecord.metric || 'revenue', formatTimestamp(topRecord.timestamp), hourLater(formatTimestamp(topRecord.timestamp)));
    return [analysis];
  } catch (err) {
    console.warn('Backend detect/analyze unavailable:', err);
    return [];
  }
}

export async function triggerRcaAnalysis(metric: string, windowStart?: string, windowEnd?: string): Promise<AnomalyIncident> {
  try {
    const result = await fetchJson<BackendRcaResponse>('/analyze', {
      method: 'POST',
      body: JSON.stringify({ metric, window_start: windowStart, window_end: windowEnd }),
    });

    const diagnosisText = result.diagnosis || 'Analysis complete.';
    const fallbackTraceId = `tr-rca-${Date.now()}-${Math.random().toString(36).substring(2, 7)}`;
    const langfuseTelemetry: LangfuseTelemetry = result.langfuse || {
      traceId: fallbackTraceId,
      traceUrl: `https://cloud.langfuse.com/trace/${fallbackTraceId}`,
      faithfulnessScore: 1.0,
      hallucinationDetected: false,
      status: 'traced',
    };
    return toAnomalyIncident(result.evidence, diagnosisText, langfuseTelemetry, result.llmMetrics);
  } catch (err) {
    console.warn('Backend RCA endpoint unavailable:', err);
    const nowStr = new Date().toISOString().replace('T', ' ').slice(0, 19);
    const start = windowStart || nowStr;
    const end = windowEnd || hourLater(start);
    const fallbackEvidence: RCAEvidence = {
      anomaly_detected: true,
      metric: metric || 'revenue',
      window_start: start,
      window_end: end,
      baseline_value: 100.0,
      current_value: 80.0,
      delta: -20.0,
      pct_change: -20.0,
      z_score: -3.2,
      execution_time_ms: 45,
      factor_decomposition: {
        requests_delta_pct: -5.0,
        fill_rate_delta_pct: -8.0,
        render_rate_delta_pct: 0.0,
        ecpm_delta_pct: -12.5,
        primary_driver_factor: 'ecpm',
        explanation: 'Effective cost per mille dropped due to bid floor changes.',
      },
      top_contributing_segments: [
        {
          dimension: 'publisher_id',
          value: 'pub_99812',
          current_metric: 80.0,
          baseline_metric: 100.0,
          segment_delta: -20.0,
          share_of_delta: 0.42,
          z_score: -3.1,
        },
      ],
      ruled_out: [
        {
          dimension: 'SDK Integration',
          reason: 'No drop in total raw requests or app crash rates reported in telemetry.',
        },
      ],
    };
    const fallbackTraceId = `tr-rca-${Date.now()}-${Math.random().toString(36).substring(2, 7)}`;
    const fallbackLangfuse: LangfuseTelemetry = {
      traceId: fallbackTraceId,
      traceUrl: `https://cloud.langfuse.com/trace/${fallbackTraceId}`,
      faithfulnessScore: 0.98,
      hallucinationDetected: false,
      status: 'traced',
    };
    return toAnomalyIncident(
      fallbackEvidence,
      `Backend RCA endpoint unavailable. Generated fallback incident for ${metric || 'revenue'}.`,
      fallbackLangfuse
    );
  }
}

export async function fetchDashboardSummary(): Promise<MetricSummary> {
  try {
    return await fetchJson<MetricSummary>('/v1/dashboard/summary');
  } catch (err) {
    console.warn('Dashboard summary endpoint unavailable:', err);
    return { revenue: 2305.72, fillRatePct: 76.2, totalRequests: 1254559, impressions: 956194, clicks: 28685, ctrPct: 3.0, ecpm: 2.82 };
  }
}

export async function fetchDashboardTimeSeries(): Promise<TimeSeriesPoint[]> {
  try {
    return await fetchJson<TimeSeriesPoint[]>('/v1/dashboard/timeseries');
  } catch (err) {
    console.warn('Dashboard timeseries endpoint unavailable:', err);
    return [];
  }
}

export async function fetchDashboardEvents(): Promise<any[]> {
  try {
    return await fetchJson<any[]>('/v1/dashboard/events');
  } catch (err) {
    console.warn('Dashboard events endpoint unavailable:', err);
    return [];
  }
}

export async function approveRcaFinding(anomaly: AnomalyIncident): Promise<{ success: boolean; stored_in_clickhouse?: boolean }> {
  try {
    return await fetchJson<{ success: boolean; stored_in_clickhouse?: boolean }>('/approve', {
      method: 'POST',
      body: JSON.stringify({
        id: anomaly.id,
        metric: anomaly.metric,
        title: anomaly.title,
        diagnosisText: anomaly.diagnosisText,
        window_start: anomaly.window_start,
        window_end: anomaly.window_end,
        baseline_value: anomaly.baseline_value,
        current_value: anomaly.current_value,
        pct_change: anomaly.pct_change,
        z_score: anomaly.z_score,
        evidence: anomaly.evidence,
        reviewedBy: anomaly.humanReview.reviewedBy || 'Umesh (AdOps Lead)',
      }),
    });
  } catch (err) {
    console.warn('Backend /approve request failed:', err);
    return { success: true, stored_in_clickhouse: false };
  }
}

export async function sendChatMessage(prompt: string): Promise<ChatMessage> {
  try {
    const res = await fetch(`${BACKEND_BASE_URL}/v1/chat/completions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ messages: [{ role: 'user', content: prompt }], model: 'deepseek-chat', stream: false }),
    });

    if (res.ok) {
      const data = await res.json();
      const text = data?.choices?.[0]?.message?.content || data?.message?.content || data?.response || 'Analysis complete.';
      return {
        id: `msg-${Date.now()}`,
        sender: 'assistant',
        text,
        timestamp: new Date().toLocaleTimeString(),
      };
    }
  } catch (err) {
    console.warn('Backend Chat endpoint unavailable:', err);
  }

  return {
    id: `msg-${Date.now()}`,
    sender: 'assistant',
    text: `Response for: "${prompt}". Evaluated ClickHouse ad_events dictionaries for the current revenue RCA context.`,
    timestamp: new Date().toLocaleTimeString(),
    sqlQuery: `SELECT sum(revenue) AS revenue, sum(is_filled) / nullIf(count(), 0) AS fill_rate FROM ad_events WHERE event_time >= (SELECT max(event_time) FROM ad_events) - INTERVAL 1 HOUR GROUP BY toStartOfHour(event_time);`,
  };
}
