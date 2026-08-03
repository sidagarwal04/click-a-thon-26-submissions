"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useSyncExternalStore } from "react";
import { getToken, setToken } from "@/lib/api";
import { ClickHouseMark, SonyLivMark } from "./BrandMarks";

/**
 * Shows whether a token is stored, and allows clearing it.
 *
 * Only rendered once a token exists: on loopback there is no token and no need
 * for one, so an empty control would be noise. Clearing reloads for the same
 * reason saving does -- every poll has to pick up the changed header.
 */
function TokenBadge() {
  // useSyncExternalStore, not state-in-an-effect: localStorage does not exist during
  // the static export's prerender, so the server snapshot is "" and the prerendered
  // HTML cannot disagree with the first client render. It also picks up a token set
  // in another tab, which the effect version could not.
  const token = useSyncExternalStore(
    (onChange) => {
      window.addEventListener("storage", onChange);
      return () => window.removeEventListener("storage", onChange);
    },
    getToken,
    () => "",
  );

  if (!token) return null;
  return (
    <button
      onClick={() => {
        setToken("");
        window.location.reload();
      }}
      title="Clear the stored bearer token"
      className="rounded border border-line px-2 py-0.5 font-mono text-[0.6875rem] text-ink-3 transition-colors hover:border-bad hover:text-bad"
    >
      token set ×
    </button>
  );
}

/**
 * The collaboration lockup: the real `liv` mark over the real ClickHouse wordmark.
 *
 * Both are the parties' own assets — SonyLIV's header PNG and ClickHouse's own
 * SVG — rather than lettering set in Inter and hoped to pass. Two brands in one
 * lockup is exactly where an approximation shows.
 *
 * Stacked, because side by side two wordmarks read as a hyphenated product name
 * while stacked with the × between them reads as two parties. The left edges
 * align and the gap is tight, which is what binds them into one mark instead of
 * two logos that happen to be near each other.
 *
 * The × stays typographic and gold. It is a multiplication sign doing the job it
 * exists for — the one case where a glyph is not standing in for an icon — and
 * it is the only place the signal colour appears in the header, so the eye reads
 * the join rather than the chrome.
 *
 * The ClickHouse mark inherits `currentColor` at ink-2, deliberately a step below
 * the liv mark's own gold: a lockup where both parties shout has no hierarchy,
 * and this is the SonyLIV problem statement.
 */
function Lockup() {
  return (
    <span
      className="flex shrink-0 flex-col gap-1"
      aria-label="SonyLIV × ClickHouse"
      title="SonyLIV × ClickHouse"
    >
      <span className="flex items-center gap-1.5">
        <SonyLivMark />
        <span className="text-[0.8125rem] leading-none text-accent">×</span>
      </span>
      <span className="text-ink-2">
        <ClickHouseMark />
      </span>
    </span>
  );
}

// Ordered by workflow, not by age: create a fleet, watch it, control it. The two
// original dashboards come last because they answer different questions — throughput
// for the load simulator, one-event-at-a-time semantics for the stepper.
const routes: { href: string; label: string; also?: string[] }[] = [
  { href: "/fleet/new", label: "Create" },
  // Session detail is a query-param page under /fleet/session, so it needs naming
  // here — otherwise opening a session lights up no tab at all.
  { href: "/fleet", label: "Sessions", also: ["/fleet/session"] },
  { href: "/live", label: "Live" },
  { href: "/", label: "Load test" },
  { href: "/manual", label: "Stepper" },
];

/**
 * Trailing slashes are stripped before comparing.
 *
 * next.config sets trailingSlash: true, so usePathname reports "/fleet/" while the
 * hrefs here are written without one. Comparing them raw would leave every tab
 * inactive.
 */
const norm = (p: string) => (p.length > 1 ? p.replace(/\/+$/, "") : p);

export function Nav() {
  const pathname = usePathname();

  return (
    <header className="sticky top-0 z-10 border-b border-line bg-ground/90 backdrop-blur">
      <div className="mx-auto flex w-full max-w-[80rem] items-center gap-4 px-5 py-3 sm:gap-6">
        <Lockup />

        <nav
          className="flex min-w-0 gap-1 overflow-x-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
          aria-label="Dashboards"
        >
          {routes.map((r) => {
            // Exact match, not startsWith: "/" is a prefix of every route, so a
            // prefix test would light up every tab everywhere.
            const here = norm(pathname);
            const active =
              here === norm(r.href) || (r.also?.includes(here) ?? false);
            return (
              <Link
                key={r.href}
                href={r.href}
                aria-current={active ? "page" : undefined}
                className={`rounded px-2.5 py-1 text-[0.8125rem] whitespace-nowrap transition-colors ${
                  active
                    ? "bg-accent-wash text-accent"
                    : "text-ink-2 hover:text-ink"
                }`}
              >
                {r.label}
              </Link>
            );
          })}
        </nav>

        {/* Just the timezone. "writes to events_raw" was stating the obvious —
            every page here writes to events_raw, so a permanent banner saying so
            carried no information and spent header width doing it. UTC stays
            because the tables are full of bare clock times and nothing else on
            the page says which zone they are in. */}
        <span className="ml-auto font-mono text-[0.6875rem] text-ink-3">UTC</span>

        <TokenBadge />
      </div>
    </header>
  );
}
