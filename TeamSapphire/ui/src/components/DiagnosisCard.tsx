import type { Narration, Signature } from "@/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

// engine/narrate.py's system prompt fixes the narration at exactly these
// three paragraphs, in this order — these are that structure's own labels,
// not an invented one, so splitting on blank lines and labeling by position
// is safe (it's re-presenting the model's real text, never rewording it).
const POINT_LABELS = ["What moved", "Factor & segment", "Checked & next steps"];

export function DiagnosisCard({
  narration,
  signature,
}: {
  narration: Narration | undefined;
  signature: Signature | null;
}) {
  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between space-y-0">
        <CardTitle className="text-base">Diagnosis</CardTitle>
        {narration && (
          <span
            className="rounded-full border px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide"
            style={
              narration.all_numbers_verified
                ? { color: "#0ca30c", borderColor: "#0ca30c66", backgroundColor: "#0ca30c1f" }
                : { color: "#d03b3b", borderColor: "#d03b3b66", backgroundColor: "#d03b3b1f" }
            }
          >
            {narration.all_numbers_verified ? "all numbers verified" : "unverified numbers"}
          </span>
        )}
      </CardHeader>
      <CardContent>
        {narration ? (
          <div className="max-w-[70ch] space-y-4 text-sm leading-relaxed text-foreground/90">
            <ul className="space-y-3">
              {narration.text.split("\n\n").map((point, i) => (
                <li key={i} className="flex gap-2.5">
                  <span
                    className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full"
                    style={{ backgroundColor: "#3987e5" }}
                  />
                  <div>
                    {POINT_LABELS[i] && (
                      <div className="mb-0.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                        {POINT_LABELS[i]}
                      </div>
                    )}
                    <p>{point}</p>
                  </div>
                </li>
              ))}
            </ul>
            {narration.unverified_numbers.length > 0 && (
              <p className="text-xs" style={{ color: "#d03b3b" }}>
                unverified: {narration.unverified_numbers.join(", ")}
              </p>
            )}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">No narration for this event.</p>
        )}

        {signature && (
          <div className="mt-4 max-w-[70ch] border-t border-border pt-4">
            <div className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Shape of the change
            </div>
            <p className="text-sm leading-relaxed text-foreground/90">{signature.reading}</p>
            {signature.held_steady.length > 0 && (
              <p className="mt-1.5 text-xs text-muted-foreground">
                Held steady: {signature.held_steady.join(", ")}
              </p>
            )}
            {signature.rules_out.length > 0 && (
              <ul className="mt-2 space-y-1">
                {signature.rules_out.map((r, i) => (
                  <li key={i} className="flex gap-2 text-xs text-muted-foreground">
                    <span className="mt-1 h-1 w-1 shrink-0 rounded-full bg-muted-foreground" />
                    <span>Rules out {r}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
