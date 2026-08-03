"use client";

import { Button } from "./ui";
import { num } from "@/lib/api";
import type { FleetBulkResult, FleetCommand } from "@/lib/types";

/**
 * Bulk actions over the current selection.
 *
 * Only rendered when something is selected, so the table is not permanently
 * wearing a disabled toolbar.
 *
 * The three buttons are the ones asked for. Pause and Resume are separate rather
 * than one toggle: a mixed selection has no toggle state, and guessing one would
 * resume sessions the operator meant to pause. Both are no-ops on sessions already
 * in the target state, which the server skips without writing an event.
 */
export function BulkBar({
  count,
  allMatching,
  total,
  busy,
  result,
  onRun,
  onClear,
}: {
  count: number;
  /** True when the selection is "everything matching the filter", not a row list. */
  allMatching: boolean;
  total: number;
  busy: FleetCommand | null;
  result: FleetBulkResult | null;
  onRun: (command: FleetCommand) => void;
  onClear: () => void;
}) {
  const n = allMatching ? total : count;
  if (n === 0) return null;

  return (
    <div className="mb-3 flex flex-wrap items-center gap-2 rounded border border-accent-dim bg-accent-wash px-3 py-2">
      <span className="font-mono text-xs text-accent">
        {allMatching ? `all ${num(total)} matching` : `${num(count)} selected`}
      </span>

      <Button onClick={() => onRun("pause")} disabled={!!busy}>
        {busy === "pause" ? "pausing…" : "Pause"}
      </Button>
      <Button onClick={() => onRun("resume")} disabled={!!busy}>
        {busy === "resume" ? "resuming…" : "Resume"}
      </Button>
      <Button
        variant="danger"
        onClick={() => onRun("end")}
        disabled={!!busy}
        title="Writes VideoSessionEnd to each. Rows stay in the list, marked ended."
      >
        {busy === "end" ? "ending…" : "Delete"}
      </Button>

      <button
        type="button"
        onClick={onClear}
        className="font-mono text-[0.6875rem] text-ink-3 hover:text-ink"
      >
        clear selection
      </button>

      {result && (
        <span className="ml-auto font-mono text-[0.6875rem] text-ink-2">
          {num(result.applied)} applied
          {result.skipped > 0 && (
            <span
              className="text-ink-3"
              title="Already in the target state, or ended. Skipped rather than written, so a bulk pause does not flood events_raw with events that change nothing."
            >
              {" "}
              · {num(result.skipped)} skipped
            </span>
          )}
          {result.unknown > 0 && (
            <span className="text-bad"> · {num(result.unknown)} gone</span>
          )}
          {" · "}
          {num(result.wrote)} events
        </span>
      )}
    </div>
  );
}
