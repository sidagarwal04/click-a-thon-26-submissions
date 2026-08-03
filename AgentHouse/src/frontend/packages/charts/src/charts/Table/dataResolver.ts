import {
  IDataResolver,
  IDataResolverResponse,
  IFilters,
  IMetric,
  IMetricFilters,
} from "../../components/Insight";
import { TimeGrain } from "../../constants/date.constant";
import { getDateRange } from "../../utils/date.util";

export const tableDataResolver = async (
  metrics: IMetric[],
  timeGrain: TimeGrain,
  timeRange: number,
  filters: IFilters,
  dataResolver: IDataResolver
): Promise<IDataResolverResponse> => {
  const { fromtime, totime } = getDateRange(timeRange, timeGrain);
  const { showTableIn } = filters ?? {};

  let dimensionFilters = [];
  const metricKey = metrics.find(({ metricKey }) => (filters?.[metricKey] as IMetricFilters)?.dimensionFilters?.length > 0)?.metricKey;
  if(metricKey) dimensionFilters = (filters?.[metricKey] as IMetricFilters)?.dimensionFilters;
  

  if (!showTableIn) return { data: [] };
  if (!metrics?.length) return { data: [] };

  return dataResolver({
    payload: {
      fromtime: fromtime,
      totime: totime,
      metrics: metrics.map(({ metricKey }) => metricKey),
      dimensions: [showTableIn],
      filters: dimensionFilters,
    },
    insight_type: "table",
  })
    .then(({ data, interpretation }) => ({
      data,
      interpretation,
    }))
    .catch(() => ({ data: [], interpretation: "", query: "" }));
};
