"use client";

import { useEffect, useState } from "react";
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
import { api, clockTime, durationBetween, seconds } from "@/lib/api";
import type { Action, ContentInfo, SessionState } from "@/lib/types";

/**
 * Buttons grouped by WHICH STATE VARIABLE they move, not alphabetically.
 *
 * That grouping is the point of the page: visibility and playback are
 * independent booleans, and a layout that mixes them into one list of verbs hides
 * the very thing the operator needs to understand.
 */
const GROUPS: { label: string; note?: string; actions: [Action, string][] }[] = [
  {
    label: "lifecycle",
    actions: [
      ["start", "Start"],
      ["end", "End"],
    ],
  },
  {
    label: "playback",
    note: "moves `playing` only",
    actions: [
      ["play", "Play"],
      ["pause", "Pause"],
      ["resume", "Resume"],
    ],
  },
  {
    label: "visibility",
    note: "moves `foreground` only",
    actions: [
      ["background", "Background"],
      ["foreground", "Foreground"],
    ],
  },
  {
    label: "signals",
    note: "renews the lease",
    actions: [
      ["heartbeat", "Heartbeat"],
      ["error", "Error"],
    ],
  },
  {
    label: "classified as liveness",
    note: "neither is a pause",
    actions: [
      ["adbreak", "Ad break"],
      ["ratechange", "Rate change"],
    ],
  },
];

const ADVANCE_PRESETS = [0, 5, 45, 130];

