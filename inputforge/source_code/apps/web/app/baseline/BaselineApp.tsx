"use client";

import { useRouter } from "next/navigation";
import { DetailView } from "./DetailView";
import { Header } from "./Header";
import { IncidentList } from "./IncidentList";
import { BG, DEFAULT_ACCENT, INK } from "./theme";
import type { DashboardData } from "./types";

export interface BaselineAppProps {
  data: DashboardData;
  accent?: string;
  incidentId?: string;
}

export function BaselineApp({
  data,
  accent = DEFAULT_ACCENT,
  incidentId,
}: BaselineAppProps) {
  const router = useRouter();
  // The URL is the only source of truth for which screen is showing —
  // no local screen/selection state to avoid it drifting from the route.
  const selectedIncident = incidentId
    ? data.incidents.find((incident) => incident.id === incidentId)
    : undefined;

  function openDetail(id: string) {
    router.push(`/incidents/${encodeURIComponent(id)}`);
  }

  return (
    <div
      style={{
        minHeight: "100vh",
        background: BG,
        color: INK,
        fontFamily: "'Helvetica Neue', Helvetica, Arial, sans-serif",
        WebkitFontSmoothing: "antialiased",
      }}
    >
      <Header />
      {!selectedIncident && (
        <main
          style={{
            padding: "30px 28px 64px",
            maxWidth: 1420,
            margin: "0 auto",
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "flex-end",
              justifyContent: "space-between",
              gap: 24,
              marginBottom: 26,
            }}
          >
            <div style={{ maxWidth: 680 }}>
              <h1
                style={{
                  fontFamily: "var(--font-newsreader), Georgia, serif",
                  fontWeight: 400,
                  fontSize: 34,
                  lineHeight: 1.15,
                  letterSpacing: "-0.015em",
                  margin: "0 0 8px",
                }}
              >
                {data.incidents.length
                  ? `${data.incidents.length} incident${data.incidents.length === 1 ? "" : "s"} need attention.`
                  : "No reportable incidents."}
              </h1>
              {data.error && (
                <p
                  style={{
                    margin: 0,
                    fontSize: 14.5,
                    lineHeight: 1.55,
                    color: "#6B675C",
                  }}
                >
                  {`Live data unavailable: ${data.error}`}
                </p>
              )}
            </div>
          </div>

          <IncidentList
            incidents={data.incidents}
            metrics={data.metrics}
            onOpenDetail={openDetail}
          />
        </main>
      )}

      {selectedIncident && (
        <DetailView
          key={selectedIncident.id}
          incident={selectedIncident}
          accent={accent}
          onBack={() => router.push("/")}
        />
      )}
    </div>
  );
}
