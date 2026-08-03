// Plain-language diagnosis. Renders the model narrative if present, otherwise a
// styled fallback built from the anomaly numbers.
export function DiagnosisCard({ narrative }: { narrative?: string | null }) {
  return (
    <section className="card">
      <span className="eyebrow">Diagnosis</span>
      <p className="narrative">
        {narrative ?? "Awaiting narration…"}
      </p>
    </section>
  );
}
