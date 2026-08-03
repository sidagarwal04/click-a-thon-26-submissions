export type ModuleType = 'dashboard' | 'rca';

export type AnomalySeverity = 'CRITICAL' | 'MAJOR' | 'WARNING';

export type HumanReviewStatus = 'PENDING' | 'APPROVED' | 'HALLUCINATION';

export interface HumanReview {
  status: HumanReviewStatus;
  reviewedAt?: string;
  reviewedBy?: string;
  hallucinationReason?: string;
  feedbackNote?: string;
}

export interface FactorDecomposition {
  requests_delta_pct: number;
  fill_rate_delta_pct: number;
  render_rate_delta_pct: number;
  ecpm_delta_pct: number;
  primary_driver_factor: string;
  explanation: string;
}

export interface SegmentDriver {
  dimension: string;
  value: string;
  current_metric: number;
  baseline_metric: number;
  segment_delta: number;
  share_of_delta: number; // e.g. 0.928 = 92.8%
  z_score: number;
}

export interface RuledOutCause {
  dimension: string;
  reason: string;
}

export interface LangfuseTelemetry {
  traceId: string;
  traceUrl?: string;
  faithfulnessScore: number;
  hallucinationDetected: boolean;
  status: string;
  sqlSpansCount?: number;
  executionTimeMs?: number;
}

export interface LlmMetrics {
  model: string;
  latencyMs: number;
  promptTokens: number;
  completionTokens: number;
  totalTokens: number;
  provider: string;
}

export interface RCAEvidence {
  anomaly_detected: boolean;
  metric: string;
  window_start: string;
  window_end: string;
  baseline_value: number;
  current_value: number;
  delta: number;
  pct_change: number;
  z_score: number;
  factor_decomposition: FactorDecomposition;
  top_contributing_segments: SegmentDriver[];
  ruled_out: RuledOutCause[];
  execution_time_ms: number;
}

export interface AnomalyIncident {
  id: string;
  title: string;
  metric: string;
  severity: AnomalySeverity;
  timestamp: string;
  window_start: string;
  window_end: string;
  z_score: number;
  baseline_value: number;
  current_value: number;
  pct_change: number;
  evidence: RCAEvidence;
  diagnosisText: string;
  langfuse?: LangfuseTelemetry;
  llmMetrics?: LlmMetrics;
  humanReview: HumanReview;
}

export interface MetricSummary {
  totalRequests: number;
  fillRatePct: number;
  impressions: number;
  clicks: number;
  ctrPct: number;
  revenue: number;
  ecpm: number;
}

export interface TimeSeriesPoint {
  time: string;
  actualFillRate: number;
  baselineFillRate: number;
  actualRevenue: number;
  baselineRevenue: number;
  requests: number;
  ecpm: number;
  isAnomaly?: boolean;
}

export interface FilterState {
  timeRange: string;
  appCategory: string;
  vertical: string;
  region: string;
  adFormat: string;
  deviceModel: string;
}

export interface ChatMessage {
  id: string;
  sender: 'user' | 'assistant';
  text: string;
  timestamp: string;
  sqlQuery?: string;
}
