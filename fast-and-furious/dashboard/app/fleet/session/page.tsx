"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useState, useSyncExternalStore } from "react";
import useSWR from "swr";
import { PhaseBadge } from "@/components/PhaseBadge";
import { Button, Caveat, ErrorNote, Panel, Stat, StatGrid } from "@/components/ui";
import { api, clockTime, fetcher, num, seconds } from "@/lib/api";
import type { FleetCommand, FleetSession } from "@/lib/types";

/**
 * A query parameter rather than a dynamic /fleet/session/[id] route.
 *
 * Not a preference: `output: 'export'` renders a page per route at build time, and a
 * dynamic segment needs generateStaticParams to enumerate them. Session ids are
 * minted at runtime, so there is nothing to enumerate. useSearchParams needs a
 * Suspense boundary because it forces client rendering of everything below it.
 */
export default function SessionPage() {
  return (
    <Suspense
      fallback={
        <Panel>
          <p className="font-mono text-xs text-ink-3">loading…</p>
        </Panel>
      }
    >
      <SessionDetail />
    </Suspense>
  );
}

/**
 * Wall clock, ticking once a second. Null until mounted.
 *
 * useSyncExternalStore rather than state-in-an-effect, because the clock IS an
 * external mutable source and this is what that hook is for. The server snapshot is
 * null so the prerendered HTML carries no timestamp and cannot disagree with the
 * first client render, and the snapshot is quantised to the second so it stays
 * referentially stable between ticks — an unquantised Date.now() would differ on
 * every read and re-render forever.
 */
function useNow(): number | null {
  return useSyncExternalStore(
    (onChange) => {
      const t = setInterval(onChange, 1000);
      return () => clearInterval(t);
    },
    () => Math.floor(Date.now() / 1000) * 1000,
    () => null,
  );
}

