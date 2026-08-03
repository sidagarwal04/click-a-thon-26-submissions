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

export const transformResponses = (
  response: IDataResolverResponse,
  metric: IMetric,
  timeGrain: TimeGrain,
  index: string = "date",
  sortKey: string = "fromtime"
): IDataResolverResponse => {
  let data: { [date: string]: IEntry } = {};

  response.data.forEach((e: IEntry) => (e.date = shortenDate(e.fromtime, e.totime, timeGrain)));
  response.data.forEach((e: IEntry) => {
    const key: string | number = e[index] ?? "";
    const metricLabel: string = metric.metricLabel;
    if (!data?.[key]?.[metricLabel])
      data[key] = {
        ...e,
        ...(data[key] ?? {}),
        [metric.metricLabel]: e[metric.metricKey] ?? 0,
      };
  });

  return {
    data: Object.values(data).sort((a: IEntry, b: IEntry) => {
      if (new Date(a[sortKey]) < new Date(b[sortKey])) return -1;
      if (new Date(a[sortKey]) > new Date(b[sortKey])) return 1;
      return 0;
    }),
    interpretation: response.interpretation,
  };
};

export const bigNumberDataResolver = async (
  [metric]: IMetric[],
  timeGrain: TimeGrain,
  timeRange: number,
  filters: IFilters,
  dataResolver: IDataResolver
): Promise<IDataResolverResponse> => {
  const { fromtime, totime } = getDateRange(timeRange, timeGrain);
  return dataResolver({
    payload: {
      fromtime,
      totime,
      metric_name: metric.metricKey,
      timegrain: TimeGrainAPIKey[timeGrain],
      filters: (filters[metric.metricKey] as IMetricFilters)?.dimensionFilters ?? [],
    },
    insight_type: "summary",
  })
    .then((response) => transformResponses(response, metric, timeGrain))
    .catch(() => ({ data: [], query: "", interpretation: "" }));
};
