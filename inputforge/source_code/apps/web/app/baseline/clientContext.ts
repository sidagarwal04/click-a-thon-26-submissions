import type { Incident, IncidentAnalysis } from "./types";

/** Exact detector identifiers and UTC bounds for the investigator's queries. */
export function buildClientContext(
  incident: Incident,
  analysis?: IncidentAnalysis | null,
) {
  return {
    dashboardIncident: {
      id: incident.id,
      metric: incident.metric,
      methods: incident.methods,
      startTime: incident.startTime,
      endTime: incident.endTime,
      maxAbsZ: incident.maxAbsZ,
      segmentSignals: incident.segmentSignals.map(({ dimension, segment }) => ({
        dimension,
        segment,
      })),
    },
    ...(analysis?.status === "completed"
      ? {
          storedIncidentAnalysis: {
            verdict: analysis.verdict,
            sliceAndDice: analysis.sliceAndDice,
            computedAt: analysis.updatedAt,
          },
        }
      : {}),
  };
}
