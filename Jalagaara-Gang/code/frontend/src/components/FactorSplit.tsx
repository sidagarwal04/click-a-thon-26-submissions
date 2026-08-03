import type { Factor } from "../types";

// Which factor moved (requests / fill / eCPM) and by how much.
export function FactorSplit({
  factors,
  primary,
  totalPct,
}: {
  factors: Factor[];
  primary: string;
  totalPct?: string;
}) {
  return (
    <section className="card">
      <div className="eyebrow-row">
        <span className="eyebrow">Factor split</span>
        {totalPct && <span className="hint">contribution to {totalPct}</span>}
      </div>
      <div className="factors">
        {factors.map((f) => {
          const isPrimary = f.factor === primary;
          const pct = Math.round(Math.abs(f.contribution_pct) * 100);
          return (
            <div key={f.factor} className={`factor-row ${isPrimary ? "is-primary" : ""}`}>
              <span className="factor-name">
                {f.factor}{isPrimary ? " ★" : ""}
              </span>
              <span className="bar-track">
                <span className="bar-fill" style={{ width: `${pct}%` }} />
              </span>
              <span className="factor-val">{pct}%</span>
            </div>
          );
        })}
      </div>
    </section>
  );
}
