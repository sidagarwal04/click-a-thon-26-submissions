import { useEffect, useMemo, useState } from "react";
import { ChartMap, ChartTypes } from "../constants/charts.constant";
import { TimeGrain } from "../constants/date.constant";
import { MenuItem } from "../common/PopUpMenu";
import { ChartContainer } from "../common/ChartContainer";
import { MdOutlineInsights } from "react-icons/md";
import { ChartConfigResolverMap } from "../constants/chartConfigResolvers.contant";
import { DataResolverMap } from "../constants/dataResolvers.constant";

export interface IMetricFilters {
  showDimensionContributionIn?: string;
  compareWith?: string[];
  showPivotIn?: {
    row: string;
    column: string;
  };
  dimensionFilters?: {
    key: string;
    value: string;
  }[];
}

export interface IFilters {
  showTableIn?: string;
  [key: string]: IMetricFilters | string;
}

export interface IOptions {
  hideTitle?: boolean;
  compact?: boolean;
  micro?: boolean;
  expanded?: boolean;
  hideCard?: boolean;
  className?: string;
  showExplanation?: boolean;
  /** Visual theme for chart text, borders, and surface. Defaults to light. */
  theme?: "light" | "dark";
  /** Custom period comparison label rendered in place of the default "vs last month/week" chip. */
  periodLabel?: string;
  /** Overrides the "vs last month/week" text — e.g. "March" or "last week". */
  vsLabel?: string;
  /** 4-line BigNumber layout: bottom window line — e.g. "April so far · Apr 1–4". */
  currentWindowLabel?: string;
  /** Alignment of BigNumber stat content: "start" | "center" | "end". Default "center". */
  align?: "start" | "center" | "end";
}

export interface IConfig {
  dataKey?: string;
  unit?: string;
  color?: string;
  stackId?: string;
  yAxisId?: string;
}

export interface IChartConfig {
  stat?: IConfig;
  lines?: IConfig[];
  areas?: IConfig[];
  bars?: IConfig[];
  ranking?: { dimension: string };
  pivot?: { rowValues: string[]; colValues: string[]; row: string; col: string; metric: string };
  table?: { dimension: string; dimensionValues: string[]; metrics: IMetric[] };
  funnel?: {
    stages: { label: string; key: string }[];
    dimension?: string;
    segments?: IConfig[];
  };
}

export interface IChartProps {
  data: IEntry[];
  chartsConfig: IChartConfig;
  loading?: boolean;
  filters?: IFilters | null;
  options?: IOptions;
  height?: string;
  width?: string;
  fontSize?: number;
  timeGrain?: TimeGrain;
}

export interface IEntry {
  date?: string;
  fromtime?: string;
  totime?: string;
  [key: string]: string | number;
}

export interface IDataResolverResponse {
  data: IEntry[];
  query?: string;
  interpretation?: string;
}

export interface IDataResolver {
  (payload: { payload: object; insight_type: string }): Promise<IDataResolverResponse>;
}

export interface IDimensionValuesResolver {
  (dimension: string): Promise<string[]>;
}

export interface IMetric {
  metricKey: string;
  metricLabel: string;
  metricUnit?: string;
  chartType?: ChartTypes;
  yAxisId?: string;
  stackId?: string;
}

export interface IInsightProps {
  type: ChartTypes;
  title?: string;
  description?: string;
  metrics: IMetric[];
  timeGrain?: TimeGrain;
  timeRange?: number;
  filters?: IFilters;
  options?: IOptions;
  actions?: MenuItem[];
  onClick?: () => void;
  onCheck?: (...args: any) => void;
  dataResolver?: IDataResolver;
  dimensionValuesResolver?: IDimensionValuesResolver;
  // Presentational mode: when `data` is supplied, the SDK skips dataResolver and renders the
  // bundled data directly. Used by Isotopes-style flows where the agent JSON already carries
  // every chart's data per atomic insight.
  data?: IEntry[];
  interpretation?: string;
}

