import { IChartConfig, IMetric } from "../../components/Insight";

export const bigNumberChartConfigResolver = async (metrics: IMetric[]): Promise<IChartConfig> => {
  const chartsConfig = {
    stat: {
      dataKey: metrics[0]?.metricLabel,
    },
  };
  return chartsConfig;
};
