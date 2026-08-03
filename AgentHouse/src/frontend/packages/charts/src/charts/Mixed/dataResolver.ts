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

export const getApiCalls = (
  metrics: IMetric[],
  timeGrain: TimeGrain,
  timeRange: number,
  filters: IFilters | null,
  dataResolver: IDataResolver
) => {
  const apiCalls: Promise<IDataResolverResponse>[] = [];

  metrics.forEach((metric) => {
    const metricFilters = filters?.[metric.metricKey];
    const { fromtime, totime } = getDateRange(timeRange, timeGrain);
    const { showDimensionContributionIn, compareWith, dimensionFilters } = metricFilters as IMetricFilters || {};

    if (showDimensionContributionIn || compareWith) {
      if (showDimensionContributionIn)
        apiCalls.push(
          dataResolver({
            payload: {
              fromtime,
              totime,
              metric_name: metric.metricKey,
              timegrain: TimeGrainAPIKey[timeGrain],
              dimensions: [showDimensionContributionIn],
              filters: dimensionFilters ?? [],
            },
            insight_type: "contributor",
          })
        );

      if (compareWith)
        apiCalls.push(
          dataResolver({
            payload: {
              fromtime,
              totime,
              metric_name: metric.metricKey,
              timegrain: TimeGrainAPIKey[timeGrain],
              filters: dimensionFilters ?? [],
            },
            insight_type: "comparison",
          })
        );
    } else {
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
        })
      );
    }
  });

  return apiCalls;
};

export const transformResponses = (
  responses: IDataResolverResponse[],
  metrics: IMetric[],
  timeGrain: TimeGrain,
  index: string = "date",
  sortKey: string = "fromtime"
): IDataResolverResponse => {
  let interpretations: string[] = [];
  let data: { [date: string]: IEntry } = {};

  responses.forEach(({ data: response, interpretation }) => {
    response.forEach((e: IEntry) => (e.date = shortenDate(e.fromtime, e.totime, timeGrain)));
    response.forEach((e: IEntry) => {
      const key: string | number = e[index] ?? "";
      metrics.forEach((metric: IMetric) => {
        const metricLabel: string = metric.metricLabel;
        if (!data?.[key]?.[metricLabel])
          data[key] = {
            ...e,
            ...(data[key] ?? {}),
            [metric.metricLabel]: e[metric.metricKey] ?? 0,
          };
      });
    });
    interpretations = [...interpretations, (interpretation ?? "")];
  });

  return {
    data: Object.values(data).sort((a: IEntry, b: IEntry) => {
      if (new Date(a[sortKey]) < new Date(b[sortKey])) return -1;
      if (new Date(a[sortKey]) > new Date(b[sortKey])) return 1;
      return 0;
    }),
    interpretation: interpretations[0],
  };
};

export const mixedDataResolver = async (
  metrics: IMetric[],
  timeGrain: TimeGrain,
  timeRange: number,
  filters: IFilters,
  dataResolver: IDataResolver
): Promise<IDataResolverResponse> => {
  return Promise.all(getApiCalls(metrics, timeGrain, timeRange, filters, dataResolver))
    .then((responses) => transformResponses(responses, metrics, timeGrain))
    .catch(() => ({ data: [], query: "", interpretation: "" }));
};
