import { IChartConfig, IDimensionValuesResolver, IFilters, IMetric } from "../../components/Insight";


export const pivotChartConfigResolver = async (
  [metric]: IMetric[],
  filters: IFilters,
  dimensionValuesResolver: IDimensionValuesResolver,
): Promise<IChartConfig> => {
  try{
    const { showPivotIn } = filters[metric.metricKey] ?? {};
    const chartsConfig = {
        pivot: {
            rowValues: [],
            colValues: [],
            row: "",
            col: "",
            metric: ""
        },
    };

   if (!showPivotIn?.row || !showPivotIn?.column)
        throw new Error("Pivot chart requires 2 dimensions");

    const {row, column} = showPivotIn;
    const rowDimensionValues = await dimensionValuesResolver(row);
    const colDimensionValues = await dimensionValuesResolver(column);
    
    chartsConfig.pivot.metric = metric.metricKey;
    chartsConfig.pivot.rowValues = rowDimensionValues;
    chartsConfig.pivot.colValues = colDimensionValues;
    chartsConfig.pivot.row = row;
    chartsConfig.pivot.col = column;
    return chartsConfig;
  }catch(e){
    return {
        pivot: {
            rowValues: [],
            colValues: [],
            row: "",
            col: "",
            metric: ""
        },
    };;
  }
};
