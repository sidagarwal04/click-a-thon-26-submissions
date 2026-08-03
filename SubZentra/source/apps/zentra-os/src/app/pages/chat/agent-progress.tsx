/**
 * What the agents are doing, while they are doing it.
 *
 * Every line here comes from the public Work Feed, which is the only stream
 * the server considers safe to show: a `summary` is a sentence an agent wrote
 * for a reader, never a prompt, a row, or a credential. Nothing is inferred
 * from timing or invented to fill a gap — if the feed says nothing, the rail
 * says nothing.
 *
 * Agents are named from `/v1/agents` rather than from a table in here. The
 * roster is registry data and can change without this file being touched.
 */

import { Badge } from '@open-zentra/foundation-design-system';
import { Icon } from '@open-zentra/foundation-icons';

import type { Agent, AgentEventPayload, ThreadEvent } from '../../types';
import type { FeedStatus } from './use-thread-events';

interface Line {
  readonly id: string;
  readonly agentId: string | null;
  readonly text: string;
  readonly done: boolean;
}

const isAgentPayload = (
  event: ThreadEvent,
): event is ThreadEvent & {
  readonly payload: AgentEventPayload;
} => event.payload.type === 'agent';

/**
 * Reduce the feed to the lines worth showing.
 *
 * `agent.capability_used` is dropped: it fires often, says little a reader can
 * act on, and would bury the sentences that do.
 */
export const progressLines = (events: readonly ThreadEvent[]): readonly Line[] => {
  const lines: Line[] = [];

  for (const event of events) {
    if (event.kind === 'investigation.queued') {
      lines.push({
        id: event.event_id,
        agentId: null,
        text: 'Investigation queued.',
        done: true,
      });
      continue;
    }
    if (event.kind === 'finding.published' && event.payload.type === 'finding') {
      lines.push({
        id: event.event_id,
        agentId: null,
        text: `Finding published with ${event.payload.citation_count} citations.`,
        done: true,
      });
      continue;
    }
    if (!isAgentPayload(event)) continue;

    const payload = event.payload;
    if (event.kind === 'agent.started') {
      lines.push({
        id: event.event_id,
        agentId: payload.agent_id,
        text: payload.summary ?? 'Working…',
        done: false,
      });
      continue;
    }
    if (event.kind === 'agent.public_update' && payload.summary) {
      lines.push({
        id: event.event_id,
        agentId: payload.agent_id,
        text: payload.summary,
        done: false,
      });
      continue;
    }
    if (event.kind === 'agent.handoff') {
      lines.push({
        id: event.event_id,
        agentId: payload.to_agent_id ?? payload.agent_id,
        text: payload.summary ?? 'Handed the work on.',
        done: false,
      });
      continue;
    }
    if (event.kind === 'agent.completed') {
      // Close out this agent's open lines rather than adding another.
      for (let index = lines.length - 1; index >= 0; index -= 1) {
        if (lines[index].agentId === payload.agent_id)
          lines[index] = {
            ...lines[index],
            done: true,
          };
      }
    }
  }

  return lines;
};

export const AgentProgress = ({
  events,
  status,
  agents,
}: {
  readonly events: readonly ThreadEvent[];
  readonly status: FeedStatus;
  readonly agents: readonly Agent[];
}) => {
  const lines = progressLines(events);
  if (lines.length === 0 && status !== 'reconnecting') return null;

  const nameOf = (agentId: string | null) =>
    agents.find((agent) => agent.agent_id === agentId)?.display_name ?? agentId;

  return (
    <section
      className="rounded-sm border border-border px-4 py-3"
      aria-live="polite"
      aria-label="Agent progress"
    >
      {status === 'reconnecting' ? (
        <Badge intent="warning" size="sm">
          Reconnecting to the work feed
        </Badge>
      ) : null}

      <ol className="m-0 flex list-none flex-col gap-2 p-0">
        {lines.map((line) => (
          <li key={line.id} className="flex items-start gap-3">
            <span
              className={
                line.done ? 'mt-1 text-foreground-muted' : 'mt-1 animate-pulse text-primary'
              }
              aria-hidden="true"
            >
              <Icon name={line.done ? 'check_circle' : 'loader_2'} size="sm" />
            </span>
            <span className="min-w-0 flex-1 text-sm text-foreground-muted">
              {line.agentId ? (
                <strong className="mr-2 font-mono text-[10px] uppercase tracking-[0.14em] text-foreground">
                  {nameOf(line.agentId)}
                </strong>
              ) : null}
              {line.text}
            </span>
          </li>
        ))}
      </ol>
    </section>
  );
};
