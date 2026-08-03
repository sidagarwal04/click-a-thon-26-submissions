import type { FleetPhase } from "@/lib/types";

/**
 * A session's lifecycle phase, coloured by whether the pipeline is counting it.
 *
 * `active` is live-coloured; everything else is not counted, and the colour says
 * which kind of not-counted. `expired` gets the warning colour on purpose: unlike
 * paused and backgrounded, nothing in the event stream announced it — the session
 * simply stopped being counted when its lease ran out, which is the case people
 * miss.
 */
const styles: Record<FleetPhase, string> = {
  active: "border-accent/50 bg-accent-wash text-accent",
  paused: "border-line bg-raised text-ink-2",
  backgrounded: "border-line bg-raised text-ink-2",
  expired: "border-bad/40 bg-bad-wash text-bad",
  ended: "border-line-soft bg-sunken text-ink-3",
};

export function PhaseBadge({ phase }: { phase: FleetPhase }) {
  return (
    <span
      className={`inline-block rounded border px-1.5 py-0.5 font-mono text-[0.625rem] whitespace-nowrap ${styles[phase]}`}
    >
      {phase}
    </span>
  );
}
