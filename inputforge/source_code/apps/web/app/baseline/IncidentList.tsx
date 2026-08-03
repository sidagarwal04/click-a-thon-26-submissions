import { Spark } from "./charts";
import {
  formatDelta,
  formatMetric,
  formatUtc,
  incidentHeadline,
  metricLabel,
} from "./format";
import { GREY, PANEL, RULE, toneColor } from "./theme";
import type { Incident, Metric } from "./types";

interface IncidentListProps {
  incidents: Incident[];
  metrics: Metric[];
  onOpenDetail: (id: string) => void;
}

export function IncidentList({
  incidents,
  metrics,
  onOpenDetail,
}: IncidentListProps) {
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "minmax(0,1fr) 336px",
        gap: 26,
        alignItems: "start",
      }}
    >
      <div
        style={{
          border: `1px solid ${RULE}`,
          borderRadius: 10,
          background: PANEL,
          overflow: "hidden",
        }}
      >
        {incidents.map((incident) => {
          return (
            <div
              key={incident.id}
              className="bl-row"
              onClick={() => onOpenDetail(incident.id)}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 18,
                padding: "14px 18px",
                borderBottom: "1px solid #F1ECE1",
                cursor: "pointer",
              }}
            >
              <div style={{ minWidth: 0, flex: 1 }}>
                <div
                  style={{ fontSize: 14, marginBottom: 4, lineHeight: 1.35 }}
                >
                  {incidentHeadline(incident)}
                </div>
                <div style={{ fontSize: 12, color: GREY }}>
                  {formatUtc(incident.startTime)} –{" "}
                  {formatUtc(incident.endTime)} · {incident.methods.length}{" "}
                  method
                  {incident.methods.length === 1 ? "" : "s"}
                </div>
              </div>
              <div style={{ flex: "none", width: 120 }}>
                <Spark
                  series={incident.series}
                  metric={incident.metric}
                  width={120}
                  height={46}
                  color={toneColor(
                    incident.pctDelta != null && incident.pctDelta > 0
                      ? "warn"
                      : "bad",
                  )}
                />
              </div>
            </div>
          );
        })}

        {!incidents.length && (
          <div
            style={{
              padding: "24px 18px",
              fontSize: 13,
              color: "#6B675C",
              lineHeight: 1.5,
            }}
          >
            No incident currently passes the dashboard rule: at least eight
            strictly consecutive flagged hours.
          </div>
        )}
      </div>

      <aside
        style={{
          position: "sticky",
          top: 88,
          display: "flex",
          flexDirection: "column",
          gap: 14,
        }}
      >
        <div
          style={{
            border: `1px solid ${RULE}`,
            borderRadius: 10,
            background: PANEL,
            overflow: "hidden",
          }}
        >
          <div
            style={{
              padding: "13px 16px",
              borderBottom: "1px solid #EFEADF",
              fontFamily: "var(--font-ibm-plex-mono), monospace",
              fontSize: 10.5,
              letterSpacing: "0.1em",
              textTransform: "uppercase",
              color: GREY,
            }}
          >
            Watched metrics
          </div>
          {metrics.map((metric) => {
            const tone = toneColor(metric.tone);
            return (
              <div
                key={metric.key}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 14,
                  padding: "11px 16px",
                  borderBottom: "1px solid #F1ECE1",
                  cursor: metric.incidentId ? "pointer" : "default",
                }}
                onClick={() =>
                  metric.incidentId && onOpenDetail(metric.incidentId)
                }
              >
                <div style={{ minWidth: 0, flex: 1 }}>
                  <div style={{ fontSize: 13, marginBottom: 3 }}>
                    {metricLabel(metric.key)}
                  </div>
                  <div
                    style={{
                      fontFamily: "var(--font-ibm-plex-mono), monospace",
                      fontSize: 15,
                      letterSpacing: "-0.01em",
                    }}
                  >
                    {formatMetric(metric.key, metric.value)}
                  </div>
                </div>
                <div style={{ flex: "none", width: 78 }}>
                  <Spark
                    series={metric.series}
                    metric={metric.key}
                    width={78}
                    height={26}
                    color={tone}
                  />
                </div>
                <div
                  style={{
                    flex: "none",
                    width: 56,
                    textAlign: "right",
                    fontFamily: "var(--font-ibm-plex-mono), monospace",
                    fontSize: 12.5,
                    color: tone,
                  }}
                >
                  {formatDelta(metric.delta)}
                </div>
              </div>
            );
          })}
        </div>
      </aside>
    </div>
  );
}
