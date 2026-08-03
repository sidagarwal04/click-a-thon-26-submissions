import { ArrowRight } from "lucide-react";
import { useState } from "react";
import { titleCase } from "../format";
import type { JsonValue } from "../types";
import { ContextVersionDiff } from "./ContextVersionDiff";

type JsonObject = Record<string, JsonValue>;

const object = (value: JsonValue | undefined): JsonObject =>
  value && typeof value === "object" && !Array.isArray(value) ? (value as JsonObject) : {};
const array = (value: JsonValue | undefined): JsonValue[] => (Array.isArray(value) ? value : []);

function joinList(items: string[]): string {
  if (items.length <= 1) return items[0] ?? "";
  if (items.length === 2) return `${items[0]} and ${items[1]}`;
  return `${items.slice(0, -1).join(", ")}, and ${items[items.length - 1]}`;
}

function entityName(item: JsonValue): string {
  const entity = object(item);
  return String(entity.name ?? entity.table_name ?? "an entity");
}

function relationshipPhrase(item: JsonValue): string {
  const link = object(item);
  return `${String(link.source_table ?? "?")}.${String(link.source_column ?? "?")} to ${String(link.target_table ?? "?")}.${String(link.target_column ?? "?")}`;
}

function metricName(item: JsonValue): string {
  return titleCase(String(object(item).name ?? "a metric"));
}

export function ContextTransition({ artifact, unavailable }: { artifact: JsonObject; unavailable?: string | null }) {
  const [diff, setDiff] = useState<{ mode: "snapshot" | "diff"; from: number | null; to: number } | null>(null);
  const version = Number(artifact.context_version ?? 0);
  const reason = unavailable ?? (version ? null : "The context agent has not written a version for this run yet.");
  if (reason) {
    return (
      <section className="context-transition context-transition--empty">
        <div>
          <span className="report-eyebrow">Context window</span>
          <h3>No context transition recorded</h3>
          <p>{reason}</p>
        </div>
      </section>
    );
  }

  const entities = array(artifact.entities_added).map(entityName);
  const relationships = array(artifact.relationships_added).map(relationshipPhrase);
  const metrics = array(artifact.metrics_added).map(metricName);
  const conventions = array(artifact.conventions_added).map(String);
  const conflicts = array(artifact.conflicts).map(String);
  const total = entities.length + relationships.length + metrics.length + conventions.length;
  // Version 1 is the seeded base layer, so there is no earlier snapshot to diff against.
  const previous = version > 1 ? `v${version - 1}` : "the base layer";

  const sentences: string[] = [];
  sentences.push(
    total > 0
      ? `Moving from ${previous} to v${version}, the context agent contributed ${total} new addition${total === 1 ? "" : "s"} to the semantic layer.`
      : `Moving from ${previous} to v${version}, the context agent found nothing new to add — the semantic layer is unchanged from the previous run.`,
  );
  if (entities.length) sentences.push(`It registered ${entities.length} new entit${entities.length === 1 ? "y" : "ies"}: ${joinList(entities)}.`);
  if (relationships.length) sentences.push(`It linked ${relationships.length} new relationship${relationships.length === 1 ? "" : "s"}, joining ${joinList(relationships)}.`);
  if (metrics.length) sentences.push(`It defined ${metrics.length} new metric${metrics.length === 1 ? "" : "s"}: ${joinList(metrics)}.`);
  if (conventions.length) sentences.push(`It captured ${conventions.length} naming convention${conventions.length === 1 ? "" : "s"}: ${joinList(conventions)}.`);
  sentences.push(
    conflicts.length
      ? `${conflicts.length} conflict${conflicts.length > 1 ? "s remain" : " remains"} unresolved: ${joinList(conflicts)}.`
      : "No conflicts were carried forward — the two versions agree everywhere they overlap.",
  );

  return (
    <section className="context-transition">
      <header className="context-transition__head">
        <div>
          <span className="report-eyebrow">Context window</span>
          <h3>How this run changed the semantic layer</h3>
        </div>
        <div className="context-transition__versions">
          <button
            type="button"
            className="version-chip version-chip--prev"
            onClick={() => setDiff({ mode: "snapshot", from: null, to: version - 1 })}
            disabled={version < 2}
            title={version < 2 ? "The base layer has no earlier version to inspect" : `Show the full context stored at v${version - 1}`}
          >
            {previous === "the base layer" ? "base" : previous}
          </button>
          <ArrowRight size={14} />
          <button
            type="button"
            className="version-chip version-chip--next"
            onClick={() => setDiff({ mode: "diff", from: version > 1 ? version - 1 : null, to: version })}
            title={`Show what changed in v${version}`}
          >
            v{version}
          </button>
        </div>
      </header>
      <p className="context-transition__narrative">
        {sentences.map((sentence, index) => <span key={index}>{sentence}</span>)}
      </p>
      {diff && <ContextVersionDiff mode={diff.mode} from={diff.from} to={diff.to} onClose={() => setDiff(null)} />}
    </section>
  );
}
