/**
 * Talking to the Thread API.
 *
 * The chat surface creates analytical work only as a consequence of a Thread
 * message resolving to a governed scenario. It never posts to
 * `/v1/investigations` — that is the older standalone flow the launcher uses,
 * and going through it directly would produce an Investigation no Thread owns.
 */

import { requestJson, type TokenSource } from '../../api';
import type {
  Agent,
  Group,
  Page,
  Project,
  ResolvedCitation,
  Thread,
  ThreadSummary,
  Visualization,
  VisualizationActionResult,
} from '../../types';

const post = (body?: unknown): RequestInit => ({
  method: 'POST',
  ...(body === undefined ? {} : { body: JSON.stringify(body) }),
});

/* -------------------------------------------------------------------------- */
/* Workspace                                                                   */
/* -------------------------------------------------------------------------- */

export const listGroups = (getToken: TokenSource) =>
  requestJson<Page<Group>>('/v1/groups', getToken);

export const createGroup = (getToken: TokenSource, name: string) =>
  requestJson<Group>('/v1/groups', getToken, post({ name }));

export const listProjects = (getToken: TokenSource, groupId: string) =>
  requestJson<Page<Project>>(`/v1/groups/${groupId}/projects`, getToken);

export const createProject = (getToken: TokenSource, groupId: string, name: string) =>
  requestJson<Project>(`/v1/groups/${groupId}/projects`, getToken, post({ name }));

/* -------------------------------------------------------------------------- */
/* Threads                                                                     */
/* -------------------------------------------------------------------------- */

export const listThreads = (getToken: TokenSource, projectId: string, cursor?: string | null) =>
  requestJson<Page<ThreadSummary>>(
    `/v1/projects/${projectId}/threads${cursor ? `?cursor=${encodeURIComponent(cursor)}` : ''}`,
    getToken,
  );

/**
 * A Thread is never created empty — the first message is what the router reads
 * to decide whether there is governed work to do.
 */
export const createThread = (getToken: TokenSource, projectId: string, message: string) =>
  requestJson<Thread>(`/v1/projects/${projectId}/threads`, getToken, post({ message }));

export const getThread = (getToken: TokenSource, threadId: string) =>
  requestJson<Thread>(`/v1/threads/${threadId}`, getToken);

/** The same endpoint serves an initial clarification and a later follow-up. */
export const appendMessage = (getToken: TokenSource, threadId: string, message: string) =>
  requestJson<Thread>(`/v1/threads/${threadId}/messages`, getToken, post({ message }));

export const archiveThread = (getToken: TokenSource, threadId: string) =>
  requestJson<Thread>(`/v1/threads/${threadId}/archive`, getToken, post());

export const restoreThread = (getToken: TokenSource, threadId: string) =>
  requestJson<Thread>(`/v1/threads/${threadId}/restore`, getToken, post());

/** Draft Threads with no Investigation only. The server enforces it. */
export const deleteThread = (getToken: TokenSource, threadId: string) =>
  requestJson<void>(`/v1/threads/${threadId}`, getToken, { method: 'DELETE' });

/* -------------------------------------------------------------------------- */
/* Investigation controls                                                      */
/* -------------------------------------------------------------------------- */

/**
 * Cancellation is cooperative: this returns as soon as the request is
 * recorded, not once the agents have stopped. The Thread snapshot is what says
 * whether they have.
 */
export const cancelInvestigation = (getToken: TokenSource, investigationId: string) =>
  requestJson<unknown>(`/v1/investigations/${investigationId}/cancel`, getToken, post());

/** Creates an immutable linked retry — a new entry in `investigations`. */
export const retryInvestigation = (getToken: TokenSource, investigationId: string) =>
  requestJson<unknown>(`/v1/investigations/${investigationId}/retry`, getToken, post());

/* -------------------------------------------------------------------------- */
/* Visualization                                                               */
/* -------------------------------------------------------------------------- */

export const getInvestigationVisualization = (getToken: TokenSource, investigationId: string) =>
  requestJson<Visualization>(`/v1/investigations/${investigationId}/visualization`, getToken);

/** Renders again without re-running any analysis. */
export const retryVisualization = (getToken: TokenSource, visualizationId: string) =>
  requestJson<Visualization>(`/v1/visualizations/${visualizationId}/retry`, getToken, post());

/**
 * Execute a stored safe action.
 *
 * No parameters are sent. The renderer generated the button, so anything it
 * generated alongside is untrusted; the server resolves `action_id` against
 * the mapping it stored itself and ignores the rest.
 */
export const executeVisualizationAction = (
  getToken: TokenSource,
  visualizationId: string,
  actionId: string,
) =>
  requestJson<VisualizationActionResult>(
    `/v1/visualizations/${visualizationId}/actions/${actionId}/execute`,
    getToken,
    post({ parameters: {} }),
  );

/* -------------------------------------------------------------------------- */
/* Evidence and roster                                                         */
/* -------------------------------------------------------------------------- */

/** Resolves to a citation, or to a tombstone if the evidence was erased. */
export const resolveCitation = (
  getToken: TokenSource,
  investigationId: string,
  citationId: string,
) =>
  requestJson<ResolvedCitation>(
    `/v1/investigations/${investigationId}/citations/${citationId}`,
    getToken,
  );

export const decideApproval = (
  getToken: TokenSource,
  investigationId: string,
  approvalId: string,
  decision: 'approve' | 'reject',
  reason: string | null,
) =>
  requestJson<unknown>(
    `/v1/investigations/${investigationId}/approvals/${approvalId}/decision`,
    getToken,
    post({ decision, reason }),
  );

export const listAgents = (getToken: TokenSource) =>
  requestJson<readonly Agent[]>('/v1/agents', getToken);
