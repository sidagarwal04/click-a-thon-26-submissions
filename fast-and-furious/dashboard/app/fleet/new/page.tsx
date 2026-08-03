"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import useSWR from "swr";
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
import type { ContentInfo, FleetMode, FleetStatsResponse } from "@/lib/types";

/**
 * The session creator.
 *
 * Creates n sessions that share one set of metadata and then run on their own —
 * each emits VideoSessionStart and Play immediately and heartbeats at the cadence
 * until an operator changes its state. So the count entered here is the number the
 * live graph reads a second later, with no ramp to explain away.
 *
 * Metadata is shared across the batch rather than randomised per session because
 * these fields are the graph's filter dimensions. Creating one batch per dimension
 * value is what makes a filter demonstrable; scattering values randomly would make
 * every filter return an uninteresting slice of the same shape.
 */
export default function CreateSessionsPage() {
  const router = useRouter();

  const [content, setContent] = useState<ContentInfo | null>(null);
  const [count, setCount] = useState(200);
  const [platform, setPlatform] = useState("ANDROID_PHONE");
  const [appVersion, setAppVersion] = useState("6.34.8");
  const [country, setCountry] = useState("india");
  const [cadence, setCadence] = useState(30);
  const [ttl, setTtl] = useState(60);
  const [mode, setMode] = useState<FleetMode>("manual");

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const { data: stats } = useSWR<FleetStatsResponse>(
    "/api/fleet/stats",
    fetcher,
  );

  const maxCreate = stats?.max_create ?? 2000;
  const maxLive = stats?.max_live ?? 10000;
  const live = stats?.stats.total ?? 0;
  const headroom = maxLive - live;

  const tooMany = count > headroom;
  const canSubmit =
    content !== null && count > 0 && count <= maxCreate && !tooMany && !busy;

  async function submit() {
    if (!content) return;
    setBusy(true);
    setError(null);
    try {
      await api.fleetCreate({
        count,
        content_id: content.content_id,
        content_title: content.title,
        platform,
        app_version: appVersion,
        country,
        cadence_seconds: cadence,
        ttl_minutes: ttl,
        mode,
      });
      router.push("/fleet/");
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }

  // Steady-state write rate. Worth showing before the button is pressed: 2,000
  // sessions at a 5s cadence is 400 events/sec, which is a different proposition
  // from the same 2,000 at 30s.
  const eventsPerSec = cadence > 0 ? count / cadence : 0;

  return (
    <div className="grid gap-4 lg:grid-cols-[1fr_20rem]">
      <div className="grid gap-4">
        <Panel title="who drives">
          <div className="grid gap-2 sm:grid-cols-2">
            <ModeCard
              on={mode === "manual"}
              onClick={() => setMode("manual")}
              title="Manual"
              body="Sessions hold whatever state you put them in and just heartbeat. You pause, background, silence and end them by hand."
            />
            <ModeCard
              on={mode === "autonomous"}
              onClick={() => setMode("autonomous")}
              title="Autonomous"
              body="Sessions pause, background and end themselves from the measured rates — 2.5 pauses and 1.35 backgrounds per session, 12-minute median life. A large batch of these is the load test."
            />
          </div>
          <Caveat>
            Either way every session stays individually addressable: an autonomous
            session can still be opened, paused by hand, or silenced. The mode
            decides who acts, not whether you can.
          </Caveat>
        </Panel>

        <Panel title="content">
          <ContentPicker
            onPick={setContent}
            selected={content ? new Set([content.content_id]) : undefined}
            emptyHint="no matches — is the catalogue loaded?"
          />
          {content && (
            <p className="mt-2 font-mono text-xs text-ink-2">
              {content.title || "(untitled)"}{" "}
              <span className="text-ink-3">
                · {content.content_id} · {content.video_type}
              </span>
            </p>
          )}
          <Caveat>
            Required, and resolved against the catalogue server-side — the{" "}
            <code>video_type</code> the graph filters on comes from the
            catalogue row, not from this page.
          </Caveat>
        </Panel>

        <Panel title="session metadata">
          <div className="grid gap-3 sm:grid-cols-3">
            <Field label="platform">
              <input
                type="text"
                value={platform}
                onChange={(e) => setPlatform(e.target.value)}
              />
            </Field>
            <Field label="app version">
              <input
                type="text"
                value={appVersion}
                onChange={(e) => setAppVersion(e.target.value)}
              />
            </Field>
            <Field label="country">
              <input
                type="text"
                value={country}
                onChange={(e) => setCountry(e.target.value)}
              />
            </Field>
          </div>
          <Caveat>
            Free-form, and written verbatim into <code>events_raw</code> — these
            are the columns the live graph filters on. Create a second batch with
            a different value to have something to filter between.
          </Caveat>
        </Panel>

        <Panel title="how many, how often">
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="sessions" hint={`1 to ${num(maxCreate)} per submit`}>
              <input
                type="number"
                min={1}
                max={maxCreate}
                value={count}
                onChange={(e) => setCount(Math.max(0, +e.target.value))}
              />
            </Field>
            <Field
              label="heartbeat cadence (seconds)"
              hint="5 to 600. The measured clients ping about every 30s."
            >
              <input
                type="number"
                min={5}
                max={600}
                value={cadence}
                onChange={(e) => setCadence(Math.max(0, +e.target.value))}
              />
            </Field>
          </div>

          <div className="mt-3">
            <Field
              label="session lifetime (minutes)"
              hint="1 to 1440. At the end the simulator writes a real VideoSessionEnd. There is no 'never': a fleet without a lifetime keeps writing into events_raw long after anyone is watching."
            >
              <input
                type="number"
                min={1}
                max={1440}
                value={ttl}
                onChange={(e) => setTtl(Math.max(0, +e.target.value))}
              />
            </Field>
          </div>

          <div className="mt-3">
            <StatGrid>
              <Stat label="steady rate" value={`${eventsPerSec.toFixed(1)}/s`} />
              <Stat label="mode" value={mode} tone={mode === "autonomous" ? "live" : "muted"} />
              <Stat label="events total" value={num(Math.round(eventsPerSec * ttl * 60))} />
              <Stat
                label="live now"
                value={num(live)}
                tone={live > 0 ? "live" : "muted"}
              />
              <Stat
                label="headroom"
                value={num(headroom)}
                tone={tooMany ? "bad" : "muted"}
              />
            </StatGrid>
          </div>

          {tooMany && (
            <p className="mt-3 font-mono text-xs text-bad">
              {num(count)} would exceed the {num(maxLive)} cap. Clear ended
              sessions on the sessions page first.
            </p>
          )}

          <div className="mt-4 flex items-center gap-2">
            <Button variant="primary" onClick={submit} disabled={!canSubmit}>
              {busy ? "creating…" : `Create ${num(count)} sessions`}
            </Button>
            {!content && (
              <span className="font-mono text-xs text-ink-3">
                pick content first
              </span>
            )}
          </div>

          <ErrorNote error={error} />
        </Panel>
      </div>

      <Panel title="what happens next" accent="live" className="h-fit">
        <ol className="grid gap-2.5 text-[0.8125rem] leading-relaxed text-ink-2">
          <li>
            <span className="text-ink">Start and Play</span> are written at the
            same instant, so every session is active immediately.
          </li>
          <li>
            Each session then <span className="text-ink">heartbeats on its own</span>{" "}
            at the cadence, with the first tick staggered across it so the insert
            rate is flat rather than a spike.
          </li>
          <li>
            On the sessions page you can pause, background,{" "}
            <span className="text-ink">silence</span> or end any one of them.
          </li>
          <li>
            {mode === "autonomous" ? (
              <>
                Each session then{" "}
                <span className="text-ink">runs its own lifecycle</span> — pauses,
                backgrounds and an ending drawn from the measured distributions.
              </>
            ) : (
              <>
                Each session then holds its state until{" "}
                <span className="text-ink">you change it</span>.
              </>
            )}
          </li>
          <li>
            After <span className="text-ink">{ttl} minutes</span> each session
            ends itself with a real <code>VideoSessionEnd</code>, so a fleet left
            running stops on its own.
          </li>
          <li>
            State is written to <code>fleet_sessions</code>, so a restart restores
            the fleet rather than losing it while its events stay in{" "}
            <code>events_raw</code>.
          </li>
        </ol>
        <Caveat>
          Events go to <code>events_raw</code> through the same ingest path a real
          producer uses, so nothing here is a shortcut around validation or
          deduplication.
        </Caveat>
      </Panel>
    </div>
  );
}

/**
 * The mode choice, as two cards rather than a select.
 *
 * It is the first decision on the page and it changes what every field below
 * means, so it gets room to explain itself. A two-option dropdown labelled "mode"
 * would hide the only thing a first-time reader needs to know.
 */
function ModeCard({
  on,
  onClick,
  title,
  body,
}: {
  on: boolean;
  onClick: () => void;
  title: string;
  body: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={on}
      className={`rounded border p-3 text-left transition-colors ${
        on
          ? "border-accent bg-accent-wash"
          : "border-line bg-sunken hover:border-ink-3"
      }`}
    >
      <span
        className={`block text-[0.8125rem] font-semibold ${on ? "text-accent" : "text-ink"}`}
      >
        {title}
      </span>
      <span className="mt-1 block text-[0.6875rem] leading-snug text-ink-3">
        {body}
      </span>
    </button>
  );
}
