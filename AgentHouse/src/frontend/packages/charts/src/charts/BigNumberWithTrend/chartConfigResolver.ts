import { IChartConfig, IMetric } from "../../components/Insight";
import { ColorPalette } from "../../constants/color.constant";

export const bigNumWithTrendChartConfigResolver = async (
  metrics: IMetric[]
): Promise<IChartConfig> => {
  const chartsConfig = {
    stat: {
      dataKey: metrics[0]?.metricLabel,
      unit: metrics[0]?.metricUnit,
    },
    areas: [
      {
        color: ColorPalette.PALE_BLUE,
        dataKey: metrics[0].metricKey,
      },
    ],
  };
  return chartsConfig;
};
