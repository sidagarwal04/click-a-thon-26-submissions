import {
  IDataResolver,
  IDataResolverResponse,
  IEntry,
  IFilters,
  IMetric,
  IMetricFilters,
} from "../../components/Insight";
import { TimeGrain, TimeGrainAPIKey } from "../../constants/date.constant";
import { getDateRange, shortenDate } from "../../utils/date.util";

const META_KEYS = new Set(["fromtime", "totime", "date", "name", "value", "retentionRate", "baseTotal"]);

function resolveDimension(metrics: IMetric[], filters: IFilters | null): string | undefined {
  for (const metric of metrics) {
    const dimension = (filters?.[metric.metricKey] as IMetricFilters | undefined)
      ?.showDimensionContributionIn;
    if (dimension) {
      return dimension;
    }
  }
  return undefined;
}

function numericFields(entry: IEntry): Record<string, number> {
  const fields: Record<string, number> = {};
  for (const [key, value] of Object.entries(entry)) {
    if (META_KEYS.has(key) || key.startsWith("__abs_")) {
      continue;
    }
    const parsed = typeof value === "number" ? value : parseFloat(String(value));
    if (!Number.isNaN(parsed)) {
      fields[key] = parsed;
    }
  }
  return fields;
}

export const getApiCalls = (
  metrics: IMetric[],
  timeGrain: TimeGrain,
  timeRange: number,
  filters: IFilters | null,
  dataResolver: IDataResolver,
) => {
  const apiCalls: Promise<IDataResolverResponse>[] = [];
  const dimension = resolveDimension(metrics, filters);
  const { fromtime, totime } = getDateRange(timeRange, timeGrain);

  metrics.forEach((metric) => {
    const metricFilters = filters?.[metric.metricKey] as IMetricFilters | undefined;
    const { dimensionFilters } = metricFilters ?? {};

    if (dimension) {
      apiCalls.push(
        dataResolver({
          payload: {
            fromtime,
            totime,
            metric_name: metric.metricKey,
            timegrain: TimeGrainAPIKey[timeGrain],
            dimensions: [dimension],
            filters: dimensionFilters ?? [],
          },
          insight_type: "contributor",
        }),
      );
      return;
    }

    apiCalls.push(
      dataResolver({
        payload: {
          fromtime,
          totime,
          metric_name: metric.metricKey,
          timegrain: TimeGrainAPIKey[timeGrain],
          filters: dimensionFilters ?? [],
        },
        insight_type: "trend",
      }),
    );
  });

  return apiCalls;
};

export const transformResponses = (
  responses: IDataResolverResponse[],
  metrics: IMetric[],
  timeGrain: TimeGrain,
  index: string = "date",
  sortKey: string = "fromtime",
): IDataResolverResponse => {
  let interpretations: string[] = [];
  let data: { [date: string]: IEntry } = {};

  responses.forEach(({ data: response, interpretation }) => {
    response.forEach((e: IEntry) => (e.date = shortenDate(e.fromtime, e.totime, timeGrain)));
    response.forEach((e: IEntry) => {
      const key: string | number = e[index] ?? "";
      metrics.forEach((metric: IMetric) => {
        if (!data?.[key]?.[metric.metricLabel])
          data[key] = {
            ...e,
            ...(data[key] ?? {}),
            [metric.metricLabel]: e[metric.metricKey] ?? 0,
          };
      });
    });
    interpretations = [...interpretations, interpretation ?? ""];
  });

  return {
    data: Object.values(data).sort((a: IEntry, b: IEntry) => {
      if (new Date(a[sortKey] as string) < new Date(b[sortKey] as string)) return -1;
      if (new Date(a[sortKey] as string) > new Date(b[sortKey] as string)) return 1;
      return 0;
    }),
    interpretation: interpretations[0],
  };
};

const transformContributorResponses = (
  responses: IDataResolverResponse[],
  metrics: IMetric[],
): IDataResolverResponse => {
  const rows: IEntry[] = metrics.map((metric, index) => {
    const response = responses[index]?.data ?? [];
    const entry = response[response.length - 1] ?? {};
    const dims = numericFields(entry);
    const value = Object.values(dims).reduce((sum, n) => sum + n, 0);

    return {
      name: metric.metricLabel,
      value,
      ...dims,
      fromtime: entry.fromtime,
      totime: entry.totime,
    };
  });

  return {
    data: rows,
    interpretation: responses[0]?.interpretation ?? "",
  };
};

export const funnelDataResolver = async (
  metrics: IMetric[],
  timeGrain: TimeGrain,
  timeRange: number,
  filters: IFilters,
  dataResolver: IDataResolver,
): Promise<IDataResolverResponse> => {
  const dimension = resolveDimension(metrics, filters);

  return Promise.all(getApiCalls(metrics, timeGrain, timeRange, filters, dataResolver))
    .then((responses) =>
      dimension
        ? transformContributorResponses(responses, metrics)
        : transformResponses(responses, metrics, timeGrain),
    )
    .catch(() => ({ data: [], query: "", interpretation: "" }));
};
