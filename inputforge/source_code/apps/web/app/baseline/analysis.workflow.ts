import "server-only";

import type { ClientSession, SessionSnapshot } from "eve/client";
import { sleep, FatalError } from "workflow";
import type {
  AnalysisOutput,
  IncidentAnalysisScope,
} from "./analysis.server";
import {
  OUTPUT_SCHEMA,
  buildAgentClient,
  isAnalysisOutput,
  saveAnalysisCompleted,
  saveAnalysisFailed,
  saveAnalysisProgress,
  toolCallsFromEvents,
} from "./analysis.server";
import type { ChatToolCall } from "./types";

const POLL_INTERVAL = "500ms";
// Occasionally a snapshot() call over the local loopback to eve's dev host
// never resolves (observed even once the underlying session had already
// completed). Bounding it lets the workflow's own poll loop retry on a
// fresh connection instead of the step hanging indefinitely.
const SNAPSHOT_TIMEOUT_MS = 20_000;

async function snapshotOrNull(
  session: ClientSession,
): Promise<SessionSnapshot | null> {
  try {
    return await session.snapshot({
      signal: AbortSignal.timeout(SNAPSHOT_TIMEOUT_MS),
    });
  } catch (error) {
    if (
      error instanceof Error &&
      (error.name === "TimeoutError" || error.name === "AbortError")
    ) {
      return null;
    }
    throw error;
  }
}

async function startAnalysisSession(
  incident: IncidentAnalysisScope,
  host: string,
): Promise<{ rootSessionId: string }> {
  "use step";

  const client = buildAgentClient(host);
  const session = client.session();
  const response = await session.send<AnalysisOutput>({
    message:
      "Run the on-demand analysis for this incident now. Delegate to root_cause_analyst and return its structured result.",
    clientContext: JSON.stringify({
      onDemandAnalysisRequest: {
        id: incident.id,
        metric: incident.metric,
        methods: incident.methods,
        startTime: incident.startTime,
        endTime: incident.endTime,
        maxAbsZ: incident.maxAbsZ,
        segmentSignals: incident.segmentSignals,
        relatedMetrics: incident.relatedMetrics,
      },
    }),
    outputSchema: OUTPUT_SCHEMA,
  });
  return { rootSessionId: response.sessionId };
}

async function pollRootForDelegation(
  rootSessionId: string,
  host: string,
): Promise<{ agentSessionId: string } | null> {
  "use step";

  const client = buildAgentClient(host);
  const root = client.session({ sessionId: rootSessionId, streamIndex: 0 });
  const snapshot = await snapshotOrNull(root);
  if (!snapshot) return null;
  for (const event of snapshot.events) {
    if (event.type === "session.failed") {
      throw new FatalError(event.data.message);
    }
    if (
      event.type === "subagent.called" &&
      event.data.toolName === "root_cause_analyst"
    ) {
      return { agentSessionId: event.data.childSessionId };
    }
  }
  return null;
}

async function pollChildSnapshot(
  agentSessionId: string,
  host: string,
): Promise<{ toolCalls: ChatToolCall[]; completed: boolean } | null> {
  "use step";

  const client = buildAgentClient(host);
  const child = client.session({ sessionId: agentSessionId, streamIndex: 0 });
  const snapshot = await snapshotOrNull(child);
  if (!snapshot) return null;
  const failure = snapshot.events.find(
    (event) => event.type === "session.failed",
  );
  if (failure?.type === "session.failed") {
    throw new FatalError(failure.data.message);
  }
  return {
    toolCalls: toolCallsFromEvents(snapshot.events),
    completed: snapshot.events.some(
      (event) => event.type === "session.completed",
    ),
  };
}

async function pollRootForOutput(
  rootSessionId: string,
  host: string,
): Promise<AnalysisOutput | null> {
  "use step";

  const client = buildAgentClient(host);
  const root = client.session({ sessionId: rootSessionId, streamIndex: 0 });
  const snapshot = await snapshotOrNull(root);
  if (!snapshot) return null;
  const failure = snapshot.events.find(
    (event) => event.type === "session.failed",
  );
  if (failure?.type === "session.failed") {
    throw new FatalError(failure.data.message);
  }
  const result = snapshot.events
    .filter((event) => event.type === "result.completed")
    .at(-1);
  if (result?.type === "result.completed" && isAnalysisOutput(result.data.result)) {
    return result.data.result;
  }
  return null;
}

async function persistProgress(
  incidentId: string,
  agentSessionId: string,
  toolCalls: ChatToolCall[],
): Promise<void> {
  "use step";
  await saveAnalysisProgress(incidentId, agentSessionId, toolCalls);
}

async function finalizeCompleted(
  incidentId: string,
  output: AnalysisOutput,
  toolCalls: ChatToolCall[],
  agentSessionId: string,
): Promise<void> {
  "use step";
  await saveAnalysisCompleted(incidentId, output, toolCalls, agentSessionId);
}

async function finalizeFailed(
  incidentId: string,
  message: string,
): Promise<void> {
  "use step";
  await saveAnalysisFailed(incidentId, message);
}

/**
 * Drives the eve `anomaly_analyst` session to completion and mirrors its
 * progress into Postgres. eve's own runtime already persists the session
 * itself; this workflow makes the *driving loop* durable too, so a dev
 * reload or a redeploy mid-analysis resumes polling instead of leaving the
 * incident stuck in "running" forever.
 */
export async function analyzeIncidentWorkflow(
  incident: IncidentAnalysisScope,
  host: string,
) {
  "use workflow";

  try {
    const { rootSessionId } = await startAnalysisSession(incident, host);

    let agentSessionId: string | undefined;
    let toolCalls: ChatToolCall[] = [];
    while (!agentSessionId) {
      const delegation = await pollRootForDelegation(rootSessionId, host);
      if (delegation) {
        agentSessionId = delegation.agentSessionId;
        await persistProgress(incident.id, agentSessionId, toolCalls);
      } else {
        await sleep(POLL_INTERVAL);
      }
    }

    let persistedTrace = "";
    let childCompleted = false;
    while (!childCompleted) {
      const child = await pollChildSnapshot(agentSessionId, host);
      if (child) {
        toolCalls = child.toolCalls;
        const nextTrace = JSON.stringify(toolCalls);
        if (nextTrace !== persistedTrace) {
          persistedTrace = nextTrace;
          await persistProgress(incident.id, agentSessionId, toolCalls);
        }
        childCompleted = child.completed;
      }
      if (!childCompleted) await sleep(POLL_INTERVAL);
    }

    let output: AnalysisOutput | null = null;
    while (!output) {
      output = await pollRootForOutput(rootSessionId, host);
      if (!output) await sleep(POLL_INTERVAL);
    }

    if (!toolCalls.length) {
      throw new Error(
        "The anomaly analyst returned without querying ClickHouse.",
      );
    }

    await finalizeCompleted(incident.id, output, toolCalls, agentSessionId);
    return { status: "completed" as const };
  } catch (error) {
    const message =
      error instanceof Error ? error.message : "Unknown anomaly analysis error";
    await finalizeFailed(incident.id, message);
    throw error;
  }
}
