"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { ContentInfo } from "@/lib/types";

/**
 * Catalogue search. Shared by both dashboards, because "which content" is the
 * one question they both ask.
 *
 * Debounced at 200ms: the search hits ClickHouse with a
 * positionCaseInsensitive scan, so a request per keystroke would be a scan per
 * keystroke.
 */
export function ContentPicker({
  onPick,
  selected,
  emptyHint,
}: {
  onPick: (c: ContentInfo) => void;
  /** ids already chosen, rendered as such so a double-pick is obvious */
  selected?: Set<number>;
  emptyHint?: string;
}) {
  const [q, setQ] = useState("");
  const [items, setItems] = useState<ContentInfo[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const timer = setTimeout(async () => {
      setLoading(true);
      try {
        const { items } = await api.content(q);
        if (!cancelled) {
          setItems(items ?? []);
          setError(null);
        }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    }, 200);

    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [q]);

  return (
    <div>
      <input
        type="search"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="title, category, or content id"
        aria-label="Search the content catalogue"
        autoComplete="off"
      />

      <div className="mt-2 max-h-44 overflow-y-auto rounded border border-line">
        {error ? (
          <p className="px-2.5 py-2 font-mono text-xs text-bad">{error}</p>
        ) : items.length === 0 ? (
          <p className="px-2.5 py-2 font-mono text-xs text-ink-3">
            {loading ? "searching…" : (emptyHint ?? "no matches")}
          </p>
        ) : (
          <ul>
            {items.map((c) => {
              const isPicked = selected?.has(c.content_id) ?? false;
              return (
                <li key={c.content_id}>
                  <button
                    type="button"
                    onClick={() => onPick(c)}
                    className="flex w-full items-baseline gap-2 border-b border-line-soft px-2.5 py-1.5 text-left text-[0.8125rem] last:border-b-0 hover:bg-sunken"
                  >
                    <span className={isPicked ? "text-accent" : "text-ink"}>
                      {c.title || "(untitled)"}
                    </span>
                    <span className="tnum ml-auto font-mono text-[0.6875rem] whitespace-nowrap text-ink-3">
                      {c.content_id} · {c.video_type}
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
}