export default function EventStepper() {
  const [platform, setPlatform] = useState("ANDROID_PHONE");
  const [advance, setAdvance] = useState(5);
  const [state, setState] = useState<SessionState | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [pending, setPending] = useState<Action | null>(null);

  const session = state?.session;
  const last = state?.timeline.at(-1);

  // Reattach to the newest server-side session on mount.
  //
  // Sessions live on the Go side, but which one you are driving was pure client
  // state — so a refresh silently orphaned a half-stepped session and offered no
  // way back to it. Restoring the most recently advanced one makes reload
  // harmless, which matters when the whole point is stepping through a sequence.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const { sessions } = await api.manualSessions();
        if (cancelled || !sessions?.length) return;
        const newest = [...sessions].sort((a, b) =>
          a.clock < b.clock ? 1 : -1,
        )[0];
        const restored = await api.manualState(newest.video_session_id);
        if (!cancelled) setState(restored);
      } catch {
        // A fresh server with no sessions is the normal case, not an error.
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  async function mint(c: ContentInfo) {
    setError(null);
    try {
      const s = await api.manualNew(c, platform);
      setState({
        session: s,
        timeline: [],
        intervals: [],
        active_ms: 0,
        timeout_ms: 120_000,
      });
    } catch (e) {
      setError(e);
    }
  }

  async function send(action: Action) {
    if (!session) return;
    setError(null);
    setPending(action);
    try {
      setState(await api.manualEvent(session.video_session_id, action, advance));
    } catch (e) {
      setError(e);
    } finally {
      setPending(null);
    }
  }

  return (
    <>
      <div className="mb-6">
        <h1 className="text-xl font-semibold tracking-tight">Event stepper</h1>
        <p className="mt-1 max-w-[68ch] text-sm text-ink-2">
          Drive one session by hand. Every state value below is computed{" "}
          <strong className="text-ink">in ClickHouse</strong> by the same
          predicate the pipeline uses — not in this page — so what you see is the
          real derivation rather than a second implementation of it.
        </p>
      </div>

      <div className="grid items-start gap-4 lg:grid-cols-[20rem_minmax(0,1fr)]">
        <div className="grid gap-4">
          <Panel title="1 · pick content">
            <ContentPicker
              onPick={mint}
              emptyHint="load the catalogue first"
              selected={session ? new Set([session.content_id]) : undefined}
            />
            <div className="mt-3">
              <Field label="platform">
                <select
                  value={platform}
                  onChange={(e) => setPlatform(e.target.value)}
                >
                  {[
                    "ANDROID_PHONE",
                    "IPHONE",
                    "SONY_ANDROID_TV",
                    "JIO_ANDROID_TV",
                    "Mweb",
                    "FIRE_TV",
                  ].map((p) => (
                    <option key={p}>{p}</option>
                  ))}
                </select>
              </Field>
            </div>
            <p className="mt-2 font-mono text-[0.6875rem] text-ink-3">
              {session
                ? `session ${session.video_session_id.slice(0, 12)}… on ${session.content_title || session.content_id}`
                : "picking a title mints a new session"}
            </p>
          </Panel>

          <Panel title="2 · advance the clock">
            <Field label="seconds before the next event">
              <input
                type="number"
                min={0}
                value={advance}
                onChange={(e) => setAdvance(+e.target.value)}
              />
            </Field>
            <div className="mt-2 flex gap-1.5">
              {ADVANCE_PRESETS.map((s) => (
                <Button
                  key={s}
                  onClick={() => setAdvance(s)}
                  className={`flex-1 !px-2 ${advance === s ? "!border-accent !text-accent" : ""}`}
                >
                  +{s}s
                </Button>
              ))}
            </div>
            <Caveat>
              The lease is {seconds(state?.timeout_ms ?? 120_000)}, so{" "}
              <strong className="text-ink-2">+130s</strong> expires it. A virtual
              event-time clock rather than wall time means you never wait two
              minutes to watch an interval close.
            </Caveat>
          </Panel>
        </div>

        <div className="grid gap-4">
          <Panel title="3 · send events" accent={last?.active ? "live" : "none"}>
            <div className="grid gap-3">
              {GROUPS.map((g) => (
                <div key={g.label}>
                  <div className="mb-1.5 flex items-baseline gap-2">
                    <span className="eyebrow text-ink-3">{g.label}</span>
                    {g.note && (
                      <span className="font-mono text-[0.625rem] text-ink-3">
                        {g.note}
                      </span>
                    )}
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {g.actions.map(([action, label]) => (
                      <Button
                        key={action}
                        onClick={() => send(action)}
                        disabled={!session || pending !== null}
                      >
                        {pending === action ? "…" : label}
                      </Button>
                    ))}
                  </div>
                </div>
              ))}
            </div>
            <ErrorNote error={error} />
          </Panel>

          <Panel title="derived state">
            <StatGrid>
              <Stat
                label="foreground"
                value={last ? (last.foreground ? "yes" : "no") : "—"}
                tone={last?.foreground ? "live" : "muted"}
              />
              <Stat
                label="playing"
                value={last ? (last.playing ? "yes" : "no") : "—"}
                tone={last?.playing ? "live" : "muted"}
              />
              <Stat
                label="active"
                value={last ? (last.active ? "ACTIVE" : "no") : "—"}
                tone={last?.active ? "live" : "muted"}
              />
              <Stat label="clock" value={clockTime(session?.clock)} />
              <Stat
                label="lease until"
                value={clockTime(last?.lease_expires)}
              />
              <Stat label="events sent" value={session?.events_sent ?? 0} />
              <Stat label="intervals" value={state?.intervals.length ?? 0} />
              <Stat
                label="active total"
                value={seconds(state?.active_ms ?? 0)}
                tone="live"
              />
            </StatGrid>

            <div className="mt-3">
              <span className="eyebrow text-ink-3">intervals</span>
              {state && state.intervals.length > 0 ? (
                <ol className="mt-1.5 grid gap-0.5 font-mono text-xs text-ink-2">
                  {state.intervals.map((iv, i) => (
                    <li key={`${iv.start}-${i}`} className="tnum">
                      <span className="text-ink-3">{i + 1}.</span>{" "}
                      {clockTime(iv.start)} → {clockTime(iv.end)}{" "}
                      <span className="text-ink-3">
                        ({durationBetween(iv.start, iv.end)})
                      </span>
                    </li>
                  ))}
                </ol>
              ) : (
                <p className="mt-1.5 font-mono text-xs text-ink-3">none yet</p>
              )}
            </div>
          </Panel>

          <Panel title="timeline · state after each event">
            <div className="overflow-x-auto">
              <table className="w-full border-collapse font-mono text-xs">
                <thead>
                  <tr className="border-b border-line">
                    {[
                      "event time",
                      "event",
                      "signal",
                      "fg",
                      "playing",
                      "lease until",
                      "active",
                    ].map((h) => (
                      <th
                        key={h}
                        className="eyebrow px-2 py-1.5 text-left font-medium text-ink-3"
                      >
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {state && state.timeline.length > 0 ? (
                    state.timeline.map((r, i) => (
                      <tr
                        key={`${r.event_ts}-${i}`}
                        className="border-b border-line-soft last:border-b-0"
                      >
                        <td
                          className={`tnum border-l px-2 py-1 whitespace-nowrap ${
                            r.active ? "border-l-accent" : "border-l-transparent"
                          }`}
                        >
                          {clockTime(r.event_ts)}
                        </td>
                        <td className="px-2 py-1 whitespace-nowrap">{r.event}</td>
                        <td className="px-2 py-1 whitespace-nowrap text-ink-2">
                          {r.signal}
                        </td>
                        <td
                          className={`px-2 py-1 ${r.foreground ? "text-accent" : "text-ink-3"}`}
                        >
                          {r.foreground ? "fg" : "bg"}
                        </td>
                        <td
                          className={`px-2 py-1 ${r.playing ? "text-accent" : "text-ink-3"}`}
                        >
                          {r.playing ? "play" : "stop"}
                        </td>
                        <td className="tnum px-2 py-1 whitespace-nowrap text-ink-3">
                          {clockTime(r.lease_expires)}
                        </td>
                        <td
                          className={`px-2 py-1 ${r.active ? "text-accent" : "text-ink-3"}`}
                        >
                          {r.active ? "ACTIVE" : "—"}
                        </td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan={7} className="px-2 py-3 text-ink-3">
                        no events yet
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>

            <Caveat>
              Try{" "}
              <strong className="text-ink-2">
                Start → Play → Background → Pause → Foreground
              </strong>
              . The session stays inactive after the foreground: it restores
              visibility but not playback. Then <strong className="text-ink-2">Resume</strong>{" "}
              and it flips on. Collapsing those two booleans into one was measured
              at 38,958 wrong event positions across 98.8% of sessions.
            </Caveat>
          </Panel>
        </div>
      </div>
    </>
  );
}
