import type { RuledOut } from "../types";

// The trust-builder: hypotheses that were checked and cleared, each with evidence.
export function RuledOutPanel({ items }: { items: RuledOut[] }) {
  return (
    <section className="card">
      <div className="eyebrow-row">
        <span className="eyebrow">Checked &amp; ruled out</span>
        <span className="hint">{items.length} hypotheses cleared</span>
      </div>
      <div className="ruled-grid">
        {items.map((r) => (
          <div key={r.query_id} className="ruled-item">
            <span className="ruled-check">✓</span>
            <div className="ruled-body">
              <span className="ruled-name">{r.hypothesis}</span>
              <span className="ruled-detail">{r.evidence}</span>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
