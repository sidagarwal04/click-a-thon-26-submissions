import { shuffle } from "../../utils/general.util";
import { ChartTypes } from "../../constants/charts.constant";
import { ColorPalette } from "../../constants/color.constant";
import {
  IChartConfig,
  IDimensionValuesResolver,
  IFilters,
  IMetric,
  IMetricFilters,
} from "../../components/Insight";

const colors = shuffle(Object.values(ColorPalette));

const getBarConfig = (metric: IMetric, index: number, splitDimensionValues: string[]) => {
  if (splitDimensionValues) {
    return splitDimensionValues.map((dimensionValue, i) => ({
      dataKey: dimensionValue,
      color: colors[(index + i) % colors.length],
      stackId: metric?.stackId ?? "1",
    }));
  }
  return [
    {
      dataKey: metric.metricLabel,
      color: colors[index],
      stackId: metric?.stackId,
    },
  ];
};

const getLineConfig = (metric: IMetric, index: number, splitDimensionValues: string[]) => {
  if (splitDimensionValues) {
    return splitDimensionValues.map((dimensionValue, i) => ({
      dataKey: dimensionValue,
      color: colors[(index + i) % colors.length],
    }));
  }
  return [
    {
      dataKey: metric.metricLabel,
      color: colors[index],
      yAxisId: metric.yAxisId,
    },
  ];
};

const getAreaConfig = (metric: IMetric, index: number, splitDimensionValues: string[]) => {
  if (splitDimensionValues) {
    return splitDimensionValues.map((dimensionValue, i) => ({
      dataKey: dimensionValue,
      color: colors[(index + i) % colors.length],
    }));
  }
  return [
    {
      dataKey: metric.metricLabel,
      color: colors[index],
    },
  ];
};

export const mixedChartConfigResolver = async (
  metrics: IMetric[],
  filters: IFilters,
  dimensionValuesResolver: IDimensionValuesResolver,
  type: ChartTypes
): Promise<IChartConfig> => {
  const chartsConfig = {
    bars: [],
    lines: [],
    areas: [],
  };

  const configPromises = metrics.map(async (metric, index) => {
    let splitDimensionValues = null;
    let chartType = metric.chartType || type;
    let { compareWith, showDimensionContributionIn } = filters[metric.metricKey] as IMetricFilters ?? {};

    if (showDimensionContributionIn)
      splitDimensionValues = await dimensionValuesResolver(showDimensionContributionIn);

    switch (chartType) {
      case ChartTypes.BAR: {
        chartsConfig.bars.push(...getBarConfig(metric, index, splitDimensionValues));
        break;
      }
      case ChartTypes.LINE: {
        chartsConfig.lines.push(...getLineConfig(metric, index, splitDimensionValues));
        break;
      }
      case ChartTypes.AREA: {
        chartsConfig.areas.push(...getAreaConfig(metric, index, splitDimensionValues));
        break;
      }
    }

    if (compareWith)
      compareWith?.forEach((option, index) => {
        chartsConfig.lines.push({
          dataKey: option,
          color: colors[(index + 3) % colors.length],
        });
      });
  });

  await Promise.all(configPromises);
  return chartsConfig;
};
