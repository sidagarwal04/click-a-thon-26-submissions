import { useState } from "react";
import { GREY, INK, RULE } from "./theme";
import type { Incident, SegmentEvidence } from "./types";

type EvidenceAssessment = "supports" | "no_support" | "contradicts" | "mixed";

function finite(value: number | null): number | null {
  return value != null && Number.isFinite(value) ? value : null;
}

function correlationFor(row: SegmentEvidence): number | null {
  return row.incidentCorrelationN >= 3
    ? finite(row.incidentCorrelation)
    : finite(row.baselineCorrelation);
}

function assessment(row: SegmentEvidence): EvidenceAssessment {
  const quietShare = row.scoredHours ? row.quietHours / row.scoredHours : 0;
  const correlation = correlationFor(row);
  const directionAligned = Math.sign(row.peakZ) === Math.sign(row.globalPeakZ);

  if (
    directionAligned &&
    Math.abs(row.peakZ) >= 2 &&
    row.directionMatchPct >= 0.5 &&
    (correlation == null || correlation >= 0.2)
  ) {
    return "supports";
  }
  if (
    !directionAligned &&
    Math.abs(row.peakZ) >= 1.5 &&
    row.directionMatchPct <= 0.33
  ) {
    return "contradicts";
  }
  if (
    quietShare >= 0.75 ||
    (Math.abs(row.meanZ) < 1 &&
      row.directionMatchPct < 0.5 &&
      (correlation == null || correlation < 0.2))
  ) {
    return "no_support";
  }
  return "mixed";
}

function zCell(value: number) {
  const strength = Math.min(Math.abs(value) / 4, 1);
  const channel = value < 0 ? "180, 68, 43" : "49, 92, 121";
  return {
    background: `rgba(${channel}, ${0.04 + strength * 0.18})`,
    color: value < 0 ? "#76402E" : "#315C79",
  };
}

function correlationCell(value: number | null) {
  if (value == null) return { color: GREY, background: "transparent" };
  const strength = Math.min(Math.abs(value), 1);
  const channel = value >= 0 ? "79, 98, 82" : "49, 92, 121";
  return {
    background: `rgba(${channel}, ${0.03 + strength * 0.17})`,
    color: value >= 0 ? "#4F6252" : "#315C79",
  };
}

function signed(value: number | null, digits = 2): string {
  if (value == null || !Number.isFinite(value)) return "—";
  return `${value > 0 ? "+" : ""}${value.toFixed(digits)}`;
}

