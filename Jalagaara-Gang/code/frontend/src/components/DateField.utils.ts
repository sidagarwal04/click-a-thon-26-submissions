/** Calendar helpers for DateField — pure functions only. */

const WEEKDAYS = ["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"] as const;

const MONTHS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
] as const;

export { WEEKDAYS, MONTHS };

/** Parse YYYY-MM-DD into local date parts; invalid → null. */
export function parseIsoDate(iso: string): { y: number; m: number; d: number } | null {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(iso)) return null;
  const [y, m, d] = iso.split("-").map(Number);
  const dt = new Date(y, m - 1, d);
  if (dt.getFullYear() !== y || dt.getMonth() !== m - 1 || dt.getDate() !== d) return null;
  return { y, m, d };
}

export function toIsoDate(y: number, m: number, d: number): string {
  return `${y}-${String(m).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
}

export function todayIso(): string {
  const now = new Date();
  return toIsoDate(now.getFullYear(), now.getMonth() + 1, now.getDate());
}

/** Display label for the trigger; empty → placeholder. */
export function formatDisplay(iso: string): string {
  const p = parseIsoDate(iso);
  if (!p) return "";
  return `${String(p.d).padStart(2, "0")} · ${String(p.m).padStart(2, "0")} · ${p.y}`;
}

export type DayCell = {
  iso: string;
  day: number;
  inMonth: boolean;
  isToday: boolean;
};

/** 6×7 grid covering the visible month (leading/trailing days from adjacent months). */
export function buildMonthGrid(viewYear: number, viewMonth: number): DayCell[] {
  const first = new Date(viewYear, viewMonth - 1, 1);
  const startPad = first.getDay(); // 0 = Sunday
  const daysInMonth = new Date(viewYear, viewMonth, 0).getDate();
  const prevMonthDays = new Date(viewYear, viewMonth - 1, 0).getDate();
  const today = todayIso();
  const cells: DayCell[] = [];

  for (let i = 0; i < 42; i++) {
    let y = viewYear;
    let m = viewMonth;
    let d: number;
    let inMonth = true;

    if (i < startPad) {
      d = prevMonthDays - startPad + i + 1;
      m = viewMonth === 1 ? 12 : viewMonth - 1;
      y = viewMonth === 1 ? viewYear - 1 : viewYear;
      inMonth = false;
    } else if (i >= startPad + daysInMonth) {
      d = i - startPad - daysInMonth + 1;
      m = viewMonth === 12 ? 1 : viewMonth + 1;
      y = viewMonth === 12 ? viewYear + 1 : viewYear;
      inMonth = false;
    } else {
      d = i - startPad + 1;
    }

    const iso = toIsoDate(y, m, d);
    cells.push({ iso, day: d, inMonth, isToday: iso === today });
  }

  return cells;
}

export function shiftMonth(year: number, month: number, delta: number): { y: number; m: number } {
  const d = new Date(year, month - 1 + delta, 1);
  return { y: d.getFullYear(), m: d.getMonth() + 1 };
}
