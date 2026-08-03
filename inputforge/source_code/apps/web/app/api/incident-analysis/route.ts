import { NextResponse } from "next/server";
import { start } from "workflow/api";
import {
  claimIncidentAnalysis,
  loadIncidentAnalysis,
} from "../../baseline/analysis.server";
import { analyzeIncidentWorkflow } from "../../baseline/analysis.workflow";
import { loadDashboardData } from "../../baseline/data";

interface RequestBody {
  incidentId?: unknown;
}

function validIncidentId(value: unknown): value is string {
  return typeof value === "string" && value.length >= 3 && value.length <= 160;
}

export async function GET(request: Request) {
  const incidentId = new URL(request.url).searchParams.get("incidentId");
  if (!validIncidentId(incidentId)) {
    return NextResponse.json({ error: "Invalid incident ID" }, { status: 400 });
  }

  try {
    const analysis = await loadIncidentAnalysis(incidentId);
    return analysis
      ? NextResponse.json({ analysis })
      : NextResponse.json({ analysis: null }, { status: 404 });
  } catch (error) {
    console.error("Failed to load incident analysis", error);
    return NextResponse.json(
      { error: "Could not load incident analysis" },
      { status: 503 },
    );
  }
}

export async function POST(request: Request) {
  let body: RequestBody;
  try {
    body = (await request.json()) as RequestBody;
  } catch {
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
  }
  if (!validIncidentId(body.incidentId)) {
    return NextResponse.json({ error: "Invalid incident ID" }, { status: 400 });
  }

  try {
    const existing = await loadIncidentAnalysis(body.incidentId);
    if (existing) {
      return NextResponse.json(
        { analysis: existing },
        { status: existing.status === "running" ? 202 : 200 },
      );
    }

    // Resolve the canonical incident server-side rather than trusting browser
    // supplied metric/window fields as analytical query scope.
    const dashboard = await loadDashboardData();
    const incident = dashboard.incidents.find(
      (candidate) => candidate.id === body.incidentId,
    );
    if (!incident) {
      return NextResponse.json({ error: "Incident not found" }, { status: 404 });
    }

    const claimed = await claimIncidentAnalysis(incident);
    if (!claimed) {
      const concurrent = await loadIncidentAnalysis(incident.id);
      return NextResponse.json(
        { analysis: concurrent },
        { status: concurrent?.status === "running" ? 202 : 200 },
      );
    }

    const origin = new URL(request.url).origin;
    await start(analyzeIncidentWorkflow, [incident, origin]);

    const analysis = await loadIncidentAnalysis(incident.id);
    return NextResponse.json({ analysis }, { status: 202 });
  } catch (error) {
    console.error("Failed to analyze incident", error);
    const analysis = await loadIncidentAnalysis(body.incidentId).catch(() => null);
    return NextResponse.json(
      {
        analysis,
        error: "Could not complete incident analysis",
      },
      { status: 503 },
    );
  }
}
