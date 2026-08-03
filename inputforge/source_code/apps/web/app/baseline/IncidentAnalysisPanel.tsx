import { ToolCallTrace } from "./ChatBubble";
import { GREY, INK, PANEL, RULE } from "./theme";
import type { IncidentAnalysis } from "./types";

const VERDICT_LABELS = {
  confirmed_anomaly: "Confirmed anomaly",
  likely_anomaly: "Likely anomaly",
  inconclusive: "Inconclusive",
  false_positive: "False positive",
} as const;

export function IncidentAnalysisPanel({
  analysis,
  error,
}: {
  analysis: IncidentAnalysis | null;
  error: string | null;
}) {
  const isRunning = analysis == null || analysis.status === "running";

  return (
    <section
      style={{
        marginTop: 34,
        padding: "22px 0 26px",
        borderTop: `1px solid ${RULE}`,
        borderBottom: `1px solid ${RULE}`,
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "baseline",
          justifyContent: "space-between",
          gap: 16,
          marginBottom: 16,
        }}
      >
        <div>
          <h2
            style={{
              fontFamily: "var(--font-newsreader), Georgia, serif",
              fontWeight: 400,
              fontSize: 23,
              letterSpacing: "-0.01em",
              margin: 0,
            }}
          >
            Agent analysis
          </h2>
        </div>
        {analysis?.verdict && (
          <span
            style={{
              border: `1px solid ${RULE}`,
              borderRadius: 999,
              padding: "4px 9px",
              fontFamily: "var(--font-ibm-plex-mono), monospace",
              fontSize: 10,
              color: INK,
              whiteSpace: "nowrap",
            }}
          >
            {Math.round(analysis.verdict.confidence * 100)}% confidence
          </span>
        )}
      </div>

      {isRunning && !error && (
        <div
          role="status"
          aria-live="polite"
          style={{
            padding: "18px 20px",
            border: `1px solid ${RULE}`,
            borderRadius: 8,
            background: PANEL,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 12, minHeight: 56 }}>
            <span
              aria-hidden="true"
              style={{
                width: 9,
                height: 9,
                borderRadius: "50%",
                background: "#B07A20",
                animation: "bl-pulse 1.25s ease-in-out infinite",
              }}
            />
            <div>
              <div style={{ fontSize: 14.5, color: INK }}>Analyzing incident…</div>
              <div style={{ marginTop: 4, fontSize: 12, color: GREY }}>
                Checking detector evidence and slicing the affected traffic.
              </div>
            </div>
          </div>

          {analysis && analysis.toolCalls.length > 0 && (
            <div style={{ marginTop: 18 }}>
              <div
                style={{
                  fontFamily: "var(--font-ibm-plex-mono), monospace",
                  fontSize: 9.5,
                  letterSpacing: "0.1em",
                  textTransform: "uppercase",
                  color: GREY,
                  marginBottom: 8,
                }}
              >
                Analysis chain
              </div>
              <ToolCallTrace tools={analysis.toolCalls} />
            </div>
          )}
        </div>
      )}

      {(error || analysis?.status === "failed") && (
        <div
          role="alert"
          style={{
            padding: "14px 16px",
            border: "1px solid #E4C4BE",
            borderRadius: 8,
            background: "#FFF5F2",
            color: "#8B3327",
            fontSize: 13,
            lineHeight: 1.55,
          }}
        >
          {analysis?.error ?? error ?? "The analysis could not be completed."}
        </div>
      )}

      {analysis?.status === "completed" && analysis.verdict && (
        <div style={{ display: "grid", gap: 22 }}>
          <div>
            <div
              style={{
                fontFamily: "var(--font-ibm-plex-mono), monospace",
                fontSize: 9.5,
                letterSpacing: "0.1em",
                textTransform: "uppercase",
                color: GREY,
                marginBottom: 7,
              }}
            >
              Verdict · {analysis.verdict.severity} severity
            </div>
            <div style={{ fontSize: 19, color: INK, marginBottom: 7 }}>
              {VERDICT_LABELS[analysis.verdict.label]}
            </div>
            <p style={{ margin: 0, fontSize: 14, lineHeight: 1.65, color: "#4A473F" }}>
              {analysis.verdict.summary}
            </p>
          </div>

          <div>
            <div
              style={{
                fontFamily: "var(--font-ibm-plex-mono), monospace",
                fontSize: 9.5,
                letterSpacing: "0.1em",
                textTransform: "uppercase",
                color: GREY,
                marginBottom: 3,
              }}
            >
              Slice and dice
            </div>
            {analysis.sliceAndDice.length ? (
              analysis.sliceAndDice.map((item, index) => (
                <div
                  key={`${item.slice}-${item.finding}`}
                  style={{
                    display: "grid",
                    gridTemplateColumns: "24px minmax(0,1fr)",
                    gap: 14,
                    padding: "17px 0",
                    borderTop: index === 0 ? "none" : "1px solid #EFEADF",
                  }}
                >
                  <span
                    aria-hidden="true"
                    style={{
                      fontFamily: "var(--font-ibm-plex-mono), monospace",
                      fontSize: 10,
                      color: "#A59A85",
                      paddingTop: 2,
                    }}
                  >
                    {String(index + 1).padStart(2, "0")}
                  </span>
                  <div>
                    <div
                      style={{
                        fontFamily: "var(--font-ibm-plex-mono), monospace",
                        fontSize: 14,
                        fontWeight: 600,
                        color: INK,
                        lineHeight: 1.4,
                        marginBottom: 5,
                      }}
                    >
                      {item.slice}
                    </div>
                    <div
                      style={{
                        fontSize: 13,
                        color: "#6B675C",
                        lineHeight: 1.5,
                        marginBottom: 6,
                      }}
                    >
                      {item.finding}
                    </div>
                    <p
                      style={{
                        margin: 0,
                        fontSize: 12.5,
                        lineHeight: 1.6,
                        color: GREY,
                      }}
                    >
                      {item.evidence}
                    </p>
                  </div>
                </div>
              ))
            ) : (
              <p style={{ margin: "10px 0 0", fontSize: 13, color: GREY }}>
                No segment explained a meaningful share of the movement.
              </p>
            )}
          </div>

          {analysis.toolCalls.length > 0 && (
            <div>
              <div
                style={{
                  fontFamily: "var(--font-ibm-plex-mono), monospace",
                  fontSize: 9.5,
                  letterSpacing: "0.1em",
                  textTransform: "uppercase",
                  color: GREY,
                  marginBottom: 8,
                }}
              >
                Tool calls
              </div>
              <ToolCallTrace tools={analysis.toolCalls} />
            </div>
          )}
        </div>
      )}
    </section>
  );
}
