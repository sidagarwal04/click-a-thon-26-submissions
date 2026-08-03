import { useEffect, useId, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import {
  MONTHS,
  WEEKDAYS,
  buildMonthGrid,
  formatDisplay,
  parseIsoDate,
  shiftMonth,
  toIsoDate,
  todayIso,
} from "./DateField.utils";

type Props = {
  value: string;
  onChange: (iso: string) => void;
  "aria-label": string;
  /** Inclusive ISO (YYYY-MM-DD) bounds. Days outside are rendered disabled and month
   *  navigation stops at the edges, so only dates the dataset actually covers are pickable. */
  min?: string;
  max?: string;
};

type PopPos = { top: number; left: number };

export function DateField({ value, onChange, "aria-label": ariaLabel, min, max }: Props) {
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState<PopPos>({ top: 0, left: 0 });
  const parsed = parseIsoDate(value);
  // ISO YYYY-MM-DD sorts lexicographically, so plain string compares are correct here.
  const outOfRange = (iso: string) => (!!min && iso < min) || (!!max && iso > max);
  const [view, setView] = useState(() => {
    // Open on the selected date, else on the first in-range month rather than today's — with a
    // bounded range, landing on an all-disabled month reads as broken.
    if (parsed) return { y: parsed.y, m: parsed.m };
    const fallback = parseIsoDate(min ?? "") ?? parseIsoDate(max ?? "");
    if (fallback) return { y: fallback.y, m: fallback.m };
    const now = new Date();
    return { y: now.getFullYear(), m: now.getMonth() + 1 };
  });
  const rootRef = useRef<HTMLDivElement>(null);
  const popRef = useRef<HTMLDivElement>(null);
  const listboxId = useId();

  // Sync calendar view when the value changes while closed (e.g. Clear / external set).
  useEffect(() => {
    if (open) return;
    if (parsed) setView({ y: parsed.y, m: parsed.m });
  }, [value, open, parsed?.y, parsed?.m]);

  // Portal popover must clear .app { overflow: hidden } — place it with fixed coords.
  useLayoutEffect(() => {
    if (!open || !rootRef.current) return;
    const place = () => {
      const trigger = rootRef.current?.querySelector(".date-field-trigger") as HTMLElement | null;
      const pop = popRef.current;
      if (!trigger || !pop) return;
      const r = trigger.getBoundingClientRect();
      const pw = pop.offsetWidth || 268;
      const ph = pop.offsetHeight || 320;
      const gap = 6;
      let left = r.right - pw;
      let top = r.bottom + gap;
      if (left < 8) left = 8;
      if (left + pw > window.innerWidth - 8) left = window.innerWidth - pw - 8;
      if (top + ph > window.innerHeight - 8 && r.top - gap - ph > 8) {
        top = r.top - gap - ph;
      }
      setPos({ top, left });
    };
    place();
    window.addEventListener("resize", place);
    window.addEventListener("scroll", place, true);
    return () => {
      window.removeEventListener("resize", place);
      window.removeEventListener("scroll", place, true);
    };
  }, [open, view.y, view.m]);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      const t = e.target as Node;
      if (rootRef.current?.contains(t) || popRef.current?.contains(t)) return;
      setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const cells = buildMonthGrid(view.y, view.m);
  const label = formatDisplay(value);
  const placeholder = "dd · mm · yyyy";

  // Stop paging once the whole adjacent month sits outside the range — the arrow would
  // otherwise walk forever through months with nothing selectable in them.
  const prev = shiftMonth(view.y, view.m, -1);
  const next = shiftMonth(view.y, view.m, 1);
  const monthEnd = (y: number, m: number) => toIsoDate(y, m, new Date(y, m, 0).getDate());
  const canGoPrev = !min || monthEnd(prev.y, prev.m) >= min;
  const canGoNext = !max || toIsoDate(next.y, next.m, 1) <= max;
  const todayPickable = !outOfRange(todayIso());

  const pick = (iso: string) => {
    if (outOfRange(iso)) return; // defensive: disabled cells shouldn't fire, but never accept one
    onChange(iso);
    setOpen(false);
  };

  const toggle = () => {
    if (!open && parsed) setView({ y: parsed.y, m: parsed.m });
    setOpen((o) => !o);
  };

  const popover = open
    ? createPortal(
        <div className="date-popover-portal spacing-default effect-smooth">
          <div
            className="date-popover"
            id={listboxId}
            role="dialog"
            aria-label={ariaLabel}
            ref={popRef}
            style={{ top: pos.top, left: pos.left }}
          >
            <div className="date-popover-head">
              <span className="date-popover-month">{MONTHS[view.m - 1]} {view.y}</span>
              <div className="date-popover-nav">
                <button
                  type="button"
                  className="date-nav-btn"
                  aria-label="Previous month"
                  disabled={!canGoPrev}
                  onClick={() => setView((v) => shiftMonth(v.y, v.m, -1))}
                >
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                    <polyline points="15 18 9 12 15 6" />
                  </svg>
                </button>
                <button
                  type="button"
                  className="date-nav-btn"
                  aria-label="Next month"
                  disabled={!canGoNext}
                  onClick={() => setView((v) => shiftMonth(v.y, v.m, 1))}
                >
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                    <polyline points="9 18 15 12 9 6" />
                  </svg>
                </button>
              </div>
            </div>

            <div className="date-weekdays" aria-hidden>
              {WEEKDAYS.map((d) => (
                <span key={d}>{d}</span>
              ))}
            </div>

            <div className="date-grid" role="grid">
              {cells.map((cell) => {
                const selected = cell.iso === value;
                const disabled = outOfRange(cell.iso);
                return (
                  <button
                    key={cell.iso}
                    type="button"
                    role="gridcell"
                    className={[
                      "date-day",
                      cell.inMonth ? "" : "is-outside",
                      cell.isToday ? "is-today" : "",
                      selected ? "is-selected" : "",
                      disabled ? "is-disabled" : "",
                    ].filter(Boolean).join(" ")}
                    aria-label={cell.iso}
                    aria-selected={selected}
                    aria-disabled={disabled}
                    disabled={disabled}
                    onClick={() => pick(cell.iso)}
                  >
                    {cell.day}
                  </button>
                );
              })}
            </div>

            <div className="date-popover-foot">
              <button type="button" className="date-foot-btn" onClick={() => { onChange(""); setOpen(false); }}>
                Clear
              </button>
              <button
                type="button"
                className="date-foot-btn"
                disabled={!todayPickable}
                title={todayPickable ? undefined : "Today is outside the available data range"}
                onClick={() => pick(todayIso())}
              >
                Today
              </button>
            </div>
          </div>
        </div>,
        document.body,
      )
    : null;

  return (
    <div className={`date-field ${open ? "is-open" : ""}`} ref={rootRef}>
      <button
        type="button"
        className="date-field-trigger"
        aria-label={ariaLabel}
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-controls={open ? listboxId : undefined}
        onClick={toggle}
      >
        <span className={label ? "date-field-value" : "date-field-placeholder"}>
          {label || placeholder}
        </span>
        <svg className="date-field-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
          <rect x="3" y="5" width="18" height="16" rx="2" />
          <path d="M3 9h18M8 3v4M16 3v4" />
        </svg>
      </button>
      {popover}
    </div>
  );
}
