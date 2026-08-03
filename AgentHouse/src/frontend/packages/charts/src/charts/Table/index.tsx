import { Loader } from "../../common/Loader";
import { IChartProps, IEntry } from "../../components/Insight";
import { valueFormatter } from "../../utils/general.util";

const Table: React.FC<IChartProps> = ({ chartsConfig, data, loading }) => {
  if (loading) return <Loader className="min-h-32 h-full" />;

  const { dimension, dimensionValues, metrics } = chartsConfig?.table ?? {};

  if (!dimension)
    return (
      <div className="flex text-center text-sm text-gray-500 h-full items-center justify-center">
        Select a dimensions to show table
      </div>
    );

  if (!dimensionValues?.length || !metrics?.length)
    return (
      <div className="flex text-center text-sm text-gray-500 h-full items-center justify-center">
        Dimension values are not available for selected dimension
      </div>
    );

  if (!data || data.length === 0)
    return <div className="flex text-center text-sm text-gray-500 h-full items-center justify-center">No data</div>;

  const dataMap = data.reduce<Record<string, IEntry>>((acc, item) => {
    acc[item[dimension] as string] = item;
    return acc;
  }, {});

  // Calculate dynamic width based on number of metrics
  const totalColumns = metrics.length + 1; // +1 for dimension column
  const columnWidth = `${100 / totalColumns}%`;

  return (
    <div className="p-2 w-full h-full overflow-auto">
      <table className="w-full border-collapse text-xs text-gray-700 border border-gray-300 table-fixed">
        <thead>
          <tr className="bg-gray-50">
            <th
              title={dimension}
              className="border border-gray-300 px-4 py-2 text-left font-medium truncate min-w-8"
              style={{ width: columnWidth }}
            >
              {dimension}
            </th>
            {metrics.map(({ metricLabel }) => (
              <th
                title={metricLabel}
                key={metricLabel}
                className="border border-gray-300 px-4 py-2 text-left font-medium truncate min-w-8"
                style={{ width: columnWidth }}
              >
                {metricLabel}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {dimensionValues.map((dimValue) => {
            const rowData = dataMap[dimValue];
            return (
              <tr key={dimValue} className="hover:bg-gray-50">
                <td
                  title={dimValue}
                  className="border border-gray-300 px-4 py-2 font-medium text-gray-900 truncate min-w-8"
                  style={{ width: columnWidth }}
                >
                  {dimValue}
                </td>
                {metrics.map(({ metricKey }) => (
                  <td
                    key={metricKey}
                    title={valueFormatter(rowData?.[metricKey] as number)}
                    className="border border-gray-300 px-4 py-2 truncate min-w-8"
                    style={{ width: columnWidth }}
                  >
                    {valueFormatter(rowData?.[metricKey] as number)}
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
};

export default Table;
