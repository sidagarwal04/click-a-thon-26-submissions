import { bigNumberDataResolver } from "../charts/BigNumber/dataResolver";
import { funnelDataResolver } from "../charts/Funnel/dataResolver";
import { mixedDataResolver } from "../charts/Mixed/dataResolver";
import { pivotDataResolver } from "../charts/Pivot/dataResolver";
import { rankingDataResolver } from "../charts/Ranking/dataResolver";
import { tableDataResolver } from "../charts/Table/dataResolver";
import { xmrDataResolver } from "../charts/XMR/dataResolver";
import { ChartTypes } from "./charts.constant";

export const DataResolverMap = {
  [ChartTypes.BIGNUMBER]: bigNumberDataResolver,
  [ChartTypes.BIGNUMBERWITHTREND]: mixedDataResolver,
  [ChartTypes.MIXED]: mixedDataResolver,
  [ChartTypes.BAR]: mixedDataResolver,
  [ChartTypes.LINE]: mixedDataResolver,
  [ChartTypes.AREA]: mixedDataResolver,
  [ChartTypes.RANKING]: rankingDataResolver,
  [ChartTypes.XMR]: xmrDataResolver,
  [ChartTypes.PIVOT]: pivotDataResolver,
  [ChartTypes.TABLE]: tableDataResolver,
  [ChartTypes.FUNNEL]: funnelDataResolver,
};
