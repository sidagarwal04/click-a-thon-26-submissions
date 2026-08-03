/**
 * Turning a Thread snapshot into the entries the chat surface renders.
 *
 * The important thing this file encodes: **an answer is not a message.** The
 * server never appends an agent-authored turn when a Finding is published — a
 * resolved Thread holds exactly the user's question, and everything the agents
 * produced lives on `thread.investigations`. Rendering only `messages` shows a
 * question and nothing else, which is precisely what a reader must not see.
 *
 * So the timeline interleaves the two. Messages carry no Investigation id, so
 * the association is positional: the router opens exactly one Investigation for
 * each question it resolves, and answers a question it cannot resolve with a
 * `router_clarification` instead. Walking the messages in order and consuming
 * one Investigation per resolved question reproduces the server's own pairing
 * without inventing a link the API does not state.
 */

import type { ChatMessage, Thread, ThreadInvestigation } from '../../types';

export interface MessageEntry {
  readonly kind: 'message';
  readonly id: string;
  readonly message: ChatMessage;
}

export interface AnswerEntry {
  readonly kind: 'answer';
  readonly id: string;
  readonly investigation: ThreadInvestigation;
}

export type TimelineEntry = MessageEntry | AnswerEntry;

const toChatMessage = (
  message: Thread['messages'][number],
  investigationId: string | null,
): ChatMessage => ({
  message_id: message.message_id,
  // Derived: the API reports who wrote it, not a role.
  role: message.authored_by_user ? 'user' : 'assistant',
  kind: message.kind,
  content: message.content,
  created_at: message.created_at,
  investigation_id: investigationId,
});

export const toTimeline = (thread: Thread): readonly TimelineEntry[] => {
  const entries: TimelineEntry[] = [];
  let attempt = 0;

  thread.messages.forEach((message, index) => {
    entries.push({
      kind: 'message',
      id: message.message_id,
      message: toChatMessage(message, null),
    });

    if (!message.authored_by_user) return;

    // A clarification immediately after the question is the router declining
    // to open any Investigation, so this question gets no answer entry.
    const next = thread.messages[index + 1];
    if (next && next.kind === 'router_clarification') return;

    const investigation = thread.investigations[attempt];
    if (!investigation) return;
    attempt += 1;
    entries.push({
      kind: 'answer',
      id: investigation.investigation_id,
      investigation,
    });
  });

  return entries;
};

/** The Investigation the surface should be showing controls for. */
export const latestInvestigation = (thread: Thread) =>
  thread.investigations.length > 0 ? thread.investigations[thread.investigations.length - 1] : null;
