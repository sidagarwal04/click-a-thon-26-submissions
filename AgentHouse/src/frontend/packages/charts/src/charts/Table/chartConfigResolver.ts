import { IChartConfig, IDimensionValuesResolver, IFilters, IMetric } from "../../components/Insight";


export const tableChartConfigResolver = async (
  metrics: IMetric[],
  filters: IFilters,
  dimensionValuesResolver: IDimensionValuesResolver,
): Promise<IChartConfig> => {
  try{
    const chartsConfig = {
        table: {
            dimension: "",
            dimensionValues: [],
            metrics: [],
        },
    };

    const { showTableIn } = filters ?? {};

    if (!showTableIn || !metrics?.length)
        throw new Error("Please select a dimension and metrics to show table");

    const dimensionValues = await dimensionValuesResolver(showTableIn);
    
    chartsConfig.table.dimension = showTableIn;
    chartsConfig.table.dimensionValues = dimensionValues;
    chartsConfig.table.metrics = metrics;

    return chartsConfig;
  }catch(e){
    return {
        table: {
            dimension: "",
            dimensionValues: [],
            metrics: [],
        },
    };
  }
};
