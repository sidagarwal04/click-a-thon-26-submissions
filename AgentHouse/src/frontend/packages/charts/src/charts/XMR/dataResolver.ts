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

const transformData = (data: IEntry[], metric: IMetric, timeGrain: TimeGrain): IEntry[] => {
  return data?.map((e) => ({
    date: shortenDate(e.fromtime, e.totime, timeGrain),
    [metric.metricLabel]: e[metric.metricKey],
    "Upper Control Limit": e.ucl,
    "Lower Control Limit": e.lcl,
    Mean: e.mean,
  }));
};

export const xmrDataResolver = async (
  [metric]: IMetric[],
  timeGrain: TimeGrain,
  timeRange: number,
  filters: IFilters,
  dataResolver: IDataResolver
): Promise<IDataResolverResponse> => {
  const { fromtime, totime } = getDateRange(timeRange, timeGrain);
  const { dimensionFilters = [] } = filters[metric.metricKey] as IMetricFilters ?? {};
  return dataResolver({
    payload: {
      fromtime: fromtime,
      totime: totime,
      timegrain: TimeGrainAPIKey[timeGrain],
      metric_name: metric.metricKey,
      filters: dimensionFilters,
    },
    insight_type: "xmr",
  })
    .then(({ data, interpretation }) => ({
      data: transformData(data, metric, timeGrain),
      interpretation,
    }))
    .catch(() => ({ data: [], interpretation: "", query: "" }));
};
