import { IChartConfig, IFilters, IMetric } from "../../components/Insight";

export const rankingChartConfigResolver = async (
  [metric]: IMetric[],
  filters: IFilters
): Promise<IChartConfig> => {
  const chartsConfig = {
    ranking: {
      dimension: filters[metric.metricKey]?.showDimensionContributionIn,
    },
  };
  return chartsConfig;
};
