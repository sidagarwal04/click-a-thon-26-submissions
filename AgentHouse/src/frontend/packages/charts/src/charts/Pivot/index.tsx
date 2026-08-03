import { useState, useRef } from "react";
import { Loader } from "../../common/Loader";
import { FloatingTooltip } from "../../common/FloatingTooltip";
import { IChartProps, IEntry } from "../../components/Insight";
import { valueFormatter } from "../../utils/general.util";
import { PivotTooltip } from "./PivotTooltip";

type PivotData = {
  [row: string]: {
    [col: string]: number;
  };
};

const transformData = (data: IEntry[], row: string, col: string, metric: string): PivotData => {
  return data?.reduce<PivotData>((acc, item) => {
    const { [row]: rowValue, [col]: colValue, [metric]: value } = item;
    if (!acc[rowValue]) acc[rowValue] = {};
    acc[rowValue][colValue] = Number(value);
    return acc;
  }, {});
};

const Pivot: React.FC<IChartProps> = ({ chartsConfig, data, loading, options }) => {
  const [tooltip, setTooltip] = useState<{
    show: boolean;
    x: number;
    y: number;
    rowValue: string;
    colValue: string;
    value: number;
  } | null>(null);
  const tableRef = useRef<HTMLDivElement>(null);

  if (loading) return <Loader className="min-h-32 h-full" />;

  if (!chartsConfig?.pivot?.row || !chartsConfig?.pivot?.col || !chartsConfig?.pivot?.metric)
    return (
      <div className="flex text-center text-sm text-gray-500 h-full items-center justify-center">
        Select 2 dimensions to show pivot
      </div>
    );

  if (!chartsConfig?.pivot?.rowValues?.length || !chartsConfig?.pivot?.colValues?.length)
    return (
      <div className="flex text-center text-sm text-gray-500 h-full items-center justify-center">
        Dimension values are not available for selected dimensions
      </div>
    );

  if (!data || data.length === 0)
    return <div className="flex text-center text-sm text-gray-500 h-full items-center justify-center">No data</div>;

  const { rowValues, colValues, row, col, metric } = chartsConfig.pivot ?? {};
  const pivotData = transformData(data, row, col, metric);

  const getHeatMapColor = (value: number) => {
    const allValues = Object.values(pivotData)
      .flatMap((row) => Object.values(row))
      .map(Number);

    const minValue = Math.min(...allValues);
    const maxValue = Math.max(...allValues);
    const range = maxValue - minValue;
    const t = range === 0 ? 0.5 : (Number(value) - minValue) / range;

    // Muted rose (low) → muted sage (high) — subtle on dark UI
    const r = Math.round(148 + (72 - 148) * t);
    const g = Math.round(82 + (122 - 82) * t);
    const b = Math.round(88 + (108 - 88) * t);
    const alpha = 0.42 + t * 0.28;

    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
  };

  // Calculate dimensions - dynamic based on parent height
  const numRows = rowValues.length;
  const numCols = colValues.length;

  const headerRowHeight = "15px"; // Fixed height for header row
  const dataRowHeight = `calc((100% - ${headerRowHeight}) / ${numRows})`; // Remaining space divided by data rows

  const firstColWidth = "60px"; // Fixed width for row headers
  const dataColWidth = `calc((100% - ${firstColWidth}) / ${numCols})`; // Remaining space divided by data columns

  const handleMouseEnter = (e: React.MouseEvent, rowValue: string, colValue: string, value: number) => {
    setTooltip({
      show: true,
      x: e.clientX,
      y: e.clientY,
      rowValue,
      colValue,
      value,
    });
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    setTooltip((prev) =>
      prev
        ? {
            ...prev,
            x: e.clientX,
            y: e.clientY,
          }
        : null,
    );
  };

  const handleMouseLeave = () => {
    setTooltip(null);
  };

  return (
    <div className="w-full h-full relative" ref={tableRef}>
      <table className="table-fixed w-full h-full text-gray-600 text-xs text-center">
        <thead>
          <tr style={{ height: headerRowHeight }}>
            <th style={{ width: firstColWidth, height: headerRowHeight }}></th>
            {colValues.map((col) => (
              <th
                title={col}
                className="font-normal pb-1 truncate"
                key={col}
                style={{ width: dataColWidth, height: headerRowHeight }}
              >
                {col}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rowValues.map((row) => (
            <tr key={row} style={{ height: dataRowHeight }}>
              <td
                title={row}
                className="text-left pr-2 truncate"
                style={{ width: firstColWidth, height: dataRowHeight }}
              >
                {row}
              </td>
              {colValues.map((col) => (
                <td
                  key={col}
                  className="border border-gray-300 truncate cursor-pointer"
                  style={{
                    width: dataColWidth,
                    height: dataRowHeight,
                    backgroundColor: getHeatMapColor(pivotData?.[row]?.[col] ?? 0),
                  }}
                  onMouseEnter={(e) => handleMouseEnter(e, row, col, pivotData?.[row]?.[col] ?? 0)}
                  onMouseMove={handleMouseMove}
                  onMouseLeave={handleMouseLeave}
                >
                  {valueFormatter(pivotData?.[row]?.[col] ?? 0)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>

      {tooltip?.show ? (
        <FloatingTooltip x={tooltip.x} y={tooltip.y} theme={options?.theme}>
          <PivotTooltip
            rowValue={tooltip.rowValue}
            colValue={tooltip.colValue}
            value={tooltip.value}
            rowLabel={chartsConfig.pivot?.row}
            colLabel={chartsConfig.pivot?.col}
          />
        </FloatingTooltip>
      ) : null}
    </div>
  );
};

export default Pivot;
