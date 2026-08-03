import { X } from "lucide-react";
import { useEffect, useState } from "react";
import { fetchContextVersion } from "../api";
import type { ContextDocument, JsonValue } from "../types";

type JsonObject = Record<string, JsonValue>;

const object = (value: JsonValue | undefined): JsonObject =>
  value && typeof value === "object" && !Array.isArray(value) ? (value as JsonObject) : {};

/** One comparable line: `key` decides identity, `text` is what gets rendered. */
type Line = { key: string; text: string };
type DiffLine = Line & { state: "added" | "removed" | "same" };
type Section = { title: string; lines: DiffLine[]; added: number; removed: number };

function entityLines(document: ContextDocument | null): Line[] {
  return (document?.entities ?? []).map((raw) => {
    const entity = object(raw);
    const name = String(entity.name ?? entity.table_name ?? "entity");
    const dimensions = Array.isArray(entity.dimensions) ? entity.dimensions.map(String) : [];
    return {
      key: name,
      text: `${name} (${String(entity.table_name ?? "—")}) pk=${String(entity.primary_key ?? "—")}${dimensions.length ? ` dims=[${dimensions.join(", ")}]` : ""}`,
    };
  });
}

function relationshipLines(document: ContextDocument | null): Line[] {
  return (document?.relationships ?? []).map((raw) => {
    const link = object(raw);
    const source = `${String(link.source_table ?? "?")}.${String(link.source_column ?? "?")}`;
    const target = `${String(link.target_table ?? "?")}.${String(link.target_column ?? "?")}`;
    return { key: `${source}->${target}`, text: `${source} → ${target}` };
  });
}

function metricLines(document: ContextDocument | null): Line[] {
  return (document?.metrics ?? []).map((raw) => {
    const metric = object(raw);
    const name = String(metric.name ?? "metric");
    return {
      key: name,
      text: `${name} = ${String(metric.numerator ?? "—")} / ${String(metric.denominator ?? "—")}`,
    };
  });
}

function conventionLines(document: ContextDocument | null): Line[] {
  return (document?.naming_conventions ?? []).map((value) => ({ key: String(value), text: String(value) }));
}

function knownIssueLines(document: ContextDocument | null): Line[] {
  return (document?.known_issues ?? []).map((raw) => {
    const issue = object(raw);
    const text = String(issue.description ?? issue.name ?? JSON.stringify(issue));
    return { key: text, text };
  });
}

/** Compare by key so an unchanged item stays context, not a remove+add pair. */
function diffLines(before: Line[], after: Line[]): DiffLine[] {
  const beforeByKey = new Map(before.map((line) => [line.key, line]));
  const afterKeys = new Set(after.map((line) => line.key));
  const removed: DiffLine[] = before
    .filter((line) => !afterKeys.has(line.key))
    .map((line) => ({ ...line, state: "removed" as const }));
  const rest: DiffLine[] = after.map((line) => {
    const previous = beforeByKey.get(line.key);
    if (!previous) return { ...line, state: "added" as const };
    // Same identity but a changed body still reads as a modification.
    return { ...line, state: previous.text === line.text ? ("same" as const) : ("added" as const) };
  });
  // Natural order is preserved so each change keeps the neighbours that give it
  // meaning; the renderer collapses the runs of untouched lines between hunks.
  return [...removed, ...rest];
}

/** Keep every change plus `padding` unchanged neighbours; collapse the rest. */
function toHunks(lines: DiffLine[], padding = 1): Array<DiffLine | { gap: number }> {
  const keep = new Set<number>();
  lines.forEach((line, index) => {
    if (line.state === "same") return;
    for (let offset = -padding; offset <= padding; offset += 1) {
      const neighbour = index + offset;
      if (neighbour >= 0 && neighbour < lines.length) keep.add(neighbour);
    }
  });
  const output: Array<DiffLine | { gap: number }> = [];
  let hidden = 0;
  lines.forEach((line, index) => {
    if (keep.has(index)) {
      if (hidden > 0) { output.push({ gap: hidden }); hidden = 0; }
      output.push(line);
    } else {
      hidden += 1;
    }
  });
  if (hidden > 0) output.push({ gap: hidden });
  return output;
}

const GROUPS: Array<{ title: string; extract: (doc: ContextDocument | null) => Line[] }> = [
  { title: "Entities", extract: entityLines },
  { title: "Relationships", extract: relationshipLines },
  { title: "Metrics", extract: metricLines },
  { title: "Naming conventions", extract: conventionLines },
  { title: "Known issues", extract: knownIssueLines },
];

function buildSections(mode: "snapshot" | "diff", before: ContextDocument | null, after: ContextDocument | null): Section[] {
  return GROUPS.map(({ title, extract }) => {
    // A snapshot is not a comparison: every line is plain content.
    const lines: DiffLine[] = mode === "snapshot"
      ? extract(after).map((line) => ({ ...line, state: "same" as const }))
      : diffLines(extract(before), extract(after));
    return {
      title,
      lines,
      added: lines.filter((line) => line.state === "added").length,
      removed: lines.filter((line) => line.state === "removed").length,
    };
  });
}

