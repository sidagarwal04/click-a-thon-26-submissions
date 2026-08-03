import { bigNumberChartConfigResolver } from "../charts/BigNumber/chartConfigResolver";
import { bigNumWithTrendChartConfigResolver } from "../charts/BigNumberWithTrend/chartConfigResolver";
import { funnelChartConfigResolver } from "../charts/Funnel/chartConfigResolver";
import { mixedChartConfigResolver } from "../charts/Mixed/chartConfigResolver";
import { pivotChartConfigResolver } from "../charts/Pivot/chartConfigResolver";
import { rankingChartConfigResolver } from "../charts/Ranking/chartConfigResolver";
import { tableChartConfigResolver } from "../charts/Table/chartConfigResolver";
import { xmrChartConfigResolver } from "../charts/XMR/chartConfigResolver";
import { ChartTypes } from "./charts.constant";

export const ChartConfigResolverMap = {
  [ChartTypes.BIGNUMBER]: bigNumberChartConfigResolver,
  [ChartTypes.BIGNUMBERWITHTREND]: bigNumWithTrendChartConfigResolver,
  [ChartTypes.MIXED]: mixedChartConfigResolver,
  [ChartTypes.BAR]: mixedChartConfigResolver,
  [ChartTypes.LINE]: mixedChartConfigResolver,
  [ChartTypes.AREA]: mixedChartConfigResolver,
  [ChartTypes.RANKING]: rankingChartConfigResolver,
  [ChartTypes.XMR]: xmrChartConfigResolver,
  [ChartTypes.PIVOT]: pivotChartConfigResolver,
  [ChartTypes.TABLE]: tableChartConfigResolver,
  [ChartTypes.FUNNEL]: funnelChartConfigResolver,
};
