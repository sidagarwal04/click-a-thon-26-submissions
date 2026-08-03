import { shuffle } from "../../utils/general.util";
import { ColorPalette } from "../../constants/color.constant";
import {
  IChartConfig,
  IDimensionValuesResolver,
  IFilters,
  IMetric,
  IMetricFilters,
} from "../../components/Insight";

const colors = shuffle(Object.values(ColorPalette));

function resolveDimension(metrics: IMetric[], filters: IFilters): string | undefined {
  for (const metric of metrics) {
    const dimension = (filters?.[metric.metricKey] as IMetricFilters | undefined)
      ?.showDimensionContributionIn;
    if (dimension) {
      return dimension;
    }
  }
  return undefined;
}

export const funnelChartConfigResolver = async (
  metrics: IMetric[],
  filters: IFilters = {},
  dimensionValuesResolver?: IDimensionValuesResolver,
): Promise<IChartConfig> => {
  const stages = metrics.map((metric) => ({
    label: metric.metricLabel,
    key: metric.metricKey,
  }));

  const dimension = resolveDimension(metrics, filters);
  if (!dimension || !dimensionValuesResolver) {
    return { funnel: { stages } };
  }

  const dimensionValues = await dimensionValuesResolver(dimension);
  return {
    funnel: {
      stages,
      dimension,
      segments: dimensionValues.map((dataKey, index) => ({
        dataKey,
        color: colors[index % colors.length],
      })),
    },
  };
};
