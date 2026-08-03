import React from "react";
import { getChange, getSum, valueFormatter } from "../../utils/general.util";
import { CompactBigNumber } from "./components/CompactBigNumber";
import { getCurrLabel } from "./utils/bigNumber.util";
import { Loader } from "../../common/Loader";
import { ExpandedBigNumber } from "./components/ExpandedBigNumber";
import { TimeGrainAPIKey } from "../../constants/date.constant";
import { IChartProps } from "../../components/Insight";
import { Stat } from "./components/Stat";
import { Change } from "./components/Change";

const BigNumber: React.FC<IChartProps> = ({ data, loading = false, timeGrain, chartsConfig, options }) => {
  const { compact, expanded, micro, hideCard, periodLabel, vsLabel, currentWindowLabel, align, className } = options || {};

  if (loading) {
    return <Loader className={`${expanded ? "min-h-20" : ""} h-full`} loaderSize={micro ? "w-4 h-4" : null} />;
  }

  if (!timeGrain || !chartsConfig?.stat || !data || data.length === 0) {
    return (
      <div className={`w-full h-full flex ${compact && hideCard ? "justify-start" : "justify-center"} items-center`}>
        <p className="text-gray-500 text-xs">No data</p>
      </div>
    );
  }

  const metricLabel = chartsConfig.stat.dataKey;
  const metricCurrValue = getSum(data[data.length - 1], [metricLabel]);
  const metricPrevValue = getSum(data[data.length - 2], [metricLabel]);
  const metricChange = getChange(data, [metricLabel]);
  const metricChangeType = metricChange > 0 ? "positive" : "negative";

  if (micro)
    return (
      <div className="flex items-center justify-center gap-1">
        <CompactBigNumber
          number={valueFormatter(metricCurrValue)}
          label={metricLabel}
          hideLabel={true}
          numberFont="text-xs"
          className="w-auto"
        />
        <Change change={metricChange} changeType={metricChangeType} className="text-[11px]" />
      </div>
    );

  if (compact)
    return (
      <CompactBigNumber number={valueFormatter(metricCurrValue)} label={metricLabel} hideLabel={options?.hideTitle} />
    );

  if (expanded)
    return (
      <ExpandedBigNumber
        data={data}
        value={metricCurrValue}
        prevValue={metricPrevValue}
        change={metricChange}
        changeType={metricChangeType}
        timeGrain={timeGrain}
      />
    );

  return (
    <Stat
      label={getCurrLabel(data, timeGrain)}
      value={metricCurrValue}
      change={metricChange}
      changeType={metricChangeType}
      interval={vsLabel ?? `last ${TimeGrainAPIKey[timeGrain]}`}
      align={align ?? "center"}
      className={className}
      periodLabel={periodLabel}
      currentWindowLabel={currentWindowLabel}
    />
  );
};

export default BigNumber;
