import { useEffect, useRef, useState } from "react";
import { useEveAgent } from "eve/react";
import { ChatBubble } from "./ChatBubble";
import { BigChart } from "./charts";
import { buildClientContext } from "./clientContext";
import { IncidentAnalysisPanel } from "./IncidentAnalysisPanel";
import { SegmentEvidenceHeatmap } from "./SegmentEvidenceHeatmap";
import {
  durationLabel,
  formatMetricMaybe,
  formatUtc,
  incidentHeadline,
  incidentOverview,
  metricLabel,
  reportabilitySummary,
} from "./format";
import { DETAIL_SUGGESTIONS } from "./suggestions";
import { GREY, INK, RULE } from "./theme";
import type {
  ChatMessage,
  ChatToolCall,
  Incident,
  IncidentAnalysis,
} from "./types";

interface DetailViewProps {
  incident: Incident;
  accent: string;
  onBack: () => void;
}

export function DetailView({ incident, accent, onBack }: DetailViewProps) {
  const agent = useEveAgent();
  const [input, setInput] = useState("");
  const [analysis, setAnalysis] = useState<IncidentAnalysis | null>(null);
  const [analysisError, setAnalysisError] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const isBusy = agent.status === "submitted" || agent.status === "streaming";
  const mapped: ChatMessage[] = agent.data.messages
    .map((message) => {
      const tools: ChatToolCall[] = message.parts
        .filter((part) => part.type === "dynamic-tool")
        .map((part) => ({
          name: part.toolName,
          input: part.input,
          output: part.output,
          error: part.errorText,
          state: part.state,
        }));
      return {
        who: (message.role === "user" ? "user" : "bot") as ChatMessage["who"],
        text: message.parts
          .filter((part) => part.type === "text")
          .map((part) => part.text)
          .join(""),
        tools,
      };
    })
    .filter(
      (message) =>
        message.who === "user" ||
        message.text.length > 0 ||
        message.tools.length > 0,
    );
  if (agent.status === "error")
    mapped.push({
      who: "bot",
      text: `Couldn't reach the agent: ${agent.error?.message ?? "unknown error"}`,
    });
  const hasPendingTool = mapped.some((message) =>
    message.tools?.some(
      (tool) => tool.state !== "output-available" && !tool.error,
    ),
  );
  const chatMessages: ChatMessage[] = mapped.length
    ? mapped
    : [
        {
          who: "bot",
          text: "Ask me anything about this incident — I'll check the live data.",
        },
      ];

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({
      block: "nearest",
      behavior: "smooth",
    });
  }, [chatMessages.length, isBusy]);

  useEffect(() => {
    let cancelled = false;
    let pollTimer: ReturnType<typeof setTimeout> | undefined;

    const POLL_INTERVAL_MS = 1_500;

    async function pollAnalysis() {
      try {
        const response = await fetch(
          `/api/incident-analysis?incidentId=${encodeURIComponent(incident.id)}`,
        );
        const payload = (await response.json()) as {
          analysis?: IncidentAnalysis | null;
          error?: string;
        };
        if (cancelled) return;
        if (!response.ok || !payload.analysis) {
          throw new Error(payload.error ?? "Could not load incident analysis.");
        }
        setAnalysisError(null);
        setAnalysis(payload.analysis);
        if (payload.analysis.status === "running") {
          pollTimer = setTimeout(() => void pollAnalysis(), POLL_INTERVAL_MS);
        } else if (payload.analysis.status === "failed") {
          setAnalysisError(
            payload.analysis.error ?? "Could not analyze this incident.",
          );
        }
      } catch (error) {
        if (!cancelled) {
          setAnalysisError(
            error instanceof Error
              ? error.message
              : "Could not analyze this incident.",
          );
        }
      }
    }

    async function startAnalysis() {
      try {
        const response = await fetch("/api/incident-analysis", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ incidentId: incident.id }),
        });
        const payload = (await response.json()) as {
          analysis?: IncidentAnalysis | null;
          error?: string;
        };
        if (!response.ok || !payload.analysis) {
          throw new Error(
            payload.error ?? "Could not start incident analysis.",
          );
        }
        if (cancelled) return;
        setAnalysis(payload.analysis);
        if (payload.analysis.status !== "running") {
          if (payload.analysis.status === "failed") {
            setAnalysisError(
              payload.analysis.error ?? "Could not analyze this incident.",
            );
          }
          return;
        }

        pollTimer = setTimeout(() => void pollAnalysis(), POLL_INTERVAL_MS);
      } catch (error) {
        if (!cancelled) {
          setAnalysisError(
            error instanceof Error
              ? error.message
              : "Could not analyze this incident.",
          );
        }
      }
    }

    void startAnalysis();

    return () => {
      cancelled = true;
      if (pollTimer) clearTimeout(pollTimer);
    };
  }, [incident.id]);

  function ask(question: string) {
    if (isBusy || !question.trim()) return;
    void agent.send({
      message: question,
      clientContext: JSON.stringify(buildClientContext(incident, analysis)),
    });
  }

  function onSend() {
    ask(input.trim());
    setInput("");
  }

  const summary = [
    {
      key: "Peak movement",
      value: `${formatMetricMaybe(incident.metric, incident.expected)} → ${formatMetricMaybe(incident.metric, incident.observed)}`,
      sub: "strongest detector row with raw values",
    },
    {
      key: "Window",
      value: `${formatUtc(incident.startTime)} – ${formatUtc(incident.endTime)}`,
      sub: durationLabel(incident),
    },
  ];

  return (
    <main
      style={{ padding: "26px 28px 96px", maxWidth: 780, margin: "0 auto" }}
    >
      <button
        className="bl-back"
        onClick={onBack}
        style={{
          marginBottom: 26,
          padding: "4px 0",
          border: "none",
          background: "transparent",
          fontSize: 12.5,
          fontFamily: "inherit",
          cursor: "pointer",
          color: GREY,
        }}
      >
        ← All incidents
      </button>

      <div
        style={{
          marginBottom: 12,
        }}
      >
        <span
          style={{
            fontFamily: "var(--font-ibm-plex-mono), monospace",
            fontSize: 11,
            color: GREY,
            letterSpacing: "0.04em",
          }}
        >
          {formatUtc(incident.detectedAt)}
        </span>
      </div>
      <h1
        style={{
          fontFamily: "var(--font-newsreader), Georgia, serif",
          fontWeight: 400,
          fontSize: 38,
          lineHeight: 1.16,
          letterSpacing: "-0.018em",
          margin: "0 0 14px",
        }}
      >
        {incidentHeadline(incident)}
      </h1>
      <p
        style={{
          margin: "0 0 24px",
          fontSize: 16,
          lineHeight: 1.65,
          color: "#4A473F",
        }}
      >
        {incidentOverview(incident)}
      </p>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(2, minmax(0,1fr))",
          gap: 32,
          paddingBottom: 24,
          borderBottom: `1px solid ${RULE}`,
          marginBottom: 30,
        }}
      >
        {summary.map((item) => (
          <div key={item.key}>
            <div
              style={{
                fontFamily: "var(--font-ibm-plex-mono), monospace",
                fontSize: 9.5,
                letterSpacing: "0.12em",
                textTransform: "uppercase",
                color: "#9A9488",
                marginBottom: 6,
              }}
            >
              {item.key}
            </div>
            <div style={{ fontSize: 15, lineHeight: 1.45, color: INK }}>
              {item.value}
            </div>
            <div
              style={{
                fontSize: 12,
                lineHeight: 1.5,
                color: GREY,
                marginTop: 4,
              }}
            >
              {item.sub}
            </div>
          </div>
        ))}
      </div>

      <div style={{ height: 30 }} />
      <div
        style={{
          display: "flex",
          alignItems: "baseline",
          justifyContent: "space-between",
          marginBottom: 6,
          flexWrap: "wrap",
          gap: 12,
        }}
      >
        <h2
          style={{
            fontFamily: "var(--font-newsreader), Georgia, serif",
            fontWeight: 400,
            fontSize: 21,
            letterSpacing: "-0.01em",
            margin: 0,
          }}
        >
          Hourly series
        </h2>
        <div style={{ display: "flex", gap: 16, fontSize: 11.5, color: GREY }}>
          <span>— actual</span>
          <span style={{ color: accent }}>┄ expected</span>
          <span style={{ color: "#B4442B" }}>▯ flagged window</span>
        </div>
      </div>
      <div
        style={{
          fontFamily: "var(--font-ibm-plex-mono), monospace",
          fontSize: 11,
          color: GREY,
          marginBottom: 4,
        }}
      >
        {metricLabel(incident.metric)} · incident window ±24h · trailing 4-week
        same-day/hour comparison
      </div>
      <BigChart
        series={incident.series}
        metric={incident.metric}
        accent={accent}
        width={760}
      />

      <div style={{ height: 38 }} />
      <div
        style={{
          display: "flex",
          alignItems: "baseline",
          justifyContent: "space-between",
          marginBottom: 14,
        }}
      >
        <h2
          style={{
            fontFamily: "var(--font-newsreader), Georgia, serif",
            fontWeight: 400,
            fontSize: 21,
            letterSpacing: "-0.01em",
            margin: 0,
          }}
        >
          Why it is reportable
        </h2>
        <span
          style={{
            fontFamily: "var(--font-ibm-plex-mono), monospace",
            fontSize: 11,
            color: "#4A473F",
          }}
        >
          max seasonal |z| {incident.maxAbsZ.toFixed(2)}
        </span>
      </div>
      <p
        style={{ margin: 0, fontSize: 15, lineHeight: 1.65, color: "#4A473F" }}
      >
        {reportabilitySummary(incident)}
      </p>

      {(incident.segmentSignals.length > 0 ||
        incident.relatedMetrics.length > 0) && (
        <div
          style={{
            marginTop: 28,
            borderTop: `1px solid ${RULE}`,
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "flex-start",
              padding: "20px 0 10px",
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
                Investigation leads
              </h2>
              <div
                style={{
                  marginTop: 6,
                  fontFamily: "var(--font-ibm-plex-mono), monospace",
                  fontSize: 10.5,
                  lineHeight: 1.5,
                  color: GREY,
                }}
              >
                {formatUtc(incident.startTime)} – {formatUtc(incident.endTime)}
              </div>
            </div>
          </div>

          <div
            style={{
              display: "flex",
              flexDirection: "column",
            }}
          >
            {incident.segmentSignals.length > 0 && (
              <div style={{ padding: "10px 0 22px" }}>
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    gap: 12,
                    marginBottom: 14,
                    fontFamily: "var(--font-ibm-plex-mono), monospace",
                    fontSize: 10,
                    letterSpacing: "0.08em",
                    textTransform: "uppercase",
                    color: GREY,
                  }}
                >
                  <span>Matching segment flags</span>
                  <span>Seasonal |z|</span>
                </div>
                <div
                  style={{ display: "flex", flexDirection: "column", gap: 12 }}
                >
                  {incident.segmentSignals.map((signal, index) => (
                    <div key={`${signal.dimension}-${signal.segment}`}>
                      <div
                        style={{
                          display: "grid",
                          gridTemplateColumns: "22px minmax(0,1fr) auto",
                          alignItems: "baseline",
                          gap: 8,
                          marginBottom: 5,
                        }}
                      >
                        <span
                          style={{
                            fontFamily: "var(--font-ibm-plex-mono), monospace",
                            fontSize: 10,
                            color: "#A59A85",
                          }}
                        >
                          {String(index + 1).padStart(2, "0")}
                        </span>
                        <span style={{ fontSize: 13.5, color: INK }}>
                          {signal.segment} <span aria-hidden="true">·</span>{" "}
                          <span style={{ color: GREY }}>
                            {signal.dimension.replaceAll("_", " ")}
                          </span>
                        </span>
                        <span
                          style={{
                            fontFamily: "var(--font-ibm-plex-mono), monospace",
                            fontSize: 11.5,
                            color: GREY,
                          }}
                        >
                          {signal.maxAbsZ.toFixed(2)}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {incident.relatedMetrics.length > 0 && (
              <div style={{ padding: "0 0 20px" }}>
                <div
                  style={{
                    fontFamily: "var(--font-ibm-plex-mono), monospace",
                    fontSize: 10,
                    letterSpacing: "0.08em",
                    textTransform: "uppercase",
                    color: GREY,
                    marginBottom: 12,
                  }}
                >
                  Overlapping incidents
                </div>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 7 }}>
                  {incident.relatedMetrics.map((metric) => (
                    <span
                      key={metric}
                      style={{
                        border: `1px solid ${RULE}`,
                        borderRadius: 999,
                        background: "transparent",
                        padding: "6px 10px",
                        fontSize: 12.5,
                        color: INK,
                      }}
                    >
                      {metricLabel(metric)}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      <SegmentEvidenceHeatmap incident={incident} />

      <IncidentAnalysisPanel analysis={analysis} error={analysisError} />

      <div style={{ height: 38 }} />
      <h2
        id="chat"
        style={{
          fontFamily: "var(--font-newsreader), Georgia, serif",
          fontWeight: 400,
          fontSize: 21,
          letterSpacing: "-0.01em",
          margin: "0 0 14px",
        }}
      >
        Investigate this incident
      </h2>
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: 14,
          marginBottom: 18,
        }}
      >
        {chatMessages.map((message, index) => (
          <ChatBubble key={index} message={message} />
        ))}
        {isBusy && !hasPendingTool && (
          <ChatBubble message={{ who: "bot", text: "Thinking…" }} />
        )}
        <div ref={messagesEndRef} />
      </div>
      <div
        style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 16 }}
      >
        {DETAIL_SUGGESTIONS.map((question) => (
          <button
            key={question}
            className="bl-pill-suggest"
            onClick={() => setInput(question)}
            disabled={isBusy}
            style={{
              padding: "8px 14px",
              borderRadius: 999,
              border: `1px solid ${RULE}`,
              background: "#FFFDF9",
              color: "#4A473F",
              fontSize: 12.5,
              fontFamily: "inherit",
              cursor: isBusy ? "default" : "pointer",
              opacity: isBusy ? 0.5 : 1,
              textAlign: "left",
              lineHeight: 1.4,
            }}
          >
            {question}
          </button>
        ))}
      </div>
      <div
        style={{
          position: "sticky",
          bottom: 20,
          display: "flex",
          alignItems: "center",
          gap: 10,
          border: "1px solid #CFC8B8",
          borderRadius: 999,
          background: "#FFFDF9",
          padding: "7px 8px 7px 18px",
          boxShadow: "0 6px 22px rgba(23,22,18,0.06)",
        }}
      >
        <input
          value={input}
          onChange={(event) => setInput(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && input.trim() && !isBusy) onSend();
          }}
          disabled={isBusy}
          placeholder="Ask anything about this incident…"
          style={{
            flex: 1,
            border: "none",
            outline: "none",
            background: "transparent",
            fontFamily: "inherit",
            fontSize: 14.5,
            color: INK,
          }}
        />
        <button
          className="bl-send"
          onClick={onSend}
          disabled={isBusy || !input.trim()}
          style={{
            padding: "9px 18px",
            borderRadius: 999,
            border: "none",
            background: INK,
            color: "#FAF8F4",
            fontSize: 13,
            fontFamily: "inherit",
            cursor: isBusy || !input.trim() ? "default" : "pointer",
            opacity: isBusy ? 0.6 : 1,
          }}
        >
          Ask
        </button>
      </div>
    </main>
  );
}
