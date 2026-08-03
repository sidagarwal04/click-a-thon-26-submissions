import {
  IDataResolver,
  IDataResolverResponse,
  IFilters,
  IMetric,
  IMetricFilters,
} from "../../components/Insight";
import { TimeGrain } from "../../constants/date.constant";
import { getDateRange } from "../../utils/date.util";

export const pivotDataResolver = async (
  [metric]: IMetric[],
  timeGrain: TimeGrain,
  timeRange: number,
  filters: IFilters,
  dataResolver: IDataResolver
): Promise<IDataResolverResponse> => {
  const { fromtime, totime } = getDateRange(timeRange, timeGrain);
  const { dimensionFilters = [], showPivotIn } = filters[metric?.metricKey] as IMetricFilters ?? {};

  if (!showPivotIn?.row || !showPivotIn?.column) return { data: [] };
  if (!metric?.metricKey) return { data: [] };

  return dataResolver({
    payload: {
      fromtime: fromtime,
      totime: totime,
      metric_name: metric.metricKey,
      dimensions: [showPivotIn.row, showPivotIn.column],
      filters: dimensionFilters,
    },
    insight_type: "pivot",
  })
    .then(({ data, interpretation }) => ({
      data,
      interpretation,
    }))
    .catch(() => ({ data: [], interpretation: "", query: "" }));
};