function DiffRow({ line }: { line: DiffLine }) {
  return (
    <div className={`diff-line diff-line--${line.state}`}>
      <span className="diff-line__sign">{line.state === "added" ? "+" : line.state === "removed" ? "−" : " "}</span>
      <code>{line.text}</code>
    </div>
  );
}

/** Renders each change with its surrounding lines; untouched runs collapse to a marker. */
function ChangedFirst({ lines }: { lines: DiffLine[] }) {
  const [expanded, setExpanded] = useState(false);
  const hasChanges = lines.some((line) => line.state !== "same");

  if (!hasChanges) {
    return (
      <div className="diff-lines diff-lines--split">
        <p className="diff-file__empty">No changes in this section.</p>
        <button type="button" className="diff-context-toggle" onClick={() => setExpanded(!expanded)}>
          {expanded ? "Hide" : "Show"} {lines.length} unchanged line{lines.length === 1 ? "" : "s"}
        </button>
        {expanded && <div className="diff-context-lines">{lines.map((line, index) => <DiffRow key={`${line.key}-${index}`} line={line} />)}</div>}
      </div>
    );
  }

  if (expanded) {
    return (
      <div className="diff-lines diff-lines--split">
        {lines.map((line, index) => <DiffRow key={`${line.key}-${index}`} line={line} />)}
        <button type="button" className="diff-context-toggle" onClick={() => setExpanded(false)}>Collapse unchanged lines</button>
      </div>
    );
  }

  return (
    <div className="diff-lines diff-lines--split">
      {toHunks(lines).map((entry, index) =>
        "gap" in entry
          ? <button type="button" className="diff-gap" key={`gap-${index}`} onClick={() => setExpanded(true)}>⋯ {entry.gap} unchanged line{entry.gap === 1 ? "" : "s"}</button>
          : <DiffRow key={`${entry.key}-${index}`} line={entry} />,
      )}
    </div>
  );
}

export function ContextVersionDiff({ mode, from, to, onClose }: { mode: "snapshot" | "diff"; from: number | null; to: number; onClose: () => void }) {
  const [before, setBefore] = useState<ContextDocument | null>(null);
  const [after, setAfter] = useState<ContextDocument | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    // Snapshot mode reads one version; diff mode also needs its predecessor.
    // `from` is null for v1, which has none: everything there reads as added.
    const needsBefore = mode === "diff" && from != null;
    Promise.all([
      needsBefore ? fetchContextVersion(from as number, controller.signal) : Promise.resolve(null),
      fetchContextVersion(to, controller.signal),
    ])
      .then(([previous, next]) => { setBefore(previous); setAfter(next); })
      .catch((reason) => { if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : "Could not load the context version"); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [mode, from, to]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => { if (event.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  // Freeze the page behind the dialog so scrolling never reaches the run list.
  useEffect(() => {
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = previous; };
  }, []);

  const snapshot = mode === "snapshot";
  const sections = buildSections(mode, before, after);
  const totalAdded = sections.reduce((sum, section) => sum + section.added, 0);
  const totalRemoved = sections.reduce((sum, section) => sum + section.removed, 0);
  const totalLines = sections.reduce((sum, section) => sum + section.lines.length, 0);
  const title = snapshot ? `v${to}` : `${from == null ? "base" : `v${from}`} → v${to}`;

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className={`context-diff-modal ${snapshot ? "context-diff-modal--snapshot" : ""}`} onClick={(event) => event.stopPropagation()} role="dialog" aria-modal="true" aria-label={snapshot ? `Context version ${to}` : `Context diff ${from ?? "base"} to ${to}`}>
        <header className="context-diff-modal__head">
          <div>
            <span className="report-eyebrow">{snapshot ? "Context snapshot" : "Context window"}</span>
            <h3>{title}</h3>
          </div>
          <div className="context-diff-modal__actions">
            {!loading && !error && (
              snapshot
                ? <span className="diff-tally"><b>{totalLines} definition{totalLines === 1 ? "" : "s"}</b></span>
                : <span className="diff-tally"><b className="diff-tally--add">+{totalAdded}</b><b className="diff-tally--del">−{totalRemoved}</b></span>
            )}
            <button onClick={onClose} aria-label="Close"><X size={16} /></button>
          </div>
        </header>

        {loading && <div className="context-diff-modal__state">{snapshot ? "Loading the context version…" : "Loading both context versions…"}</div>}
        {error && <div className="context-diff-modal__state context-diff-modal__state--error">{error}</div>}

        {!loading && !error && (
          <div className="context-diff-modal__body">
            {sections.map((section) => (
              <section className="diff-file" key={section.title}>
                <header className="diff-file__head">
                  <strong>{section.title}</strong>
                  {snapshot
                    ? <span>{section.lines.length}</span>
                    : <span><b className="diff-tally--add">+{section.added}</b><b className="diff-tally--del">−{section.removed}</b></span>}
                </header>
                {section.lines.length === 0 ? (
                  <p className="diff-file__empty">{snapshot ? "Nothing defined in this version." : "Empty in both versions."}</p>
                ) : snapshot ? (
                  <div className="diff-lines">
                    {section.lines.map((line, index) => <DiffRow key={`${line.key}-${index}`} line={line} />)}
                  </div>
                ) : (
                  <ChangedFirst lines={section.lines} />
                )}
              </section>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
