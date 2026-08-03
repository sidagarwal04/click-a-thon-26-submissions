export type SupportedMetric = {
  id: string;
  label: string;
  description: string;
  aliases: string[];
  isRatio: boolean;
};

export const DEFAULT_METRIC = "revenue";

export const SUPPORTED_METRICS: SupportedMetric[] = [
  { id: "revenue", label: "Revenue", description: "Money earned on impressions.", aliases: ["revenue"], isRatio: false },
];

export function detectMetricFromText(text: string): string | undefined {
  const normalized = text.toLowerCase();
  for (const metric of SUPPORTED_METRICS) {
    if (metric.aliases.some((alias) => normalized.includes(alias.toLowerCase()))) {
      return metric.id;
    }
  }
  return undefined;
}