function filtersEqual(a: IFilters, b: IFilters): boolean {
  const aKeys = Object.keys(a);
  const bKeys = Object.keys(b);
  if (aKeys.length !== bKeys.length) {
    return false;
  }
  for (const key of aKeys) {
    if (!(key in b)) {
      return false;
    }
    if (JSON.stringify(a[key]) !== JSON.stringify(b[key])) {
      return false;
    }
  }
  return true;
}

export const Insight = ({
  type,
  title,
  description,
  metrics,
  timeGrain: _timeGrain,
  timeRange: _timeRange,
  filters: _filters,
  options,
  actions,
  onClick,
  onCheck,
  dataResolver,
  dimensionValuesResolver,
  data: _dataProp,
  interpretation: _interpretationProp,
}: IInsightProps) => {
  const { className, showExplanation = false, hideCard = false, theme = "light" } = options ?? {};
  const Chart = useMemo(() => ChartMap[type], [type, metrics]);
  const themeClass = theme === "dark" ? "da-theme-dark" : "da-theme-light";
  const surfaceClass = "da-chart-surface";

  const [timeGrain, setTimeGrain] = useState<TimeGrain>(_timeGrain);
  const [timeRange, setTimeRange] = useState<number>(_timeRange);
  const [filters, setFilters] = useState<IFilters>();

  const [data, setData] = useState<IEntry[]>();
  const [chartConfig, setChartConfig] = useState<IChartConfig>();
  const [interpretation, setInterpretation] = useState<string>();

  useEffect(() => setTimeGrain(_timeGrain ?? TimeGrain.MONTHLY), [_timeGrain]);
  useEffect(() => setTimeRange(_timeRange ?? 180), [_timeRange]);
  useEffect(() => {
    const next = _filters ?? {};
    setFilters((prev) => (prev && filtersEqual(prev, next) ? prev : next));
  }, [_filters]);

  useEffect(() => {
    if (!filters) return;
    setChartConfig(undefined);
    const resolver = ChartConfigResolverMap[type];
    resolver?.(metrics, filters, dimensionValuesResolver, type).then((config: IChartConfig) => setChartConfig(config));
  }, [metrics, type, filters]);

  useEffect(() => {
    if (!filters) return;
    if (_dataProp !== undefined) {
      setData(_dataProp);
      setInterpretation(_interpretationProp);
      return;
    }
    setData(undefined);
    const resolver = DataResolverMap[type];
    resolver?.(metrics, timeGrain, timeRange, filters, dataResolver).then((res: IDataResolverResponse) => {
      setData(res.data);
      setInterpretation(res.interpretation);
    });
  }, [metrics, type, timeGrain, timeRange, filters, dataResolver, _dataProp, _interpretationProp]);

  if (hideCard)
    return (
      <div className={`w-full h-full flex flex-col ${themeClass} ${surfaceClass} ${className ?? ""}`}>
        <Chart
          data={data}
          filters={filters}
          chartsConfig={chartConfig}
          loading={!data || !chartConfig}
          options={options}
          timeGrain={timeGrain}
        />
      </div>
    );

  return (
    <ChartContainer
      title={title}
      description={description}
      className={`${themeClass} ${surfaceClass} ${className ?? ""}`}
      actions={actions}
      onClick={onClick}
      onCheck={onCheck}
    >
      <div className="flex flex-col h-full">
        <div className={`flex-1 ${showExplanation && interpretation?.[0] ? "min-h-0" : ""}`}>
          <Chart
            chartsConfig={chartConfig}
            filters={filters}
            data={data}
            loading={data === undefined || chartConfig === undefined}
            options={options}
            timeGrain={timeGrain}
          />
        </div>
        {showExplanation && interpretation && (
          <div className="flex-shrink-0 px-3 py-2 border-t border-gray-300">
            <div className="flex items-center gap-x-3 w-full max-h-12 overflow-auto">
              <MdOutlineInsights size={16} className="text-black" />
              <p className="text-xs text-gray-600 w-[95%]">{interpretation}</p>
            </div>
          </div>
        )}
      </div>
    </ChartContainer>
  );
};
