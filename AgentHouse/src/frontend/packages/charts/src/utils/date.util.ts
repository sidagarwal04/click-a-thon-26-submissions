import { format } from "date-fns";
import { TimeGrain, TimeGrainAPIKey, TimeGrainOffset } from "../constants/date.constant";

export function generateDatePairs(range, period) {
  const datePairs = [];

  const currentDate = new Date();
  const oneDay = 24 * 60 * 60 * 1000; // milliseconds in a day

  for (let i = 0; i < range; i++) {
    let startDate, endDate;
    if (period === TimeGrain.DAILY || period === TimeGrainAPIKey[TimeGrain.DAILY]) {
      startDate = new Date(currentDate.getTime() - i * oneDay);
      endDate = startDate;
    } else if (period === TimeGrain.WEEKLY || period === TimeGrainAPIKey[TimeGrain.WEEKLY]) {
      startDate = new Date(currentDate.getTime() - (currentDate.getDay() - 1 + 7 * i) * oneDay);
      endDate = new Date(startDate.getTime() + 6 * oneDay);
    } else if (period === TimeGrain.MONTHLY || period === TimeGrainAPIKey[TimeGrain.MONTHLY]) {
      startDate = new Date(currentDate.getFullYear(), currentDate.getMonth() - i, 1);
      endDate = new Date(currentDate.getFullYear(), currentDate.getMonth() - i + 1, 0);
    } else {
      throw new Error("Invalid period. Supported values are DAILY, WEEKLY, and MONTHLY.");
    }

    datePairs.push({ start: startDate, end: endDate });
  }

  return datePairs;
}

export function getDateRange(timeRange: number, timeGrain: TimeGrain) {
  const pageSize = timeRange / parseInt(TimeGrainOffset[timeGrain] + "");
  const d = generateDatePairs(pageSize ?? 2, timeGrain);
  const fromtime = formatDate(d?.[d.length - 1]?.start ?? new Date(), "yyyy-MM-dd");
  const totime = formatDate(d?.[0]?.end ?? new Date(), "yyyy-MM-dd");
  return { fromtime, totime };
}

export const stringifyDatePair = (dp) => {
  if (typeof dp === "string") return dp;
  const _dp = {
    start: new Date(dp?.start)?.toDateString(),
    end: new Date(dp?.end)?.toDateString(),
  };
  return JSON.stringify(_dp);
};

export const formatDatePair = (dp, period) => {
  switch (period) {
    case TimeGrain.WEEKLY:
      return `${formatDate(dp.start, "MMM dd, yyyy")} - ${formatDate(dp.end, "MMM dd, yyyy")}`;
    case TimeGrain.MONTHLY:
      return `${formatDate(dp.start, "MMM yyyy")}`;
    default:
      return `${formatDate(dp.start, "MMM dd, yyyy")}`;
  }
};

export function formatDate(date, formatStr = "yyyy-MM-dd") {
  return format(new Date(date), formatStr);
}

function groupByMonth(data, dateKey) {
  const groupedData = {};

  data.forEach((entry) => {
    const date = new Date(entry.date);
    const month = date.toLocaleString("default", { month: "short" });
    const year = date.toLocaleDateString("default", { year: "numeric" });
    const shortDate = month + " " + year;

    if (!groupedData[shortDate]) {
      groupedData[shortDate] = {};
      Object.keys(entry).forEach((key) => {
        groupedData[shortDate][key] = key === dateKey ? shortDate : 0;
      });
    }

    Object.keys(entry).forEach((key) => {
      if (key !== dateKey) groupedData[shortDate][key] += entry[key];
    });
  });

  return Object.values(groupedData).sort((a: any, b: any): any => {
    const [monthA, yearA] = a.date.split(" ");
    const [monthB, yearB] = b.date.split(" ");

    const dateA: any = new Date(`${monthA} 1, ${yearA}`);
    const dateB: any = new Date(`${monthB} 1, ${yearB}`);

    return dateA - dateB;
  });
}

function groupByWeek(data, dateKey) {
  const groupedData = {};
  const daysInWeek = 7; // Number of days in a week

  data.forEach((entry) => {
    const date = new Date(entry.date);
    const dayOfWeek = date.getDay(); // 0 for Sunday, 1 for Monday, ..., 6 for Saturday
    const startOfWeek = new Date(date); // Copy the current date
    startOfWeek.setDate(date.getDate() - dayOfWeek); // Go to the previous Monday
    const endOfWeek = new Date(startOfWeek); // Copy the start of the week
    endOfWeek.setDate(startOfWeek.getDate() + daysInWeek - 1); // Calculate end of the week

    const weekLabel = `${startOfWeek.toLocaleString("default", {
      month: "short",
    })} ${startOfWeek.getDate()} - ${endOfWeek.toLocaleString("default", {
      month: "short",
    })} ${endOfWeek.getDate()}`;

    if (!groupedData[weekLabel]) {
      groupedData[weekLabel] = {};
      Object.keys(entry).forEach((key) => {
        groupedData[weekLabel][key] = key === dateKey ? weekLabel : 0;
      });
    }

    Object.keys(entry).forEach((key) => {
      if (key !== dateKey) groupedData[weekLabel][key] += entry[key];
    });
  });

  return Object.values(groupedData);
}

