import "server-only";

import { getVercelOidcToken } from "@vercel/oidc";
import { Client, type MessageStreamEvent } from "eve/client";
import type { QueryResultRow } from "pg";
import type {
  AnalysisVerdict,
  ChatToolCall,
  Incident,
  IncidentAnalysis,
  SliceAndDiceFinding,
} from "./types";
import { getPostgresPool } from "./postgres.server";

export const OUTPUT_SCHEMA = {
  type: "object",
  properties: {
    verdict: {
      type: "object",
      properties: {
        label: {
          type: "string",
          enum: [
            "confirmed_anomaly",
            "likely_anomaly",
            "inconclusive",
            "false_positive",
          ],
        },
        summary: { type: "string" },
        confidence: { type: "number", minimum: 0, maximum: 1 },
        severity: {
          type: "string",
          enum: ["low", "medium", "high", "critical"],
        },
      },
      required: ["label", "summary", "confidence", "severity"],
      additionalProperties: false,
    },
    sliceAndDice: {
      type: "array",
      items: {
        type: "object",
        properties: {
          slice: { type: "string" },
          finding: { type: "string" },
          evidence: { type: "string" },
        },
        required: ["slice", "finding", "evidence"],
        additionalProperties: false,
      },
    },
  },
  required: ["verdict", "sliceAndDice"],
  additionalProperties: false,
} as const;

export interface AnalysisOutput {
  verdict: AnalysisVerdict;
  sliceAndDice: SliceAndDiceFinding[];
}

export type IncidentAnalysisScope = Pick<
  Incident,
  | "id"
  | "metric"
  | "methods"
  | "startTime"
  | "endTime"
  | "maxAbsZ"
  | "segmentSignals"
  | "relatedMetrics"
>;

interface AnalysisRow extends QueryResultRow {
  incident_id: string;
  status: IncidentAnalysis["status"];
  verdict: AnalysisVerdict | null;
  slice_and_dice: SliceAndDiceFinding[] | null;
  tool_calls: ChatToolCall[];
  agent_session_id: string | null;
  error: string | null;
  updated_at: Date | string;
}

function toAnalysis(row: AnalysisRow): IncidentAnalysis {
  return {
    incidentId: row.incident_id,
    status: row.status,
    verdict: row.verdict ?? undefined,
    sliceAndDice: row.slice_and_dice ?? [],
    toolCalls: row.tool_calls ?? [],
    agentSessionId: row.agent_session_id ?? undefined,
    error: row.error ?? undefined,
    updatedAt: new Date(row.updated_at).toISOString(),
  };
}

export async function loadIncidentAnalysis(
  incidentId: string,
): Promise<IncidentAnalysis | null> {
  const result = await getPostgresPool().query<AnalysisRow>(
    `SELECT incident_id, status, verdict, slice_and_dice, tool_calls,
            agent_session_id, error, updated_at
     FROM incident_analysis
     WHERE incident_id = $1`,
    [incidentId],
  );
  return result.rows[0] ? toAnalysis(result.rows[0]) : null;
}

export async function claimIncidentAnalysis(
  incident: IncidentAnalysisScope,
): Promise<boolean> {
  const result = await getPostgresPool().query(
    `INSERT INTO incident_analysis (
       incident_id, metric, start_time, end_time, status
     ) VALUES ($1, $2, $3, $4, 'running')
     ON CONFLICT (incident_id) DO NOTHING
     RETURNING incident_id`,
    [incident.id, incident.metric, incident.startTime, incident.endTime],
  );
  return result.rowCount === 1;
}

export function buildAgentClient(host: string): Client {
  const auth = process.env.VERCEL
    ? { vercelOidc: { token: () => getVercelOidcToken() } }
    : undefined;
  return new Client({
    host: process.env.EVE_AGENT_URL ?? host,
    auth,
    redirect: auth ? "manual" : undefined,
  });
}

export function toolCallsFromEvents(
  events: readonly MessageStreamEvent[],
): ChatToolCall[] {
  const calls = new Map<string, ChatToolCall>();
  for (const event of events) {
    if (event.type === "actions.requested") {
      for (const action of event.data.actions) {
        if (action.kind !== "tool-call") continue;
        calls.set(action.callId, {
          name: action.toolName,
          input: action.input,
          state: "input-available",
        });
      }
    }
    if (event.type === "action.result") {
      const result = event.data.result;
      if (result.kind !== "tool-result") continue;
      const existing = calls.get(result.callId);
      calls.set(result.callId, {
        name: existing?.name ?? result.toolName,
        input: existing?.input,
        output: result.output,
        error: event.data.error?.message,
        state:
          event.data.status === "completed"
            ? "output-available"
            : "output-error",
      });
    }
  }
  return [...calls.values()];
}

export async function saveAnalysisProgress(
  incidentId: string,
  agentSessionId: string,
  toolCalls: ChatToolCall[],
): Promise<void> {
  await getPostgresPool().query(
    `UPDATE incident_analysis SET agent_session_id = $2,
       tool_calls = $3::jsonb, updated_at = now()
     WHERE incident_id = $1 AND status = 'running'`,
    [incidentId, agentSessionId, JSON.stringify(toolCalls)],
  );
}

export function isAnalysisOutput(value: unknown): value is AnalysisOutput {
  if (typeof value !== "object" || value === null) return false;
  const candidate = value as Partial<AnalysisOutput>;
  return (
    typeof candidate.verdict?.summary === "string" &&
    typeof candidate.verdict.confidence === "number" &&
    Array.isArray(candidate.sliceAndDice)
  );
}

export async function saveAnalysisCompleted(
  incidentId: string,
  output: AnalysisOutput,
  toolCalls: ChatToolCall[],
  agentSessionId: string,
): Promise<void> {
  await getPostgresPool().query(
    `UPDATE incident_analysis SET
       status = 'completed', verdict = $2::jsonb,
       slice_and_dice = $3::jsonb, tool_calls = $4::jsonb,
       agent_session_id = $5, error = NULL, completed_at = now(),
       updated_at = now()
     WHERE incident_id = $1`,
    [
      incidentId,
      JSON.stringify(output.verdict),
      JSON.stringify(output.sliceAndDice),
      JSON.stringify(toolCalls),
      agentSessionId,
    ],
  );
}

export async function saveAnalysisFailed(
  incidentId: string,
  message: string,
): Promise<void> {
  await getPostgresPool().query(
    `UPDATE incident_analysis SET status = 'failed', error = $2,
       updated_at = now()
     WHERE incident_id = $1`,
    [incidentId, message.slice(0, 2_000)],
  );
}
