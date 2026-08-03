import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { INK, PANEL, RULE } from "./theme";
import type { ChatMessage, ChatToolCall } from "./types";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function formatResult(value: unknown): string {
  const text = JSON.stringify(value, null, 2) ?? "null";
  return text.length > 6_000 ? `${text.slice(0, 6_000)}\n…result truncated` : text;
}

function numberAt(value: unknown, key: string): number | undefined {
  return isRecord(value) && typeof value[key] === "number" ? value[key] : undefined;
}

function toolSummary(tool: ChatToolCall): string {
  if (tool.error) return "ClickHouse returned an error";
  if (tool.state !== "output-available") return "Query in progress";

  if (tool.name === "query_clickhouse_evidence") {
    const rowCount = numberAt(tool.output, "rowCount");
    return rowCount === undefined ? "Query completed" : `${rowCount} ${rowCount === 1 ? "row" : "rows"} returned`;
  }

  const evidence = isRecord(tool.output) ? tool.output : {};
  const detectorRows = Array.isArray(evidence.detectorRows) ? evidence.detectorRows.length : 0;
  const segmentSignals = Array.isArray(evidence.segmentSignals) ? evidence.segmentSignals.length : 0;
  const hourly = Array.isArray(evidence.hourly) ? evidence.hourly.length : 0;
  return `${detectorRows} anomaly rows · ${segmentSignals} segments · ${hourly} hourly values`;
}

function ClickHouseToolCall({ tool, divider = true }: { tool: ChatToolCall; divider?: boolean }) {
  const directSql = tool.name === "query_clickhouse_evidence";
  const evidenceLookup = tool.name === "retrieve_anomaly_evidence";
  if (!directSql && !evidenceLookup) return null;

  const sql = directSql && isRecord(tool.input) && typeof tool.input.sql === "string" ? tool.input.sql : undefined;
  const status = tool.error ? "failed" : tool.state === "output-available" ? "complete" : "running";
  const label = status === "running" ? "Thinking…" : tool.name;
  const result = tool.error ?? (tool.output === undefined ? "Waiting for ClickHouse…" : formatResult(tool.output));
  const statusColor = status === "failed" ? "#A7473C" : status === "complete" ? "#817A6E" : "#9A6B16";

  return (
    <details
      style={
        divider
          ? { marginTop: 9, paddingTop: 8, borderTop: "1px solid #EFEADF" }
          : undefined
      }
    >
      <summary
        style={{
          cursor: "pointer",
          display: "flex",
          alignItems: "center",
          gap: 8,
          padding: 0,
          fontFamily: "var(--font-ibm-plex-mono), monospace",
          fontSize: 10.5,
          color: "#817A6E",
        }}
      >
        <span aria-hidden="true" style={{ width: 5, height: 5, borderRadius: "50%", background: statusColor, flex: "0 0 auto" }} />
        <span>{label}</span>
        <span style={{ color: "#9B958A", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>· {toolSummary(tool)}</span>
      </summary>
      <div style={{ marginTop: 9, paddingTop: 9, borderTop: "1px solid #EFEADF", display: "grid", gap: 10 }}>
        {sql && (
          <div>
            <div style={{ fontFamily: "var(--font-ibm-plex-mono), monospace", fontSize: 10, color: "#8A857A", marginBottom: 4 }}>SQL QUERY</div>
            <pre style={{ margin: 0, overflowX: "auto", whiteSpace: "pre-wrap", background: "#F6F2EA", borderRadius: 5, padding: 9, fontSize: 11, lineHeight: 1.5 }}>{sql}</pre>
          </div>
        )}
        <div>
          <div style={{ fontFamily: "var(--font-ibm-plex-mono), monospace", fontSize: 10, color: tool.error ? "#B33A2B" : "#8A857A", marginBottom: 4 }}>{tool.error ? "ERROR" : "RESULT"}</div>
          <pre style={{ margin: 0, maxHeight: 300, overflow: "auto", whiteSpace: "pre-wrap", background: tool.error ? "#FFF2F0" : "#F6F2EA", borderRadius: 5, padding: 9, fontSize: 11, lineHeight: 1.5 }}>{result}</pre>
        </div>
      </div>
    </details>
  );
}

export function ToolCallTrace({ tools }: { tools: ChatToolCall[] }) {
  return (
    <div>
      {tools.map((tool, index) => (
        <ClickHouseToolCall
          key={`${tool.name}-${index}`}
          tool={tool}
          divider={index > 0}
        />
      ))}
    </div>
  );
}

export function ChatBubble({ message }: { message: ChatMessage }) {
  const user = message.who === "user";
  return (
    <div style={{ display: "flex", justifyContent: user ? "flex-end" : "flex-start" }}>
      <div
        style={
          user
            ? {
                maxWidth: "78%",
                padding: "10px 15px",
                borderRadius: "14px 14px 4px 14px",
                background: INK,
                color: "#FAF8F4",
                fontSize: 13.5,
                lineHeight: 1.55,
              }
            : {
                maxWidth: "88%",
                padding: "12px 16px",
                borderRadius: "14px 14px 14px 4px",
                background: PANEL,
                border: `1px solid ${RULE}`,
                color: INK,
                fontSize: 13.5,
                lineHeight: 1.6,
              }
        }
      >
        {user ? (
          <div style={{ whiteSpace: "pre-wrap" }}>{message.text}</div>
        ) : message.text ? (
          <Markdown
            remarkPlugins={[remarkGfm]}
            components={{
              p: ({ children }) => <p style={{ margin: "0 0 10px" }}>{children}</p>,
              ul: ({ children }) => <ul style={{ margin: "0 0 10px", paddingLeft: 20 }}>{children}</ul>,
              ol: ({ children }) => <ol style={{ margin: "0 0 10px", paddingLeft: 20 }}>{children}</ol>,
              li: ({ children }) => <li style={{ marginBottom: 4 }}>{children}</li>,
              strong: ({ children }) => <strong style={{ fontWeight: 650 }}>{children}</strong>,
              code: ({ children }) => (
                <code style={{ fontFamily: "var(--font-ibm-plex-mono), monospace", fontSize: "0.9em", background: "#F1ECE1", borderRadius: 3, padding: "1px 4px" }}>
                  {children}
                </code>
              ),
            }}
          >
            {message.text}
          </Markdown>
        ) : null}
        {message.tools?.map((tool, index) => <ClickHouseToolCall key={`${tool.name}-${index}`} tool={tool} />)}
      </div>
    </div>
  );
}
