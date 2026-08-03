import type { ReactNode } from "react";

/**
 * Shared primitives. These exist so spacing and colour decisions live in one
 * place — the failure mode with Tailwind on a multi-page tool is two panels that
 * differ by 2px because two files each spelled out their own padding.
 */

export function Panel({
  title,
  children,
  accent = "accent",
  className = "",
}: {
  title?: string;
  children: ReactNode;
  /** Semantic state, so a panel can read as live or as a warning. */
  accent?: "accent" | "live" | "bad" | "none";
  className?: string;
}) {
  /*
    State is carried by the TITLE, not by a coloured left rule.

    The rule was a 2px `border-l` in the brand colour on every panel — the
    decorative-stripe habit, and the thing that made eight identical cards read
    as eight identical cards. SonyLIV never does it: its surfaces are flat
    fields separated by a hairline and distinguished by what is written on them.
    The state colour now lands on the one element that names the state.
  */
  const titleTone = {
    accent: "text-accent",
    live: "text-accent",
    bad: "text-bad",
    none: "text-ink-3",
  }[accent];

  return (
    <section
      // min-w-0 is required, not defensive. Panels are grid items, and a grid
      // item's default min-width:auto refuses to shrink below its content's
      // min-content width — measured at 537px inside a 350px column on a 390px
      // viewport, which pushed the whole page into horizontal scroll. Allowing the
      // panel to shrink hands the overflow to the wrappers built to scroll it.
      className={`min-w-0 rounded-lg border border-line bg-panel p-4 ${className}`}
    >
      {title && <h2 className={`eyebrow mb-3 ${titleTone}`}>{title}</h2>}
      {children}
    </section>
  );
}

export function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs text-ink-2">{label}</span>
      {children}
      {hint && (
        <span className="mt-1 block text-[0.6875rem] leading-snug text-ink-3">
          {hint}
        </span>
      )}
    </label>
  );
}

export function Button({
  children,
  variant = "default",
  ...rest
}: React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "default" | "primary" | "danger";
}) {
  /*
    Three weights of the same idea, separated by fill rather than by hue —
    which is how a one-colour system stays legible. Primary is the gold filled;
    default is a hairline on the raised surface; danger is the red outlined,
    never filled, because a destructive control should not be the loudest thing
    on the page.
  */
  const styles = {
    default: "border-line bg-raised text-ink hover:border-ink-3",
    primary:
      "border-accent bg-accent font-semibold text-black hover:bg-[#ffb733] hover:border-[#ffb733]",
    danger: "border-bad/50 bg-transparent text-bad hover:border-bad",
  }[variant];

  return (
    <button
      {...rest}
      className={`rounded border px-3 py-2 text-[0.8125rem] transition-colors duration-150 disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:border-line ${styles} ${rest.className ?? ""}`}
    >
      {children}
    </button>
  );
}

/**
 * One measurement. `tone` encodes state in form as well as number, so what needs
 * attention reads at a glance rather than requiring the label to be read.
 */
export function Stat({
  label,
  value,
  tone = "plain",
}: {
  label: string;
  value: ReactNode;
  tone?: "plain" | "live" | "bad" | "muted";
}) {
  const color = {
    plain: "text-ink",
    live: "text-accent",
    bad: "text-bad",
    muted: "text-ink-3",
  }[tone];

  return (
    <div className="rounded border border-line bg-sunken px-2.5 py-2">
      <div className="eyebrow text-ink-3">{label}</div>
      <div className={`tnum mt-1 font-mono text-base ${color}`}>{value}</div>
    </div>
  );
}

export function StatGrid({ children }: { children: ReactNode }) {
  return (
    <div className="grid grid-cols-[repeat(auto-fit,minmax(7rem,1fr))] gap-2">
      {children}
    </div>
  );
}

/** A boolean rendered as a state, not as the word "true". */
export function Flag({
  on,
  onLabel,
  offLabel,
}: {
  on: boolean;
  onLabel: string;
  offLabel: string;
}) {
  return (
    <span className={on ? "text-accent" : "text-ink-3"}>
      {on ? onLabel : offLabel}
    </span>
  );
}

export function ErrorNote({ error }: { error: unknown }) {
  if (!error) return null;
  const msg = error instanceof Error ? error.message : String(error);
  return (
    <p className="mt-3 rounded border border-bad/40 bg-bad-wash px-2.5 py-2 font-mono text-xs whitespace-pre-wrap text-bad">
      {msg}
    </p>
  );
}

/**
 * A claim the reader must not mistake for the served answer. Used for the live
 * curve, which is an approximation and says so.
 *
 * A hairline rule, not the 2px coloured bar this used to be: at 1px it is a
 * typographic mark that sets the note apart from body copy, which is what an
 * aside needs. Above that it becomes the decorative stripe.
 */
export function Caveat({ children }: { children: ReactNode }) {
  return (
    <p className="mt-3 border-l border-line pl-2.5 text-xs leading-relaxed text-ink-3">
      {children}
    </p>
  );
}
