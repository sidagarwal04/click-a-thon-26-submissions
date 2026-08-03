export const INK = "#171612";
export const RULE = "#E4DFD4";
export const PANEL = "#FFFDF9";
export const ALARM = "#B4442B";
export const WARN = "#A8761F";
export const OK = "#4E7A4A";
export const GREY = "#8A857A";
export const BG = "#FAF8F4";
export const DEFAULT_ACCENT = "#2F6E70";

export function toneColor(tone: "bad" | "warn" | "ok"): string {
  return tone === "bad" ? ALARM : tone === "warn" ? WARN : OK;
}
