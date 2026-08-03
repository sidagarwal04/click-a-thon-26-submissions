"use client";

import Link from "next/link";
import { useState } from "react";
import useSWR from "swr";
import { BulkBar } from "@/components/BulkBar";
import { FleetFilters } from "@/components/FleetFilters";
import { PhaseBadge } from "@/components/PhaseBadge";
import { Button, ErrorNote, Panel, Stat, StatGrid } from "@/components/ui";
import { api, clockTime, fetcher, filterQuery, num, seconds } from "@/lib/api";
import type {
  FleetBulkResult,
  FleetCommand,
  FleetFilter,
  FleetListResponse,
} from "@/lib/types";

const PAGE = 50;

/**
 * The session listing.
 *
 * Polls at 2s: every row's phase can change without anyone touching it — a silenced
 * session flips to `expired` when its lease runs out — so a static table would be
 * quietly wrong most of the time.
 *
 * Paged server-side. At the 2,000-per-create ceiling, rendering every row would put
 * tens of thousands of DOM nodes on the page to show information nobody can read.
 */
export default function FleetPage() {
  const [filter, setFilter] = useState<FleetFilter>({});
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  // Selection is a set of ids, not row indexes: the table re-sorts nothing but it
  // does refresh every 2s, and an index-based selection would silently retarget
  // when a session is created or cleared under it.
  const [selected, setSelected] = useState<Set<string>>(new Set());
  // "Everything matching the filter", including rows on pages never visited. The
  // one thing an id list cannot express, so it is a separate mode rather than a
  // very long array.
  const [allMatching, setAllMatching] = useState(false);
  const [bulkBusy, setBulkBusy] = useState<FleetCommand | null>(null);
  const [bulkResult, setBulkResult] = useState<FleetBulkResult | null>(null);

  const qs = filterQuery(filter);
  const { data, mutate } = useSWR<FleetListResponse>(
    `/api/fleet/sessions?offset=${offset}&limit=${PAGE}&${qs}`,
    fetcher,
    { refreshInterval: 2000, keepPreviousData: true },
  );

  const sessions = data?.sessions ?? [];
  const total = data?.total ?? 0;
  const stats = data?.stats;

  // Not memoised: it is a map over at most PAGE strings, and memoising it would
  // need `sessions` to be stable, which it is not while data is loading.
  const pageIDs = sessions.map((s) => s.video_session_id);
  const pageAllSelected =
    pageIDs.length > 0 && pageIDs.every((id) => selected.has(id));

  function clearSelection() {
    setSelected(new Set());
    setAllMatching(false);
    setBulkResult(null);
  }

  function toggleOne(id: string) {
    setAllMatching(false);
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function togglePage() {
    setAllMatching(false);
    setSelected((prev) => {
      const next = new Set(prev);
      if (pageAllSelected) pageIDs.forEach((id) => next.delete(id));
      else pageIDs.forEach((id) => next.add(id));
      return next;
    });
  }

  async function runBulk(command: FleetCommand) {
    setBulkBusy(command);
    setError(null);
    try {
      // Ids for a tick-box selection; the filter only when the selection is
      // explicitly "all matching", which is the case the browser has no ids for.
      const target: { ids: string[] } | { all: true } = allMatching
        ? { all: true }
        : { ids: [...selected] };
      const res = await api.fleetBulk(command, target, filter);
      setBulkResult(res);
      setSelected(new Set());
      setAllMatching(false);
      await mutate();
    } catch (e) {
      setError(e);
    } finally {
      setBulkBusy(null);
    }
  }

  function setModeTab(mode: string | undefined) {
    setFilter({ ...filter, mode });
    setOffset(0);
    clearSelection();
  }

  async function clearEnded() {
    setBusy(true);
    setError(null);
    try {
      await api.fleetClearEnded();
      setOffset(0);
      await mutate();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid gap-4">
      <Panel title="fleet">
        <StatGrid>
          <Stat
            label="active"
            value={num(stats?.active)}
            tone={stats?.active ? "live" : "muted"}
          />
          <Stat label="paused" value={num(stats?.paused)} />
          <Stat label="background" value={num(stats?.backgrounded)} />
          <Stat
            label="expired"
            value={num(stats?.expired)}
            tone={stats?.expired ? "bad" : "muted"}
          />
          <Stat label="ended" value={num(stats?.ended)} tone="muted" />
          <Stat label="total" value={num(stats?.total)} />
          <Stat label="events sent" value={num(stats?.events_sent)} />
        </StatGrid>

        <div className="mt-4 flex flex-wrap items-center gap-2">
          <Link href="/fleet/new/">
            <Button variant="primary">Create sessions</Button>
          </Link>
          <Button
            onClick={clearEnded}
            disabled={busy || !stats?.ended}
            title="Removes ended sessions from this list. Events already in ClickHouse are untouched."
          >
            Clear {num(stats?.ended)} ended
          </Button>
          <Link
            href="/live/"
            className="font-mono text-xs text-accent hover:underline"
          >
            live graph →
          </Link>
        </div>
        <ErrorNote error={error} />
      </Panel>

      {/* Mode tabs, above the dimension filter and not inside it. Mode is not a
          dimension — it is which population you are looking at, and burying it in
          a row of selects would make the two fleets feel like one filtered list. */}
      <div className="flex gap-1" role="tablist" aria-label="Session population">
        <ModeTab
          label="All"
          count={stats?.total}
          on={!filter.mode}
          onClick={() => setModeTab(undefined)}
        />
        <ModeTab
          label="Autonomous"
          count={stats?.autonomous}
          on={filter.mode === "autonomous"}
          onClick={() => setModeTab("autonomous")}
        />
        <ModeTab
          label="Manual"
          count={stats?.manual}
          on={filter.mode === "manual"}
          onClick={() => setModeTab("manual")}
        />
      </div>

      <Panel title="filter">
        <FleetFilters
          value={filter}
          onChange={(next) => {
            setFilter(next);
            // Reset paging: page 3 of the old filter is rarely page 3 of the new
            // one, and landing past the end shows an empty table that looks broken.
            setOffset(0);
            // And drop the selection: keeping ids that the new filter excludes
            // would let a bulk action hit rows that are no longer on screen.
            clearSelection();
          }}
        />
      </Panel>

      <Panel title={`sessions — ${num(total)} matching`}>
        <BulkBar
          count={selected.size}
          allMatching={allMatching}
          total={total}
          busy={bulkBusy}
          result={bulkResult}
          onRun={runBulk}
          onClear={clearSelection}
        />

        {/* Offered only when the page cannot express the whole selection. Ticking
            every box on a 50-row page when 500 match is a reasonable thing to
            mean either way, so the choice is made explicit rather than guessed. */}
        {pageAllSelected && !allMatching && total > pageIDs.length && (
          <p className="mb-3 font-mono text-xs text-ink-3">
            All {num(pageIDs.length)} on this page selected.{" "}
            <button
              type="button"
              onClick={() => setAllMatching(true)}
              className="text-accent hover:underline"
            >
              Select all {num(total)} matching the filter
            </button>
          </p>
        )}

        {sessions.length === 0 ? (
          <p className="font-mono text-xs text-ink-3">
            {total === 0
              ? "no sessions yet — create some."
              : "no sessions on this page."}
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-[0.8125rem]">
              <thead>
                <tr className="border-b border-line text-left">
                  <th className="w-8 pb-2">
                    <input
                      type="checkbox"
                      checked={pageAllSelected}
                      onChange={togglePage}
                      aria-label="Select every session on this page"
                    />
                  </th>
                  <Th>phase</Th>
                  <Th>session</Th>
                  <Th>content</Th>
                  <Th>mode</Th>
                  <Th>platform</Th>
                  <Th right>events</Th>
                  <Th right>active</Th>
                  <Th right>expires</Th>
                </tr>
              </thead>
              <tbody>
                {sessions.map((s) => (
                  <tr
                    key={s.video_session_id}
                    className={`border-b border-line-soft last:border-b-0 hover:bg-sunken ${
                      allMatching || selected.has(s.video_session_id)
                        ? "bg-accent-wash/40"
                        : ""
                    }`}
                  >
                    <td className="py-1.5">
                      <input
                        type="checkbox"
                        checked={allMatching || selected.has(s.video_session_id)}
                        onChange={() => toggleOne(s.video_session_id)}
                        aria-label={`Select session ${s.video_session_id.slice(0, 12)}`}
                      />
                    </td>
                    <Td>
                      <PhaseBadge phase={s.phase} />
                    </Td>
                    <Td>
                      <Link
                        href={`/fleet/session/?id=${s.video_session_id}`}
                        className="font-mono text-xs text-ink-2 transition-colors hover:text-accent hover:underline"
                      >
                        {s.video_session_id.slice(0, 12)}…
                      </Link>
                      {!s.heartbeating && !s.ended && (
                        <span
                          className="ml-2 font-mono text-[0.625rem] text-bad"
                          title="Heartbeats stopped. The pipeline only notices when the lease expires."
                        >
                          silenced
                        </span>
                      )}
                    </Td>
                    <Td>
                      <span className="text-ink-2">
                        {s.content_title || "(untitled)"}
                      </span>
                      <span className="ml-1.5 font-mono text-[0.6875rem] text-ink-3">
                        {s.content_id}
                      </span>
                    </Td>
                    <Td>
                      <span
                        className={`font-mono text-[0.6875rem] ${
                          s.mode === "autonomous" ? "text-ink-2" : "text-ink-3"
                        }`}
                      >
                        {s.mode === "autonomous" ? "auto" : "manual"}
                      </span>
                    </Td>
                    <Td>
                      <span className="font-mono text-[0.6875rem] text-ink-3">
                        {s.platform} · {s.country}
                      </span>
                    </Td>
                    <Td right mono>
                      {num(s.events_sent)}
                    </Td>
                    <Td right mono>
                      {seconds(s.active_ms)}
                    </Td>
                    <Td right mono>
                      {clockTime(s.expires_at)}
                    </Td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {total > PAGE && (
          <div className="mt-3 flex items-center gap-2 font-mono text-xs">
            <Button
              onClick={() => setOffset(Math.max(0, offset - PAGE))}
              disabled={offset === 0}
            >
              ← prev
            </Button>
            <span className="text-ink-3">
              {num(offset + 1)}–{num(Math.min(offset + PAGE, total))} of{" "}
              {num(total)}
            </span>
            <Button
              onClick={() => setOffset(offset + PAGE)}
              disabled={offset + PAGE >= total}
            >
              next →
            </Button>
          </div>
        )}
      </Panel>
    </div>
  );
}

function Th({
  children,
  right,
}: {
  children: React.ReactNode;
  right?: boolean;
}) {
  return (
    <th
      className={`eyebrow pb-2 font-normal text-ink-3 ${right ? "text-right" : ""}`}
    >
      {children}
    </th>
  );
}

function Td({
  children,
  right,
  mono,
}: {
  children: React.ReactNode;
  right?: boolean;
  mono?: boolean;
}) {
  return (
    <td
      className={`py-1.5 ${right ? "text-right" : ""} ${mono ? "tnum font-mono text-xs text-ink-2" : ""}`}
    >
      {children}
    </td>
  );
}

function ModeTab({
  label,
  count,
  on,
  onClick,
}: {
  label: string;
  count: number | undefined;
  on: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      role="tab"
      aria-selected={on}
      onClick={onClick}
      className={`rounded-t border-b-2 px-3 py-1.5 text-[0.8125rem] transition-colors ${
        on
          ? "border-accent text-accent"
          : "border-transparent text-ink-3 hover:text-ink"
      }`}
    >
      {label}
      <span className="tnum ml-1.5 font-mono text-[0.6875rem] text-ink-3">
        {num(count)}
      </span>
    </button>
  );
}
