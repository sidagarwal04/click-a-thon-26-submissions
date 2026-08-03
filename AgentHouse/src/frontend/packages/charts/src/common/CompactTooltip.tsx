import { valueFormatter } from "../utils/general.util";

export interface ICustomTooltipProps {
  payload: [
    {
      color: string;
      dataKey: string;
      value: number;
      payload: {
        fill: string;
        date?: string;
        time?: string;
        prevDateLabel?: string;
        segment?: string;
        state?: string;
      };
    }
  ];
  active: boolean;
}

export const CompactTooltip: React.FC<ICustomTooltipProps> = (params) => {
  const { payload, active } = params;
  if (!active || !payload) return null;
  return (
    <div className="da-tooltip w-auto rounded-md text-sm shadow-sm bg-white border border-gray-300 px-3 py-2">
      <div className="flex justify-between gap-x-4 min-w-16">
        <p className="text-gray-700">{payload?.[0]?.payload?.date}</p>
        <p className="text-gray-600">{valueFormatter(payload?.[0]?.value)}</p>
      </div>
    </div>
  );
};
