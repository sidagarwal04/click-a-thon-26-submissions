"use client";

import useSWR from "swr";
import { fetcher } from "@/lib/api";
import type { FleetDimensions, FleetFilter } from "@/lib/types";

const PHASES = ["active", "paused", "backgrounded", "expired", "ended"];

/**
 * The dimension filter, shared by the session listing and the live graph.
 *
 * One component for both, because the two must narrow to the same set — the graph's
 * ClickHouse line is scoped from the session ids the filter selects, so a listing
 * filtered differently from the graph beside it would be answering a different
 * question.
 *
 * Options come from what the fleet actually holds rather than a hardcoded list. A
 * dropdown offering FIRETV when no FIRETV session exists invites a filter that
 * returns nothing and looks like a bug.
 */
export function FleetFilters({
  value,
  onChange,
  showPhase = true,
}: {
  value: FleetFilter;
  onChange: (next: FleetFilter) => void;
  /** The graph hides it: filtering a time series by current phase would drop the
   *  history of sessions that have since changed state, which reads as data loss. */
  showPhase?: boolean;
}) {
  const { data: dims } = useSWR<FleetDimensions>(
    "/api/fleet/dimensions",
    fetcher,
    { refreshInterval: 15_000 },
  );

  const set = (k: keyof FleetFilter, v: string) =>
    onChange({ ...value, [k]: v || undefined });

  const active = Object.values(value).filter(Boolean).length;

  return (
    <div className="flex flex-wrap items-end gap-2">
      <label className="block">
        <span className="mb-1 block text-xs text-ink-2">content id</span>
        <input
          type="text"
          inputMode="numeric"
          value={value.content_id ?? ""}
          onChange={(e) => set("content_id", e.target.value.replace(/\D/g, ""))}
          placeholder="any"
          className="w-28"
          aria-label="Filter by content id"
        />
      </label>

      <Select
        label="video type"
        value={value.video_type}
        options={dims?.video_type ?? []}
        onChange={(v) => set("video_type", v)}
      />
      <Select
        label="platform"
        value={value.platform}
        options={dims?.platform ?? []}
        onChange={(v) => set("platform", v)}
      />
      <Select
        label="app version"
        value={value.app_version}
        options={dims?.app_version ?? []}
        onChange={(v) => set("app_version", v)}
      />
      <Select
        label="country"
        value={value.country}
        options={dims?.country ?? []}
        onChange={(v) => set("country", v)}
      />
      {showPhase && (
        <Select
          label="phase"
          value={value.phase}
          options={PHASES}
          onChange={(v) => set("phase", v)}
        />
      )}

      {active > 0 && (
        <button
          type="button"
          onClick={() => onChange({})}
          className="rounded border border-line px-2 py-2 font-mono text-[0.6875rem] text-ink-3 transition-colors hover:border-accent hover:text-accent"
        >
          clear {active} filter{active === 1 ? "" : "s"}
        </button>
      )}
    </div>
  );
}

function Select({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string | undefined;
  options: string[];
  onChange: (v: string) => void;
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs text-ink-2">{label}</span>
      <select
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value)}
        disabled={options.length === 0}
        aria-label={`Filter by ${label}`}
      >
        <option value="">any</option>
        {options.map((o) => (
          <option key={o} value={o}>
            {o}
          </option>
        ))}
      </select>
    </label>
  );
}
