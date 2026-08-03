/**
 * The shapes the chat surface renders.
 *
 * Unlike `thread.ts`, these are *not* the wire contract — they are the small
 * view model the chat components consume, derived from a `Thread` snapshot by
 * `to-chat-message.ts`. The distinction matters: the server reports who
 * authored a message and what kind it is, and the surface wants a role. That
 * derivation belongs in one mapper, not scattered across components.
 */

import type { IconName } from '@open-zentra/foundation-icons';

export type ChatRole = 'user' | 'assistant';

export interface ChatMessage {
  readonly message_id: string;
  /** Derived from `authored_by_user`. The API has no notion of a role. */
  readonly role: ChatRole;
  /**
   * The server's own message kind, carried through unchanged —
   * `user_question`, `router_clarification`, and whatever the vocabulary grows
   * to next. A `router_clarification` is not rendered like an answer.
   */
  readonly kind: string;
  /** Markdown. Rendered, never injected as HTML. */
  readonly content: string;
  readonly created_at: string;
  /**
   * An Investigation this answer came from, when the agent opened one.
   * Null for a message that needed no governed query.
   */
  readonly investigation_id: string | null;
}

/** A starting question offered on an empty thread. */
export interface ChatSuggestion {
  readonly suggestion_id: string;
  readonly icon: IconName;
  readonly label: string;
  /** What is sent when the card is chosen. */
  readonly prompt: string;
}
