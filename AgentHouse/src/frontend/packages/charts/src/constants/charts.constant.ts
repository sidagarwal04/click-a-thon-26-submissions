import BigNumber from "../charts/BigNumber";
import BigNumberWithTrend from "../charts/BigNumberWithTrend";
import Funnel from "../charts/Funnel";
import MixedChart from "../charts/Mixed";
import Pivot from "../charts/Pivot";
import Ranking from "../charts/Ranking";
import Table from "../charts/Table";
import XMR from "../charts/XMR";

export enum ChartTypes {
  BIGNUMBER = "BIGNUMBER",
  BIGNUMBERWITHTREND = "BIGNUMBERWITHTREND",
  MIXED = "MIXED",
  AREA = "AREA",
  BAR = "BAR",
  LINE = "LINE",
  RANKING = "RANKING",
  XMR = "XMR",
  PIVOT = "PIVOT",
  TABLE = "TABLE",
  FUNNEL = "FUNNEL",
}

export const ChartMap = {
  [ChartTypes.BIGNUMBER]: BigNumber,
  [ChartTypes.BIGNUMBERWITHTREND]: BigNumberWithTrend,
  [ChartTypes.MIXED]: MixedChart,
  [ChartTypes.BAR]: MixedChart,
  [ChartTypes.LINE]: MixedChart,
  [ChartTypes.AREA]: MixedChart,
  [ChartTypes.RANKING]: Ranking,
  [ChartTypes.XMR]: XMR,
  [ChartTypes.PIVOT]: Pivot,
  [ChartTypes.TABLE]: Table,
  [ChartTypes.FUNNEL]: Funnel,
};
