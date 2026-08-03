import React from "react";
import { Change } from "./Change";
import { IEntry } from "../../../components/Insight";
import { CompactBigNumber } from "./CompactBigNumber";
import { valueFormatter } from "../../../utils/general.util";
import { TimeGrain } from "../../../constants/date.constant";
import { getComparisonLabel, getCurrLabel, getPrevLabel } from "../utils/bigNumber.util";

export type ExpandedBigNumberProps = {
  data: IEntry[];
  value: number;
  prevValue: number;
  change: number;
  changeType: string;
  timeGrain: TimeGrain;
};

export const ExpandedBigNumber: React.FC<ExpandedBigNumberProps> = ({
  data,
  value,
  prevValue,
  change,
  changeType,
  timeGrain,
}) => {
  return (
    <div className="grid grid-cols-3 divide-x min-h-16 h-full">
      <CompactBigNumber
        number={valueFormatter(value)}
        label={getCurrLabel(data, timeGrain)}
        numberFont="text-2xl font-medium"
      />
      <CompactBigNumber
        number={valueFormatter(prevValue)}
        label={getPrevLabel(data, timeGrain)}
        numberFont="text-2xl font-medium"
      />
      <CompactBigNumber
        number={
          <Change
            change={change}
            changeType={changeType}
            className="justify-center !text-2xl font-medium"
            iconSize={18}
          />
        }
        label={getComparisonLabel(data, timeGrain)}
        numberFont="text-2xl font-medium"
      />
    </div>
  );
};
