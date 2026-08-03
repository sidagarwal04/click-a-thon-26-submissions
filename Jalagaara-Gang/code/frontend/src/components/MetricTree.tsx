import type { Anomaly, DrilldownNode } from "../types";

const pct = (n: number) => `${Math.round(n * 100)}%`;

function label(node: DrilldownNode): string {
  const entries = Object.entries(node.segment);
  const [dim, val] = entries[entries.length - 1] ?? [node.split_dimension, "?"];
  return `${dim} = ${val}`;
}

type Row = {
  key: string;
  title: string;
  badge: string;
  culprit: boolean;
  width: number; // 0..100
  share: string;
  detail: string;
};

// Hero component: the drill-down path from the broad metric to the localized culprit,
// rendered as a vertical timeline. `step` reveals rows one at a time during replay.
export function MetricTree({
  metric,
  anomaly,
  nodes,
  step,
}: {
  metric: string;
  anomaly: Anomaly;
  nodes: DrilldownNode[];
  step?: number;
}) {
  const rootShare = `${anomaly.pct_delta < 0 ? "−" : "+"}${Math.abs(anomaly.pct_delta * 100).toFixed(1)}%`;
  const rows: Row[] = [
    {
      key: "root",
      title: metric,
      badge: "root",
      culprit: false,
      width: 100,
      share: rootShare,
      detail: `${Math.round(anomaly.observed).toLocaleString("en-US")} vs ${Math.round(anomaly.expected).toLocaleString("en-US")} expected`,
    },
    ...nodes.map((n) => ({
      key: n.query_id,
      title: label(n),
      badge: n.status,
      culprit: n.status === "culprit",
      width: Math.round(Math.abs(n.contribution_pct) * 100),
      share: `${pct(Math.abs(n.contribution_pct))} of drop`,
      detail:
        n.metric_from != null && n.metric_to != null
          ? `fill ${pct(n.metric_from)} → ${pct(n.metric_to)}`
          : "",
    })),
  ];

  const active = step ?? rows.length; // default: everything revealed

  return (
    <div className="tree">
      {rows.map((r, i) => {
        const first = i === 0;
        const last = i === rows.length - 1;
        return (
          <div key={r.key} className={`tree-row ${r.culprit ? "is-culprit" : ""}`}>
            <div className="tree-rail">
              <span className={`tree-line ${first ? "blank" : ""}`} />
              <span className="tree-dot" />
              <span className={`tree-line ${last ? "blank" : ""}`} />
            </div>
            <div className="tree-cell">
              <div className={`tree-node ${i > active - 1 ? "dim" : ""}`}>
                <div className="node-top">
                  <span className="node-title">{r.title}</span>
                  <span className="node-badge">{r.badge}</span>
                </div>
                <div className="node-meter">
                  <span className="bar-track">
                    <span className="bar-fill" style={{ width: `${r.width}%` }} />
                  </span>
                  <span className="node-share">{r.share}</span>
                </div>
                {r.detail && <span className="node-detail">{r.detail}</span>}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
