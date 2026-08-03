import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";
import { IEntry } from "../components/Insight";

export function getSum(entry: IEntry, keys: string[] = []): number {
  if (!entry || keys.length == 0) return 0;
  const sum = keys.reduce((total, key) => {
    if (typeof entry[key] === "string") return total;
    return total + (entry[key] ?? 0);
  }, 0);
  return sum;
}

export const getChangeInPercent = (a: number, b: number): string => {
  return (((a - b) / b) * 100).toFixed(2);
};

export function getChange(entries: IEntry[], keys: string[] = []): number {
  const a = getSum(entries?.[entries.length - 1], keys) ?? 0;
  const b = Math.max(1, getSum(entries?.[entries.length - 2], keys) ?? 0);

  return parseFloat(getChangeInPercent(a, b));
}

export const sleep = (ms: number): Promise<void> =>
  new Promise((resolve) => setTimeout(resolve, ms));

export function shuffle<T>(array: T[]): T[] {
  let currentIndex = array.length,
    randomIndex;

  while (currentIndex > 0) {
    randomIndex = Math.floor(Math.random() * currentIndex);
    currentIndex--;

    [array[currentIndex], array[randomIndex]] = [array[randomIndex], array[currentIndex]];
  }

  return array;
}

export const classNames = (...classes: string[]): string => classes.filter(Boolean).join(" ");

export const valueFormatter = (number: number): string => {
  if (isNaN(number) || number === null || number === undefined) {
    return "N/A";
  }

  if (number === 0) return "0";
  if (number < 1) return parseFloat(number + "")?.toFixed(3);

  // Define the scale suffixes and their corresponding multipliers
  const scales = [
    { value: 1, suffix: "" },
    { value: 1e3, suffix: "K" },
    { value: 1e6, suffix: "M" },
    { value: 1e9, suffix: "B" },
  ];

  // Loop through the scales and find the appropriate scale for formatting
  for (let i = scales.length - 1; i >= 0; i--) {
    const scale = scales[i];
    if (Math.abs(number) >= scale.value) {
      // Format the number with commas and append the scale suffix
      const formattedNumber = (number / scale.value).toLocaleString(undefined, {
        maximumFractionDigits: 1,
      });
      return `${formattedNumber} ${scale.suffix}`;
    }
  }

  return "N/A";
};

export const formatString = (input) => {
  if (!input) return input;
  return input
    ?.split?.("_")
    ?.map?.((word, index) =>
      index === 0 ? word.charAt(0).toUpperCase() + word.slice(1) : word.toLowerCase()
    )
    ?.join?.(" ");
};

export function cn(...inputs) {
  return twMerge(clsx(inputs));
}
