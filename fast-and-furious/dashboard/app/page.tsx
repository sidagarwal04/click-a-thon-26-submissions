"use client";

import { useState } from "react";
import useSWR from "swr";
import { CurveChart } from "@/components/CurveChart";
import { ContentPicker } from "@/components/ContentPicker";
import {
  Button,
  Caveat,
  ErrorNote,
  Field,
  Panel,
  Stat,
  StatGrid,
} from "@/components/ui";
import { api, fetcher, num } from "@/lib/api";
import type { ContentInfo, CurveResponse, SimStatus } from "@/lib/types";

export default function LoadSimulator() {
  const [pinned, setPinned] = useState<Map<number, string>>(new Map());
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  const [form, setForm] = useState({
    concurrency: 500,
    userPool: 100_000,
    botShare: 0,
    contentPool: 5000,
    speed: 30,
    rampUp: 30,
    duration: 10,
    maxEvents: 0,
    lateFraction: 0.07,
    dupFraction: 0.005,
    batchSize: 50_000,
    workers: 6,
    async: false,
    sink: "direct" as "direct" | "api",
  });
  const set = <K extends keyof typeof form>(k: K, v: (typeof form)[K]) =>
    setForm((f) => ({ ...f, [k]: v }));

  // Status comes from the loader's in-process counters, so polling it costs no
  // ClickHouse queries.
  const { data: status } = useSWR<SimStatus>("/api/sim", fetcher, {
    refreshInterval: 1500,
  });
  // The curve IS a ClickHouse aggregate, so it polls more slowly.
  const { data: curve } = useSWR<CurveResponse>(
    "/api/curve?minutes=30",
    fetcher,
    { refreshInterval: 5000 },
  );

  const running = status?.running ?? false;
  const summary = status?.summary;

  /** A generator total: an em dash until it exists, never a misleading zero. */
  const gen = (v: number | undefined) => (v === undefined ? "—" : num(v));

  const pick = (c: ContentInfo) =>
    setPinned((m) =>
      new Map(m).set(c.content_id, c.title || String(c.content_id)),
    );
  const unpin = (id: number) =>
    setPinned((m) => {
      const next = new Map(m);
      next.delete(id);
      return next;
    });

  async function start() {
    setBusy(true);
    setError(null);
    try {
      await api.simStart({
        concurrency: form.concurrency,
        user_pool: form.userPool,
        content_ids: [...pinned.keys()],
        content_pool: form.contentPool,
        speed_factor: form.speed,
        ramp_up_seconds: form.rampUp,
        duration_minutes: form.duration,
        max_events: form.maxEvents,
        late_fraction: form.lateFraction,
        dup_fraction: form.dupFraction,
        batch_size: form.batchSize,
        workers: form.workers,
        async: form.async,
        sink: form.sink,
      });
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }

  async function stop() {
    setBusy(true);
    try {
      await api.simStop();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }

  // Two different situations, and conflating them produced a wrong message:
  //   pinned ids  -> "N of M ids were not in the catalogue" (a real problem)
  //   sample size -> the catalogue simply has fewer rows than you asked to sample
  //                  (normal, and not about missing ids at all)
  const pinnedRun = (status?.params?.content_ids?.length ?? 0) > 0;
  const contentShortfall =
    status && status.content_requested > status.content_resolved
      ? status.content_requested - status.content_resolved
      : 0;

  return (
    <>
      <div className="mb-6">
        <h1 className="text-xl font-semibold tracking-tight">Load simulator</h1>
        <p className="mt-1 max-w-[64ch] text-sm text-ink-2">
          Set a viewer count, pick content, and watch traffic land. The generator
          is calibrated to the supplied extract — 40s heartbeat cadence,
          lognormal session durations, background and pause episodes — so this
          carries the same disorder the real stream has.
        </p>
      </div>

      <div className="grid items-start gap-4 lg:grid-cols-[22rem_minmax(0,1fr)]">
        <div className="grid gap-4">
          <Panel title="viewers">
            <div className="grid gap-3">
              <Field
                label="concurrent sessions"
                hint="steady-state simultaneously active sessions — the natural dial for this workload"
              >
                <input
                  type="number"
                  min={1}
                  value={form.concurrency}
                  onChange={(e) => set("concurrency", +e.target.value)}
                />
              </Field>
              <Field
                label="distinct users"
                hint="fewer users than sessions produces multi-session users, which is what makes session and user concurrency differ"
              >
                <input
                  type="number"
                  min={1}
                  value={form.userPool}
                  onChange={(e) => set("userPool", +e.target.value)}
                />
              </Field>
              <Field
                label="bot share"
                hint="share of sessions on one shared identity, reproducing the observed 95-concurrent outlier"
              >
                <input
                  type="number"
                  min={0}
                  max={1}
                  step={0.01}
                  value={form.botShare}
                  onChange={(e) => set("botShare", +e.target.value)}
                />
              </Field>
            </div>
          </Panel>

          <Panel title="content">
            <ContentPicker onPick={pick} selected={new Set(pinned.keys())} />

            {pinned.size > 0 && (
              <ul className="mt-2 flex flex-wrap gap-1.5">
                {[...pinned].map(([id, title]) => (
                  <li key={id}>
                    <button
                      type="button"
                      onClick={() => unpin(id)}
                      title="remove"
                      className="rounded-sm border border-line bg-sunken px-1.5 py-0.5 font-mono text-[0.6875rem] text-ink-2 hover:border-bad hover:text-bad"
                    >
                      {title.slice(0, 26)} ✕
                    </button>
                  </li>
                ))}
              </ul>
            )}

            <div className="mt-3">
              <Field
                label="or sample this many catalogue rows"
                hint="pinning a handful manufactures a live-event spike on one asset; sampling is the realistic spread"
              >
                <input
                  type="number"
                  min={1}
                  disabled={pinned.size > 0}
                  value={form.contentPool}
                  onChange={(e) => set("contentPool", +e.target.value)}
                  className="disabled:opacity-40"
                />
              </Field>
            </div>
          </Panel>

          <Panel title="pace">
            <div className="grid gap-3">
              <div className="grid grid-cols-2 gap-2">
                <Field label="speed ×">
                  <input
                    type="number"
                    min={0}
                    value={form.speed}
                    onChange={(e) => set("speed", +e.target.value)}
                  />
                </Field>
                <Field label="ramp-up s">
                  <input
                    type="number"
                    min={0}
                    value={form.rampUp}
                    onChange={(e) => set("rampUp", +e.target.value)}
                  />
                </Field>
              </div>
              <p className="text-[0.6875rem] leading-snug text-ink-3">
                speed 30 = 30 event-seconds per wall second; 0 = as fast as
                ClickHouse accepts
              </p>

              <div className="grid grid-cols-2 gap-2">
                <Field label="duration min">
                  <input
                    type="number"
                    min={0}
                    value={form.duration}
                    onChange={(e) => set("duration", +e.target.value)}
                  />
                </Field>
                <Field label="max events">
                  <input
                    type="number"
                    min={0}
                    value={form.maxEvents}
                    onChange={(e) => set("maxEvents", +e.target.value)}
                  />
                </Field>
              </div>
              <p className="text-[0.6875rem] leading-snug text-ink-3">
                both 0 = run until stopped
              </p>

              <div className="grid grid-cols-2 gap-2">
                <Field label="late fraction">
                  <input
                    type="number"
                    min={0}
                    max={1}
                    step={0.005}
                    value={form.lateFraction}
                    onChange={(e) => set("lateFraction", +e.target.value)}
                  />
                </Field>
                <Field label="dup fraction">
                  <input
                    type="number"
                    min={0}
                    max={1}
                    step={0.001}
                    value={form.dupFraction}
                    onChange={(e) => set("dupFraction", +e.target.value)}
                  />
                </Field>
              </div>
              <p className="text-[0.6875rem] leading-snug text-ink-3">
                measured: 7% out-of-order, 0.465% byte-identical duplicates. Set
                both to 0 for a perfectly ordered stream when isolating a bug
                from the disorder.
              </p>

              <div className="grid grid-cols-2 gap-2">
                <Field label="batch size">
                  <input
                    type="number"
                    min={1000}
                    value={form.batchSize}
                    onChange={(e) => set("batchSize", +e.target.value)}
                  />
                </Field>
                <Field label="workers">
                  <input
                    type="number"
                    min={1}
                    value={form.workers}
                    onChange={(e) => set("workers", +e.target.value)}
                  />
                </Field>
              </div>

              <Field
                label="write path"
                hint={
                  form.sink === "api"
                    ? "the generator POSTs to /api/events, so every run exercises the ingest endpoint end to end — slower by design, since JSON plus a round trip is what a real producer pays"
                    : "ClickHouse native protocol, straight through chx.Loader"
                }
              >
                <select
                  value={form.sink}
                  onChange={(e) =>
                    set("sink", e.target.value as "direct" | "api")
                  }
                >
                  <option value="direct">direct — native protocol</option>
                  <option value="api">api — POST /api/events</option>
                </select>
              </Field>

              <label className="flex flex-wrap items-center gap-2 text-xs text-ink-2">
                <input
                  type="checkbox"
                  checked={form.async}
                  onChange={(e) => set("async", e.target.checked)}
                />
                async insert
                <span className="text-ink-3">
                  — for small batches, not 50k ones
                </span>
              </label>

              <div className="mt-1 flex gap-2">
                <Button
                  variant="primary"
                  onClick={start}
                  disabled={running || busy}
                  className="flex-1"
                >
                  {busy && !running ? "Starting…" : "Start"}
                </Button>
                <Button
                  variant="danger"
                  onClick={stop}
                  disabled={!running || busy}
                  className="flex-1"
                >
                  Stop
                </Button>
              </div>

              <ErrorNote error={error} />
              {status?.error && <ErrorNote error={new Error(status.error)} />}
            </div>
          </Panel>
        </div>

        <div className="grid gap-4">
          <Panel title="ingest" accent={running ? "live" : "none"}>
            <StatGrid>
              <Stat
                label="state"
                value={running ? "RUNNING" : status?.finished ? "done" : "idle"}
                tone={running ? "live" : "muted"}
              />
              <Stat label="rows sent" value={num(status?.rows)} />
              <Stat
                label="rows/sec"
                value={num(Math.round(status?.rows_per_sec ?? 0))}
              />
              <Stat label="batches" value={num(status?.batches)} />
              <Stat
                label="retries"
                value={num(status?.retries)}
                tone={status?.retries ? "bad" : "muted"}
              />
              <Stat
                label="insert p50"
                value={`${(status?.insert_p50_ms ?? 0).toFixed(0)}ms`}
              />
              <Stat
                label="insert p99"
                value={`${(status?.insert_p99_ms ?? 0).toFixed(0)}ms`}
              />
              <Stat
                label="elapsed"
                value={`${(status?.elapsed_seconds ?? 0).toFixed(0)}s`}
              />
            </StatGrid>

            {/*
              generator.Summary is only returned when Generator.Run finishes, so
              during a run there is nothing to show. Rendering num(undefined) as 0
              would be worse than blank: "sessions 0" next to "rows sent 15,000"
              reads as a bug in the generator rather than a value that has not
              arrived yet.
            */}
            <div className="mt-2">
              <StatGrid>
                <Stat label="sessions" value={gen(summary?.Sessions)} tone={summary ? "plain" : "muted"} />
                <Stat
                  label="peak conc."
                  value={gen(summary?.PeakConcurrency)}
                  tone={summary ? "live" : "muted"}
                />
                <Stat label="still open" value={gen(summary?.SessionsOpen)} tone="muted" />
                <Stat label="late" value={gen(summary?.LateEvents)} tone="muted" />
                <Stat label="duplicates" value={gen(summary?.Duplicates)} tone="muted" />
                <Stat
                  label="dropped"
                  value={gen(summary?.DroppedPastCutoff)}
                  tone={summary?.DroppedPastCutoff ? "bad" : "muted"}
                />
              </StatGrid>
              {!summary && (
                <p className="mt-1.5 text-[0.6875rem] text-ink-3">
                  Generator totals are reported when the run completes — the row
                  counters above are live.
                </p>
              )}
            </div>

            {contentShortfall > 0 &&
              (pinnedRun ? (
                <p className="mt-3 font-mono text-xs text-bad">
                  {contentShortfall} of {status?.content_requested} pinned content
                  ids are not in the catalogue and were ignored.
                </p>
              ) : (
                <p className="mt-3 font-mono text-xs text-ink-3">
                  Catalogue holds {status?.content_resolved} rows, fewer than the{" "}
                  {status?.content_requested} requested — sampled all of them.
                </p>
              ))}
          </Panel>

          <Panel title="sessions active per minute">
            <CurveChart points={curve?.points ?? []} />
            <Caveat>
              This is the{" "}
              <strong className="text-ink-2">heartbeat-lease estimate</strong>,
              not served concurrency. It cannot retract paused or backgrounded
              time — on the supplied extract the same estimator peaks at 3,162
              against an exact 2,305, so read it as a liveness signal only. The
              exact curve needs the minute layer, which is not deployed yet.
            </Caveat>
          </Panel>
        </div>
      </div>
    </>
  );
}