export function SegmentEvidenceHeatmap({
  incident,
}: {
  incident: Pick<Incident, "segmentEvidence">;
}) {
  const groups = new Map<string, SegmentEvidence[]>();
  for (const row of incident.segmentEvidence) {
    groups.set(row.dimension, [...(groups.get(row.dimension) ?? []), row]);
  }
  const dimensions = [...groups.keys()];
  const [selectedDimension, setSelectedDimension] = useState(
    dimensions[0] ?? "",
  );
  if (!incident.segmentEvidence.length) return null;

  const activeDimension = groups.has(selectedDimension)
    ? selectedDimension
    : dimensions[0]!;
  const rows = groups.get(activeDimension) ?? [];
  const counts = rows.reduce(
    (result, row) => {
      result[assessment(row)] += 1;
      return result;
    },
    { supports: 0, no_support: 0, contradicts: 0, mixed: 0 },
  );

  return (
    <section style={{ marginTop: 34, borderTop: `1px solid ${RULE}` }}>
      <div style={{ padding: "24px 0 18px" }}>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 16,
            flexWrap: "wrap",
          }}
        >
          <h2
            style={{
              fontFamily: "var(--font-newsreader), Georgia, serif",
              fontWeight: 400,
              fontSize: 23,
              letterSpacing: "-0.01em",
              margin: 0,
            }}
          >
            Segment evidence heatmap
          </h2>
          <label
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              fontFamily: "var(--font-ibm-plex-mono), monospace",
              fontSize: 10,
              color: GREY,
              textTransform: "uppercase",
              letterSpacing: "0.06em",
            }}
          >
            Dimension
            <select
              value={activeDimension}
              onChange={(event) => setSelectedDimension(event.target.value)}
              style={{
                border: `1px solid ${RULE}`,
                borderRadius: 8,
                background: "#FFFDF9",
                color: INK,
                padding: "7px 28px 7px 9px",
                fontFamily: "inherit",
                fontSize: 11.5,
                textTransform: "none",
                letterSpacing: 0,
                cursor: "pointer",
              }}
            >
              {dimensions.map((dimension) => (
                <option key={dimension} value={dimension}>
                  {dimension.replaceAll("_", " ")}
                </option>
              ))}
            </select>
          </label>
        </div>
        <div
          style={{
            marginTop: 8,
            fontFamily: "var(--font-ibm-plex-mono), monospace",
            fontSize: 10.5,
            color: GREY,
          }}
        >
          {rows.length} segments · {counts.supports} supporting
          {" · "}
          {counts.no_support} without supporting movement
          {counts.contradicts ? ` · ${counts.contradicts} opposite` : ""}
        </div>
      </div>

      <div style={{ marginBottom: 24 }}>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            gap: 12,
            marginBottom: 8,
            fontFamily: "var(--font-ibm-plex-mono), monospace",
            fontSize: 10,
            letterSpacing: "0.08em",
            textTransform: "uppercase",
            color: GREY,
          }}
        >
          <span>{activeDimension.replaceAll("_", " ")}</span>
          <span>{rows.length} segments</span>
        </div>
        <div style={{ overflowX: "auto", borderTop: `1px solid ${RULE}` }}>
          <table
            style={{
              width: "100%",
              minWidth: 520,
              borderCollapse: "collapse",
              fontSize: 11.5,
            }}
          >
            <thead>
              <tr style={{ color: GREY, textAlign: "right" }}>
                <th style={{ ...headerCell, textAlign: "left" }}>Segment</th>
                <th style={headerCell}>Peak seasonal z</th>
                <th style={headerCell}>Mean seasonal z</th>
                <th style={headerCell}>Incident corr.</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => {
                return (
                  <tr key={`${row.dimension}-${row.segment}`}>
                    <td style={{ ...bodyCell, color: INK, fontSize: 12.5 }}>
                      {row.segment}
                    </td>
                    <td style={{ ...bodyCell, ...zCell(row.peakZ) }}>
                      {signed(row.peakZ)}
                    </td>
                    <td style={{ ...bodyCell, ...zCell(row.meanZ) }}>
                      {signed(row.meanZ)}
                    </td>
                    <td
                      style={{
                        ...bodyCell,
                        ...correlationCell(row.incidentCorrelation),
                      }}
                      title={`${row.incidentCorrelationN} paired incident hours`}
                    >
                      {signed(row.incidentCorrelation)}
                      <small style={sampleStyle}>
                        {" "}
                        n={row.incidentCorrelationN}
                      </small>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      <p
        style={{
          margin: "4px 0 0",
          paddingTop: 12,
          borderTop: `1px solid ${RULE}`,
          fontSize: 11.5,
          lineHeight: 1.55,
          color: GREY,
        }}
      >
        “No supporting movement” means the segment stayed within seasonal |z|
        &lt; 1 for at least 75% of scored incident hours, or showed weak,
        unaligned residual movement. This rules the segment out under this
        statistical test; it does not prove causality for segments that do
        support it.
      </p>
    </section>
  );
}

const headerCell = {
  padding: "8px 7px",
  borderBottom: `1px solid ${RULE}`,
  fontFamily: "var(--font-ibm-plex-mono), monospace",
  fontSize: 9,
  fontWeight: 400,
  letterSpacing: "0.04em",
  whiteSpace: "nowrap" as const,
};

const bodyCell = {
  padding: "8px 7px",
  borderBottom: `1px solid ${RULE}`,
  textAlign: "right" as const,
  fontFamily: "var(--font-ibm-plex-mono), monospace",
  whiteSpace: "nowrap" as const,
};

const sampleStyle = {
  display: "block",
  marginTop: 2,
  fontSize: 8.5,
  color: GREY,
};
