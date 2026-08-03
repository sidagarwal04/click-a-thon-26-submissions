import { format } from "date-fns";
import { TimeGrain } from "../../../constants/date.constant";
import { IEntry } from "../../Mixed/dataResolver";

export const getCurrLabel = (data: IEntry[], timeGrain: TimeGrain): string => {
  try {
    if (timeGrain === TimeGrain.DAILY) return "Today";
    else if (timeGrain === TimeGrain.WEEKLY) return "This week";
    else return format(new Date(data?.[data?.length - 1]?.fromtime), "MMMM");
  } catch {
    return "";
  }
};

export const getPrevLabel = (data: IEntry[], timeGrain: TimeGrain): string => {
  try {
    if (timeGrain === TimeGrain.DAILY) return "Yesterday";
    else if (timeGrain === TimeGrain.WEEKLY) return "Last week";
    else return format(new Date(data?.[data?.length - 2]?.fromtime), "MMMM");
  } catch {
    return "";
  }
};

export const getComparisonLabel = (data: IEntry[], timeGrain: TimeGrain): string => {
  try {
    if (timeGrain === TimeGrain.DAILY) return "Today vs Yesterday";
    else if (timeGrain === TimeGrain.WEEKLY) return "This week vs Last week";
    else
      return (
        format(new Date(data[data.length - 1].fromtime), "MMMM") +
        " vs " +
        format(new Date(data[data.length - 2].fromtime), "MMMM")
      );
  } catch {
    return "";
  }
};
