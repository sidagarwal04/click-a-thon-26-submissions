import {
  IDataResolver,
  IDataResolverResponse,
  IEntry,
  IFilters,
  IMetric,
  IMetricFilters,
} from "../../components/Insight";
import { TimeGrain } from "../../constants/date.constant";
import { getDateRange } from "../../utils/date.util";

const transformData = (data: IEntry[]): IEntry[] => {
  const arr = [];

  let sum = 0;
  for (let key in data[0]) {
    if (key == "fromtime" || key == "totime") continue;
    try {
      sum += parseFloat((data[0][key] ?? 0) + "");
    } catch (e) {
      sum += 0;
    }
  }

  for (const key in data[0]) {
    const obj: IEntry = {
      segment: "",
      value: 0,
      percentage: 0,
    };

    if (key !== "fromtime" && key !== "totime") {
      obj.segment = key;
      try {
        obj.value = parseFloat((data[0][key] ?? 0) + "");
      } catch (e) {
        obj.value = 0;
      }
      obj.percentage = (obj.value / sum) * 100;
      arr.push(obj);
    }
  }

  return arr;
};

export const rankingDataResolver = async (
  [metric]: IMetric[],
  timeGrain: TimeGrain,
  timeRange: number,
  filters: IFilters,
  dataResolver: IDataResolver
): Promise<IDataResolverResponse> => {
  const { fromtime, totime } = getDateRange(timeRange, timeGrain);

  return dataResolver({
    payload: {
      fromtime: fromtime,
      totime: totime,
      metric_name: metric.metricKey,
      dimensions: [(filters[metric.metricKey] as IMetricFilters)?.showDimensionContributionIn],
      filters: (filters[metric.metricKey] as IMetricFilters)?.dimensionFilters ?? [],
    },
    insight_type: "contributor",
  })
    .then(({ data, interpretation }) => ({ data: transformData(data), interpretation }))
    .catch(() => ({ data: [], interpretation: "", query: "" }));
};
