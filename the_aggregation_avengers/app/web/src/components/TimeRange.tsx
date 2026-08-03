// Time-range control, CloudWatch-shaped.
//
// Two ways to say the same thing, so they are ONE piece of state:
//   relative -- "the last 3 hours", a duration
//   absolute -- an explicit from/to, which is also what a brush drag on the
//               chart produces
//
// Keeping them in one `TimeRange` union is what lets a drag-selection on the
// chart show up here as "Custom", and lets clicking a chip clear the zoom. Two
// separate controls would have needed to be kept in sync by hand, and the two
// would eventually disagree.
//
// EVERYTHING HERE IS UTC, AND SAYS SO.
// The data carries its own clock -- ClickHouse is on UTC and the events are a
// fixed historical day. Rendering the picker in the viewer's local timezone
// would silently shift every window (a viewer in IST would ask for 05:30 and
// get 00:00 of the data's day), so the inputs are treated as literal wall-clock
// strings in the data's own timezone and never passed through Date parsing.

import { useEffect, useRef, useState } from "react";
import type { Facets } from "../lib/api";

export type TimeRange =
  | { mode: "rel"; minutes: number } // minutes = 0 means the full extent
  | { mode: "abs"; from: string; to: string };

/**
 * Quick picks.
 *
 * Anchored to the LAST MINUTE IN THE DATA, not to wall-clock now -- "last hour"
 * of a historical day means the last hour that has data in it. Anchoring to now
 * would return an empty chart for every preset.
 *
 * The dataset spans 12 days but 94% of events land on the final one, so the
 * short picks are the useful ones and the default is 6h.
 */
export const QUICK: { key: string; label: string; minutes: number }[] = [
  { key: "30m", label: "30m", minutes: 30 },
  { key: "1h", label: "1h", minutes: 60 },
  { key: "3h", label: "3h", minutes: 180 },
  { key: "6h", label: "6h", minutes: 360 },
  { key: "12h", label: "12h", minutes: 720 },
  { key: "1d", label: "1d", minutes: 1440 },
  { key: "3d", label: "3d", minutes: 4320 },
  // Labelled "Max", not "All". It is the widest range the picker OFFERS, which
  // is the span carrying real traffic -- not every row in the table. Calling it
  // "All" claimed something it stopped doing the moment the range was bounded,
  // and a control that overstates itself is worse than one that is narrow.
  { key: "All", label: "Max", minutes: 0 },
];

export const DEFAULT_RANGE: TimeRange = { mode: "rel", minutes: 360 };

// --- UTC string arithmetic, no Date-timezone involvement ---------------------

/** "2026-07-26 11:30:00" -> epoch ms, read as UTC. */
const parseUTC = (s: string) => Date.parse(s.replace(" ", "T") + "Z");
/** epoch ms -> "2026-07-26 11:30:00". */
const fmtUTC = (ms: number) => new Date(ms).toISOString().slice(0, 19).replace("T", " ");
/** "2026-07-26 11:30:00" <-> the "2026-07-26T11:30" a datetime-local wants. */
const toInput = (s: string) => s.slice(0, 16).replace(" ", "T");
const fromInput = (s: string) => (s.length === 16 ? s.replace("T", " ") + ":00" : s.replace("T", " "));

/**
 * Resolve a range to the API's `from`/`to`.
 *
 * `to` is EXCLUSIVE server-side (`minute < to`), so the end always gets one
 * extra minute added -- otherwise the last minute of every window, including
 * the peak minute when it sits at the edge, would be dropped.
 */
export function rangeFor(r: TimeRange, facets: Facets | null): { from?: string; to?: string } {
  if (!facets) return {};
  if (r.mode === "abs") return { from: r.from, to: fmtUTC(parseUTC(r.to) + 60_000) };
  // "All" means the whole range the picker OFFERS, not an unbounded query.
  // Sending no bounds made the server fall back to the table's true extent --
  // which 358 clock-skewed sessions stretch from 2014 to 2026. The chart then
  // drew an eleven-year axis with one spike, and the rollup fell to quarterly
  // buckets. facets already reports the range that has real traffic; "All"
  // should mean exactly that.
  if (!r.minutes) {
    return { from: facets.min_minute, to: fmtUTC(parseUTC(facets.max_minute) + 60_000) };
  }
  const end = parseUTC(facets.max_minute);
  return { from: fmtUTC(end - r.minutes * 60_000), to: fmtUTC(end + 60_000) };
}

