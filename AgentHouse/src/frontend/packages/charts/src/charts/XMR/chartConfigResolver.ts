import { IChartConfig, IFilters, IMetric } from "../../components/Insight";
import { ColorPalette } from "../../constants/color.constant";
import { shuffle } from "../../utils/general.util";

const colors = shuffle(Object.values(ColorPalette));

export const xmrChartConfigResolver = async (
  [metric]: IMetric[],
  filters: IFilters
): Promise<IChartConfig> => {
  const chartsConfig = {
    lines: [],
  };

  chartsConfig.lines.push({
    dataKey: metric.metricLabel,
    color: colors[0],
  });

  chartsConfig.lines.push({
    dataKey: "Lower Control Limit",
    color: colors[1],
  });

  chartsConfig.lines.push({
    dataKey: "Mean",
    color: colors[2],
  });

  chartsConfig.lines.push({
    dataKey: "Upper Control Limit",
    color: colors[3],
  });

  return chartsConfig;
};