export function groupDataByPeriod(entries, timeGrain, dateKey = "date") {
  switch (timeGrain) {
    case TimeGrain.MONTHLY:
      return groupByMonth(entries, dateKey);
    case TimeGrain.WEEKLY:
      return groupByWeek(entries, dateKey);
    case TimeGrain.DAILY:
      return entries;
    default:
      return [];
  }
}

export function getDatesWithDiff(gap = 1) {
  const today = new Date();
  const past = new Date(today);
  past.setDate(today.getDate() - gap);

  const fromTime = formatDate(past, "yyyy-MM-dd");
  const toTime = formatDate(today, "yyyy-MM-dd");

  return { fromTime, toTime };
}

export function isDateGreaterOrEqual(d1, d2) {
  // Convert input strings to Date objects
  const date1 = new Date(d1);
  const date2 = new Date(d2);

  // Use getTime() to compare the timestamps of the two dates
  return date1.getTime() >= date2.getTime();
}

export function shortenDate(fromDateString, toDateString, timeGrain, dateFormat?: string) {
  if (!fromDateString || !toDateString) return "";
  switch (timeGrain) {
    case TimeGrain.DAILY:
      return formatDate(fromDateString, dateFormat ?? "MMM dd");
    case TimeGrain.WEEKLY:
      return `${formatDate(fromDateString, dateFormat ?? "MMM dd")} - ${formatDate(
        toDateString,
        dateFormat ?? "MMM dd"
      )}`;
    case TimeGrain.MONTHLY:
      return formatDate(fromDateString, dateFormat ?? "MMM");
    default:
      return `${fromDateString} - ${toDateString}`;
  }
}

export const getPeriodRanges = (cadence) => {
  switch (cadence) {
    case TimeGrain.DAILY:
      return [
        {
          label: "D",
          value: TimeGrain.DAILY,
        },
        {
          label: "W",
          value: TimeGrain.WEEKLY,
        },
        {
          label: "M",
          value: TimeGrain.MONTHLY,
        },
      ];
    case TimeGrain.WEEKLY:
      return [
        {
          label: "W",
          value: TimeGrain.WEEKLY,
        },
        {
          label: "M",
          value: TimeGrain.MONTHLY,
        },
      ];
    case TimeGrain.MONTHLY:
      return [
        {
          label: "M",
          value: TimeGrain.MONTHLY,
        },
      ];
    default:
      return [];
  }
};

export const getTimeRanges = (cadence) => {
  switch (cadence) {
    case TimeGrain.DAILY:
      return [
        {
          label: "7d",
          value: 7,
        },
        {
          label: "14d",
          value: 14,
        },
        {
          label: "1m",
          value: 30,
        },
        {
          label: "3m",
          value: 90,
        },
        {
          label: "6m",
          value: 180,
        },
        {
          label: "1y",
          value: 360,
        },
      ];
    case TimeGrain.WEEKLY:
      return [
        {
          label: "1m",
          value: 30,
        },
        {
          label: "3m",
          value: 90,
        },
        {
          label: "6m",
          value: 180,
        },
        {
          label: "1y",
          value: 360,
        },
      ];
    case TimeGrain.MONTHLY:
      return [
        {
          label: "3m",
          value: 90,
        },
        {
          label: "6m",
          value: 180,
        },
        {
          label: "1y",
          value: 360,
        },
      ];
    default:
      return [];
  }
};

export const getWeek = (date) => {
  const firstDayOfYear: any = new Date(date.getFullYear(), 0, 1);
  const pastDaysOfYear: any = (date - firstDayOfYear) / 86400000 + firstDayOfYear.getDay();
  return Math.ceil((pastDaysOfYear + firstDayOfYear.getDay() + 1) / 7);
};

export const monthsDifference = (date1, date2) => {
  const d1 = new Date(date1);
  const d2 = new Date(date2);

  const yearDiff = d2.getFullYear() - d1.getFullYear();
  const monthDiff = d2.getMonth() - d1.getMonth();

  return yearDiff * 12 + monthDiff;
};

export const weeksDifference = (date1, date2) => {
  const d1: any = new Date(date1);
  const d2: any = new Date(date2);
  const diffInMs = d2 - d1;

  const msInWeek = 7 * 24 * 60 * 60 * 1000;
  const diffInWeeks = diffInMs / msInWeek;

  return Math.floor(diffInWeeks);
};

export const daysDifference = (date1, date2) => {
  const d1: any = new Date(date1);
  const d2: any = new Date(date2);
  const diffInMs = d2 - d1;

  const msInDay = 24 * 60 * 60 * 1000;
  const diffInDays = diffInMs / msInDay;

  return Math.floor(diffInDays);
};

export const addMonths = (date, offset) => {
  const d = new Date(date);
  d.setMonth(d.getMonth() + offset);
  return d;
};

export const addWeeks = (date, offset) => {
  const d = new Date(date);
  const daysOffset = offset * 7;
  d.setDate(d.getDate() + daysOffset);
  return d;
};

export const addDays = (date, offset) => {
  const d = new Date(date);
  d.setDate(d.getDate() + offset);
  return d;
};
