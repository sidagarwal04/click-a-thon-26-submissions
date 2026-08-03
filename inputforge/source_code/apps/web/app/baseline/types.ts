export type MetricKey =
  | "requests"
  | "revenue"
  | "fill_rate"
  | "render_rate"
  | "ctr"
  | "ecpm"
  | "rpr";

export interface ChartPoint {
  time: string;
  actual: number;
  expected: number | null;
  lower: number | null;
  upper: number | null;
  anomalous: boolean;
}

export interface SegmentSignal {
  dimension: string;
  segment: string;
  methods: string[];
  maxAbsZ: number;
  pctDelta: number | null;
}

export interface SegmentEvidence {
  dimension: string;
  segment: string;
  peakZ: number;
  meanZ: number;
  globalPeakZ: number;
  globalMeanZ: number;
  incidentCorrelation: number | null;
  incidentCorrelationN: number;
  baselineCorrelation: number | null;
  baselineCorrelationN: number;
  directionMatchPct: number;
  scoredHours: number;
  quietHours: number;
}

export interface Incident {
  id: string;
  metric: MetricKey;
  methods: string[];
  startTime: string;
  endTime: string;
  detectedAt: string;
  flaggedHours: number;
  maxAbsZ: number;
  observed: number | null;
  expected: number | null;
  pctDelta: number | null;
  series: ChartPoint[];
  segmentSignals: SegmentSignal[];
  segmentEvidence: SegmentEvidence[];
  relatedMetrics: MetricKey[];
}

export interface Metric {
  key: MetricKey;
  value: number;
  expected: number | null;
  delta: number | null;
  tone: "bad" | "warn" | "ok";
  incidentId: string | null;
  series: ChartPoint[];
}

export interface DashboardData {
  incidents: Incident[];
  metrics: Metric[];
  rawSignalCount: number;
  generatedAt: string;
  error?: string;
}

export interface ChatMessage {
  who: "user" | "bot";
  text: string;
  tools?: ChatToolCall[];
}

export interface ChatToolCall {
  name: string;
  input?: unknown;
  output?: unknown;
  error?: string;
  state: string;
}

export type AnalysisVerdictLabel =
  | "confirmed_anomaly"
  | "likely_anomaly"
  | "inconclusive"
  | "false_positive";

export interface AnalysisVerdict {
  label: AnalysisVerdictLabel;
  summary: string;
  confidence: number;
  severity: "low" | "medium" | "high" | "critical";
}

export interface SliceAndDiceFinding {
  slice: string;
  finding: string;
  evidence: string;
}

export interface IncidentAnalysis {
  incidentId: string;
  status: "running" | "completed" | "failed";
  verdict?: AnalysisVerdict;
  sliceAndDice: SliceAndDiceFinding[];
  toolCalls: ChatToolCall[];
  agentSessionId?: string;
  error?: string;
  updatedAt: string;
}