/** Human span: "6h", "1h 45m", "3d 2h". */
export function spanLabel(minutes: number): string {
  if (minutes < 60) return `${minutes}m`;
  const d = Math.floor(minutes / 1440);
  const h = Math.floor((minutes % 1440) / 60);
  const m = minutes % 60;
  return [d && `${d}d`, h && `${h}h`, !d && m ? `${m}m` : ""].filter(Boolean).join(" ") || `${minutes}m`;
}

/** What the control is currently showing, in words. */
export function describeRange(r: TimeRange, facets: Facets | null): string {
  if (r.mode === "rel") {
    if (!r.minutes) return "Full range";
    return `Last ${spanLabel(r.minutes)}`;
  }
  const mins = Math.round((parseUTC(r.to) - parseUTC(r.from)) / 60_000) + 1;
  void facets;
  // Show the END DATE whenever the range crosses a day. Abbreviating the end to
  // a bare time made "07-14 23:30 → 11:30" look like a 12-hour window on the
  // 14th, when it is actually eleven days ending on the 26th -- so an applied
  // range read as if it had not applied.
  // Full date on both ends, year included. "07-14 -> 11:30" told the reader
  // neither the end date nor the year of either.
  const sameDay = r.from.slice(0, 10) === r.to.slice(0, 10);
  const end = sameDay ? r.to.slice(11, 16) : r.to.slice(0, 16);
  return `${r.from.slice(0, 16)} → ${end} UTC · ${spanLabel(mins)}`;
}

/** "2026-07-26 11:30:00" -> "26 Jul 11:30" */
const stampShort = (ts: string) => {
  const [d, t] = (ts ?? "").split(" ");
  if (!d || !t) return ts;
  const [, m, day] = d.split("-");
  const month = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"][Number(m) - 1];
  return `${Number(day)} ${month} ${d.slice(0, 4)} ${t.slice(0, 5)}`;
};

function Jump({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      style={{
        background: "transparent",
        border: "1px solid var(--border)",
        borderRadius: 999,
        padding: "3px 9px",
        fontSize: 11,
        cursor: "pointer",
        color: "var(--text-secondary)",
      }}
    >
      {label}
    </button>
  );
}

// --- control -----------------------------------------------------------------