function SessionDetail() {
  const id = useSearchParams().get("id") ?? "";
  const now = useNow();

  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState<FleetCommand | null>(null);

  const { data, mutate } = useSWR<{ session: FleetSession; timeout_ms: number }>(
    id ? `/api/fleet/sessions/${id}` : null,
    fetcher,
    { refreshInterval: 1000, keepPreviousData: true },
  );

  if (!id) {
    return (
      <Panel accent="bad">
        <p className="font-mono text-xs text-bad">
          No session id in the URL. Pick one from the{" "}
          <Link href="/fleet/" className="text-accent hover:underline">
            sessions list
          </Link>
          .
        </p>
      </Panel>
    );
  }

  const s = data?.session;

  async function send(command: FleetCommand) {
    setBusy(command);
    setError(null);
    try {
      const res = await api.fleetCommand(id, command);
      await mutate({ session: res.session, timeout_ms: data?.timeout_ms ?? 0 });
    } catch (e) {
      setError(e);
    } finally {
      setBusy(null);
    }
  }

  if (!s) {
    return (
      <Panel>
        <p className="font-mono text-xs text-ink-3">loading session {id.slice(0, 12)}…</p>
        <ErrorNote error={error} />
      </Panel>
    );
  }

  const leaseMS = now ? new Date(s.lease_expires).getTime() - now : null;
  const withinLease = leaseMS === null ? null : leaseMS > 0;
  // Two different clocks: the lease is 120s of missed heartbeats, the lifetime is
  // the session's TTL. Showing both stops them being mistaken for each other.
  const ttlMS = now ? new Date(s.expires_at).getTime() - now : null;

  return (
    <div className="grid gap-4">
      <Panel title="session">
        <div className="flex flex-wrap items-center gap-3">
          <PhaseBadge phase={s.phase} />
          <code className="font-mono text-xs break-all text-ink-2">
            {s.video_session_id}
          </code>
          <Link
            href="/fleet/"
            className="ml-auto font-mono text-xs text-accent hover:underline"
          >
            ← all sessions
          </Link>
        </div>

        <div className="mt-3 grid gap-1 font-mono text-xs text-ink-3 sm:grid-cols-2">
          <span>
            content <span className="text-ink-2">{s.content_id}</span>{" "}
            {s.content_title && `· ${s.content_title}`}{" "}
            {s.video_type && `· ${s.video_type}`}
          </span>
          <span>
            {s.platform} · {s.app_version} · {s.country}
          </span>
          <span>
            started <span className="text-ink-2">{clockTime(s.start_epoch)}</span>
          </span>
          <span>
            cadence <span className="text-ink-2">{s.cadence_seconds}s</span>
          </span>
          <span>
            expires <span className="text-ink-2">{clockTime(s.expires_at)}</span>
          </span>
        </div>

        <div className="mt-4">
          <StatGrid>
            <Stat
              label="active"
              value={s.active ? "yes" : "no"}
              tone={s.active ? "live" : "muted"}
            />
            <Stat label="active time" value={seconds(s.active_ms)} />
            <Stat label="events sent" value={num(s.events_sent)} />
            <Stat
              label="lease"
              value={
                leaseMS === null
                  ? "—"
                  : leaseMS > 0
                    ? `${Math.ceil(leaseMS / 1000)}s left`
                    : "expired"
              }
              tone={withinLease === false ? "bad" : "plain"}
            />
            <Stat label="intervals" value={num(s.intervals.length)} />
            <Stat
              label="lifetime left"
              value={
                ttlMS === null
                  ? "—"
                  : ttlMS > 0
                    ? `${Math.ceil(ttlMS / 60000)}m`
                    : "expired"
              }
              tone={ttlMS !== null && ttlMS <= 0 ? "muted" : "plain"}
            />
          </StatGrid>
        </div>
      </Panel>

      <Panel title="controls">
        <div className="flex flex-wrap gap-2">
          {s.playing ? (
            <Button onClick={() => send("pause")} disabled={s.ended || !!busy}>
              Pause
            </Button>
          ) : (
            <Button onClick={() => send("resume")} disabled={s.ended || !!busy}>
              Resume
            </Button>
          )}

          {s.foreground ? (
            <Button onClick={() => send("background")} disabled={s.ended || !!busy}>
              Background
            </Button>
          ) : (
            <Button onClick={() => send("foreground")} disabled={s.ended || !!busy}>
              Foreground
            </Button>
          )}

          {s.heartbeating ? (
            <Button
              onClick={() => send("silence")}
              disabled={s.ended || !!busy}
              title="Stops heartbeats and writes nothing. The pipeline only notices when the lease expires."
            >
              Stop heartbeats
            </Button>
          ) : (
            <Button onClick={() => send("unsilence")} disabled={s.ended || !!busy}>
              Resume heartbeats
            </Button>
          )}

          <Button
            variant="danger"
            onClick={() => send("end")}
            disabled={s.ended || !!busy}
            title="Writes VideoSessionEnd. The row stays in the list, marked ended."
            className="ml-auto"
          >
            Delete (end session)
          </Button>
        </div>

        <Caveat>
          <span className="text-ink-2">Stop heartbeats</span> writes no event at
          all — it is the app-killed case, and the only control here the pipeline
          cannot observe directly. Watch the lease count down and the phase flip
          to <code>expired</code> on its own.
        </Caveat>

        <ErrorNote error={error} />
      </Panel>

      <Panel title="why it is or is not counted">
        <ul className="grid gap-1.5 font-mono text-xs">
          <Term ok={s.started} label="started" detail="a session_start was seen" />
          <Term ok={!s.ended} label="not ended" detail="no session_end yet" />
          <Term
            ok={s.foreground}
            label="foreground"
            detail="AppBackgrounded clears this, AppForegrounded restores it"
          />
          <Term
            ok={s.playing}
            label="playing"
            detail="pause and error clear this, play and resume restore it"
          />
          <Term
            ok={withinLease}
            label="inside the lease"
            detail={`expires ${clockTime(s.lease_expires)} · last eligible signal ${clockTime(s.last_eligible)}`}
          />
        </ul>
        <Caveat>
          All five must hold. They are the same five terms the pipeline evaluates,
          which is why <code>foreground</code> and <code>playing</code> are
          separate — collapsing them into one state was measured at 38,958
          disagreements across 98.8% of sessions, every one an overcount.
        </Caveat>
      </Panel>

      <Panel title="recorded active intervals">
        {s.intervals.length === 0 ? (
          <p className="font-mono text-xs text-ink-3">
            none closed yet{s.active && " — the current one is still open"}
          </p>
        ) : (
          <ul className="grid gap-1 font-mono text-xs">
            {s.intervals.map((iv, i) => (
              <li key={i} className="flex items-baseline gap-3">
                <span className="text-ink-3">{String(i + 1).padStart(2, "0")}</span>
                <span className="text-ink-2">
                  {clockTime(iv.start)} → {clockTime(iv.end)}
                </span>
                <span className="ml-auto text-ink-3">
                  {seconds(
                    new Date(iv.end).getTime() - new Date(iv.start).getTime(),
                  )}
                </span>
              </li>
            ))}
          </ul>
        )}
        <Caveat>
          Recorded at the moment of each transition, not inferred from the event
          stream — which is what makes these usable as the reference the live
          graph compares ClickHouse against.
        </Caveat>
      </Panel>
    </div>
  );
}

function Term({
  ok,
  label,
  detail,
}: {
  ok: boolean | null;
  label: string;
  detail: string;
}) {
  const mark = ok === null ? "·" : ok ? "✓" : "✗";
  const tone = ok === null ? "text-ink-3" : ok ? "text-accent" : "text-bad";
  return (
    <li className="flex items-baseline gap-2">
      <span className={`${tone} w-3`}>{mark}</span>
      <span className={ok === false ? "text-bad" : "text-ink-2"}>{label}</span>
      <span className="text-ink-3">— {detail}</span>
    </li>
  );
}
