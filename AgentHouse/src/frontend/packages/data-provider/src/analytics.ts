import { z } from 'zod';

export const analyticsInsightTypeSchema = z.enum(['Trend', 'Ranking', 'Pivot', 'Funnel']);
export type AnalyticsInsightType = z.infer<typeof analyticsInsightTypeSchema>;

export const analyticsTimeGrainSchema = z.enum(['DAILY', 'WEEKLY', 'MONTHLY']);
export type AnalyticsTimeGrain = z.infer<typeof analyticsTimeGrainSchema>;

export const analyticsMetricSchema = z.object({
  metric_name: z.string().min(1),
  metric_label: z.string().min(1),
});
export type AnalyticsMetric = z.infer<typeof analyticsMetricSchema>;

export const analyticsTextBlockSchema = z.object({
  type: z.literal('text'),
  text: z.string(),
});
export type AnalyticsTextBlock = z.infer<typeof analyticsTextBlockSchema>;

/** Metadata-only insight block — chart data is fetched via SDK dataResolver. */
export const analyticsInsightBlockSchema = z.object({
  type: z.literal('insight'),
  title: z.string().nullish(),
  caption: z.string().nullish(),
  insight_type: analyticsInsightTypeSchema,
  metrics: z.array(analyticsMetricSchema).min(1),
  dimensions: z.array(z.string()).nullish(),
  fromTime: z.string().min(1),
  toTime: z.string().min(1),
  timeGrain: analyticsTimeGrainSchema,
});
export type AnalyticsInsightBlock = z.infer<typeof analyticsInsightBlockSchema>;

export const analyticsBlockSchema = z.discriminatedUnion('type', [
  analyticsTextBlockSchema,
  analyticsInsightBlockSchema,
]);
export type AnalyticsBlock = z.infer<typeof analyticsBlockSchema>;

export const analyticsQueryMetaSchema = z.object({
  model: z.string().nullish(),
  latency_ms: z.number().int().nullish(),
  warnings: z.array(z.string()).nullish(),
});
export type AnalyticsQueryMeta = z.infer<typeof analyticsQueryMetaSchema>;

export const analyticsResponseSchema = z.object({
  blocks: z.array(analyticsBlockSchema).min(1),
  meta: analyticsQueryMetaSchema.nullish(),
});
export type AnalyticsResponse = z.infer<typeof analyticsResponseSchema>;

export const analyticsHistoryTurnSchema = z.object({
  role: z.enum(['user', 'assistant']),
  content: z.string(),
});
export type AnalyticsHistoryTurn = z.infer<typeof analyticsHistoryTurnSchema>;

/** Shared POST /api/analytics/query body. */
export const analyticsQueryRequestSchema = z.object({
  prompt: z.string().min(1),
  conversation_id: z.string().nullish(),
  history: z.array(analyticsHistoryTurnSchema).nullish(),
  tenant_id: z.string().nullish(),
  locale: z.string().nullish(),
});
export type AnalyticsQueryRequest = z.infer<typeof analyticsQueryRequestSchema>;

export const analyticsDimensionFilterSchema = z.object({
  key: z.string().min(1),
  value: z.string(),
});
export type AnalyticsDimensionFilter = z.infer<typeof analyticsDimensionFilterSchema>;

export const analyticsDataInsightTypeSchema = z.enum(['trend', 'contributor', 'pivot']);
export type AnalyticsDataInsightType = z.infer<typeof analyticsDataInsightTypeSchema>;

export const analyticsDataPayloadSchema = z.object({
  fromtime: z.string().min(1),
  totime: z.string().min(1),
  metric_name: z.string().min(1),
  timegrain: z.enum(['day', 'week', 'month']).nullish(),
  dimensions: z.array(z.string()).nullish(),
  filters: z.array(analyticsDimensionFilterSchema).nullish(),
});
export type AnalyticsDataPayload = z.infer<typeof analyticsDataPayloadSchema>;

export const analyticsDataRequestSchema = z.object({
  payload: analyticsDataPayloadSchema,
  insight_type: analyticsDataInsightTypeSchema,
});
export type AnalyticsDataRequest = z.infer<typeof analyticsDataRequestSchema>;

export const analyticsDataResponseSchema = z.object({
  data: z.array(z.record(z.union([z.string(), z.number(), z.null()]))),
  interpretation: z.string().nullish(),
  query: z.string().nullish(),
  latency_ms: z.number().nullish(),
});
export type AnalyticsDataResponse = z.infer<typeof analyticsDataResponseSchema>;

export const analyticsDimensionsRequestSchema = z.object({
  dimension: z.string().min(1),
  fromtime: z.string().nullish(),
  totime: z.string().nullish(),
  metric_name: z.string().nullish(),
  filters: z.array(analyticsDimensionFilterSchema).nullish(),
  tenant_id: z.string().nullish(),
});
export type AnalyticsDimensionsRequest = z.infer<typeof analyticsDimensionsRequestSchema>;

export const analyticsDimensionsResponseSchema = z.object({
  dimension: z.string(),
  values: z.array(z.string()),
  latency_ms: z.number().nullish(),
});
export type AnalyticsDimensionsResponse = z.infer<typeof analyticsDimensionsResponseSchema>;

/**
 * Persist payload for analytics turns.
 * Native POST /api/messages/:id rejects writes until a conversation already exists,
 * so analytics saves go through /api/analytics/persist (upserts convo + messages).
 */
export const analyticsPersistMessageSchema = z.object({
  messageId: z.string().uuid(),
  parentMessageId: z.string().min(1),
  conversationId: z.string().uuid(),
  text: z.string(),
  sender: z.string().min(1),
  isCreatedByUser: z.boolean(),
  endpoint: z.string().nullable().optional(),
  model: z.string().nullable().optional(),
  metadata: z.record(z.unknown()).optional(),
  error: z.boolean().optional(),
  unfinished: z.boolean().optional(),
  createdAt: z.string().optional(),
  updatedAt: z.string().optional(),
});
export type AnalyticsPersistMessage = z.infer<typeof analyticsPersistMessageSchema>;

export const analyticsPersistRequestSchema = z.object({
  conversationId: z.string().uuid(),
  title: z.string().min(1).max(1024),
  endpoint: z.string().nullable().optional(),
  model: z.string().nullable().optional(),
  messages: z.array(analyticsPersistMessageSchema).min(1),
});
export type AnalyticsPersistRequest = z.infer<typeof analyticsPersistRequestSchema>;

export const analyticsPersistResponseSchema = z.object({
  conversationId: z.string().uuid(),
  title: z.string(),
});
export type AnalyticsPersistResponse = z.infer<typeof analyticsPersistResponseSchema>;

/** Message metadata payload for analytics lego blocks. */
export type AnalyticsMessageMetadata = {
  blocks: AnalyticsBlock[];
};

/** Saved analytics report (hackathon: persisted in browser localStorage). */
export type AnalyticsReport = {
  id: string;
  title: string;
  conversationId: string;
  blocks: AnalyticsBlock[];
  createdAt: string;
  updatedAt: string;
};

export function isAnalyticsMessageMetadata(
  value: unknown,
): value is AnalyticsMessageMetadata {
  return analyticsResponseSchema.safeParse(value).success;
}