export function TimeRangeControl({
  value,
  onChange,
  facets,
}: {
  value: TimeRange;
  onChange: (r: TimeRange) => void;
  facets: Facets | null;
}) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  // Seeded from whatever is currently applied, so opening Custom on a brushed
  // range lets you nudge its edges instead of starting from nothing.
  const applied = rangeFor(value, facets);
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");

  useEffect(() => {
    if (!open) return;
    setFrom(toInput(applied.from ?? facets?.min_minute ?? ""));
    // Undo the exclusive-end minute so the picker shows the last minute you can
    // actually see, not the one after it.
    setTo(toInput(applied.to ? fmtUTC(parseUTC(applied.to) - 60_000) : facets?.max_minute ?? ""));
    // Deliberately keyed on `open` alone: re-seeding on every applied change
    // would fight the user's typing while the popover is open.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      const t = e.target as Node;
      if (rootRef.current?.contains(t)) return;
      // The browser's native date picker is CHROME, not DOM. Interacting with
      // it leaves the page's own mousedown target outside this component, so a
      // naive outside-click handler closes the popover the instant you touch
      // the calendar -- which is exactly why typing a date worked and picking
      // one did not. Focus stays inside our inputs while the picker is open,
      // so that is the signal to trust.
      //
      // The guard has to be NARROW. "Focus is still in our input, so ignore"
      // was the obvious rule and it is wrong: focus stays in the input after
      // you have clicked it, so a genuine click elsewhere stopped closing the
      // popover at all. The distinguishing signal is the TARGET -- a real click
      // lands on a real element, whereas the stray events that accompany the
      // native picker land on body/html with focus still held by our input.
      const strayFromPicker =
        (t === document.body || t === document.documentElement) &&
        !!rootRef.current?.contains(document.activeElement);
      if (strayFromPicker) return;
      // A mousedown on a node already detached from the document is the tail of
      // an interaction with something since unmounted, not a click outside.
      if (!t.isConnected) return;
      setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const activeKey = value.mode === "rel" ? QUICK.find((q) => q.minutes === value.minutes)?.key : null;
  const invalid = !from || !to || parseUTC(fromInput(from)) > parseUTC(fromInput(to));

  const apply = () => {
    if (invalid) return;
    onChange({ mode: "abs", from: fromInput(from), to: fromInput(to) });
    setOpen(false);
  };

  return (
    <div ref={rootRef} style={{ position: "relative", display: "grid", gap: 3 }}>
      {/* "Last 2 hours" of WHAT is the question this label exists to answer.
          Anchoring to wall-clock now would return an empty chart for every
          preset -- the data is a fixed historical window that ended days ago --
          so the anchor is the last minute of data, and it says so. */}
      <span style={{ fontSize: 11, color: "var(--text-muted)" }}>
        Time range <span style={{ opacity: 0.7 }}>· UTC</span>
        {facets && (
          <span style={{ opacity: 0.7 }}> · back from end of data ({stampShort(facets.max_minute)})</span>
        )}
      </span>

      <div style={{ display: "flex", alignItems: "stretch", gap: 6 }}>
        {/* Segmented quick picks. One row, no dropdown -- the whole point of
            the CloudWatch shape is that the common spans are one click. */}
        <div
          role="group"
          aria-label="Quick time range"
          style={{
            display: "flex",
            background: "var(--surface-1)",
            border: "1px solid var(--border)",
            borderRadius: 8,
            overflow: "hidden",
          }}
        >
          {QUICK.map((q, i) => {
            const on = activeKey === q.key;
            return (
              <button
                key={q.key}
                onClick={() => onChange({ mode: "rel", minutes: q.minutes })}
                aria-pressed={on}
                title={
                  q.minutes
                    ? `Last ${spanLabel(q.minutes)} of data`
                    : "The full span that carries real traffic. A little data sits outside it — a few hundred sessions with wrong client clocks, none of them busier than 9 concurrent. Type a date in Custom to see them."
                }
                style={{
                  border: "none",
                  borderLeft: i ? "1px solid var(--border)" : "none",
                  // Selection is chrome, so it is a neutral wash and a weight
                  // change -- a series colour here would read as data.
                  background: on ? "var(--page)" : "transparent",
                  color: on ? "var(--text-primary)" : "var(--text-secondary)",
                  fontWeight: on ? 600 : 400,
                  fontSize: 12,
                  padding: "6px 10px",
                  cursor: "pointer",
                  fontVariantNumeric: "tabular-nums",
                }}
              >
                {q.label}
              </button>
            );
          })}
        </div>

        <button
          onClick={() => setOpen((o) => !o)}
          aria-expanded={open}
          aria-haspopup="dialog"
          title="Pick exact start and end times"
          style={{
            background: value.mode === "abs" ? "var(--page)" : "var(--surface-1)",
            border: "1px solid var(--border)",
            borderRadius: 8,
            padding: "6px 10px",
            fontSize: 12,
            cursor: "pointer",
            color: value.mode === "abs" ? "var(--text-primary)" : "var(--text-secondary)",
            fontWeight: value.mode === "abs" ? 600 : 400,
            whiteSpace: "nowrap",
            display: "flex",
            alignItems: "center",
            gap: 6,
          }}
        >
          <span aria-hidden>🗓</span>
          {value.mode === "abs" ? describeRange(value, facets) : "Custom"}
          <span aria-hidden style={{ fontSize: 9, color: "var(--text-muted)" }}>▾</span>
        </button>
      </div>

      {open && (
        <div
          className="card"
          role="dialog"
          aria-label="Custom time range"
          style={{
            position: "absolute",
            top: "calc(100% + 6px)",
            left: 0,
            zIndex: 900,
            padding: 12,
            display: "grid",
            gap: 10,
            minWidth: 300,
            boxShadow: "0 8px 24px rgba(0,0,0,0.28)",
          }}
        >
          <div style={{ fontSize: 11, color: "var(--text-muted)" }}>
            Absolute window &middot; times are UTC, matching the data&rsquo;s own clock
          </div>
          {/* Stated UP FRONT, not as a footnote. The calendar's min/max are the
              extent of the data, so dates outside it are greyed out and will
              not select -- which reads as a broken picker unless you are told
              why. This dataset is a fixed historical window; it has no today. */}
          <div
            style={{
              fontSize: 11,
              background: "var(--page)",
              border: "1px solid var(--border)",
              borderRadius: 6,
              padding: "6px 8px",
              color: "var(--text-secondary)",
              lineHeight: 1.45,
            }}
          >
            Rows exist for{" "}
            <strong>
              {facets?.data_min?.slice(0, 16)} &rarr; {facets?.data_max?.slice(0, 16)}
            </strong>
            , all of it selectable here. The presets cover{" "}
            <strong>
              {facets?.min_minute?.slice(0, 16)} &rarr; {facets?.max_minute?.slice(0, 16)}
            </strong>
            , the span carrying real traffic &mdash; outside it are a few hundred sessions with
            wrong client clocks, none busier than 9 concurrent.
          </div>
          {(["from", "to"] as const).map((which) => (
            <label key={which} style={{ display: "grid", gap: 3 }}>
              <span style={{ fontSize: 11, color: "var(--text-secondary)" }}>
                {which === "from" ? "Start" : "End"}
              </span>
              <input
                type="datetime-local"
                value={which === "from" ? from : to}
                // Bounded by the TRUE extent, not by the traffic range. Using
                // the latter disabled every other month and year in the
                // calendar, so picking any date outside one week was
                // impossible -- the presets' default became a hard limit.
                min={toInput(facets?.data_min ?? facets?.min_minute ?? "")}
                max={toInput(facets?.data_max ?? facets?.max_minute ?? "")}
                onChange={(e) => (which === "from" ? setFrom : setTo)(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && apply()}
                // Chrome shows a calendar only via the icon; make the whole
                // field open it where the browser supports it.
                onClick={(e) => (e.currentTarget as HTMLInputElement).showPicker?.()}
                style={{
                  background: "var(--page)",
                  border: "1px solid var(--border)",
                  borderRadius: 6,
                  padding: "6px 8px",
                  fontSize: 13,
                  color: "var(--text-primary)",
                  colorScheme: "inherit",
                }}
              />
            </label>
          ))}

          {/* Shortcuts to the boundaries. The calendar is fiddly for a window
              you already know you want, and in this dataset "the busy day" is
              the only window anybody actually asks for. */}
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
            {facets && (
              <>
                <Jump
                  label="Whole dataset"
                  onClick={() => {
                    setFrom(toInput(facets.min_minute));
                    setTo(toInput(facets.max_minute));
                  }}
                />
                <Jump
                  label="Busiest day"
                  onClick={() => {
                    setFrom(`${facets.max_minute.slice(0, 10)}T00:00`);
                    setTo(toInput(facets.max_minute));
                  }}
                />
                <Jump
                  label="Last hour of data"
                  onClick={() => {
                    setFrom(toInput(fmtUTC(parseUTC(facets.max_minute) - 3600_000)));
                    setTo(toInput(facets.max_minute));
                  }}
                />
              </>
            )}
          </div>

          {/* Live preview of what Apply will do.
              Chrome's native calendar has no confirm step -- you click a day
              and it silently rewrites the field -- so there is no feedback that
              anything happened until you press Apply and the whole page moves.
              Echoing the pending window here makes the state visible BEFORE
              committing to it. */}
          <div
            style={{
              fontSize: 12,
              color: invalid ? "var(--critical)" : "var(--text-primary)",
              background: "var(--page)",
              border: "1px solid var(--border)",
              borderRadius: 6,
              padding: "7px 9px",
              fontVariantNumeric: "tabular-nums",
            }}
          >
            {invalid ? (
              "Start must come before end"
            ) : (
              <>
                Will show{" "}
                <strong>
                  {stampShort(fromInput(from))} &rarr; {stampShort(fromInput(to))}
                </strong>{" "}
                <span style={{ color: "var(--text-muted)" }}>
                  ({spanLabel(Math.max(1, Math.round((parseUTC(fromInput(to)) - parseUTC(fromInput(from))) / 60_000) + 1))})
                </span>
              </>
            )}
          </div>

          <div style={{ display: "flex", gap: 8 }}>
            <button
              onClick={() => setOpen(false)}
              style={{
                background: "transparent",
                border: "1px solid var(--border)",
                borderRadius: 6,
                padding: "5px 10px",
                fontSize: 12,
                cursor: "pointer",
                color: "var(--text-secondary)",
              }}
            >
              Cancel
            </button>
            {/* Primary action, and it looks like one. It was a 5x12 outline
                button indistinguishable from Cancel, which is thin for the only
                control that commits the change. */}
            <button
              onClick={apply}
              disabled={invalid}
              style={{
                flex: 1,
                background: "var(--brand)",
                border: "1px solid var(--brand)",
                borderRadius: 6,
                padding: "7px 12px",
                fontSize: 12,
                fontWeight: 700,
                cursor: invalid ? "default" : "pointer",
                opacity: invalid ? 0.4 : 1,
                color: "#000",
              }}
            >
              Apply range
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
