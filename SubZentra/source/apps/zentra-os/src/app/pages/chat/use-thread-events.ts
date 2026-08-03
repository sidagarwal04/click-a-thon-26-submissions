/**
 * Tailing the public Work Feed.
 *
 * The browser's own `EventSource` cannot set an `Authorization` header, and
 * this endpoint is bearer-protected, so the stream is read by hand: `fetch`
 * plus a reader over the response body. That also means the SSE framing is
 * ours to parse, which the parser below does literally rather than cleverly.
 *
 * The contract is snapshot-then-tail. The Thread snapshot hands over an
 * `event_cursor`; the stream resumes after it. A reconnect can replay an event
 * that already arrived, so events are deduplicated by `event_id` — the
 * sequence alone is not enough, because it is also the resume token.
 */

import { useEffect, useRef, useState } from 'react';

import { apiUrl, type TokenSource } from '../../api';
import type { ThreadEvent } from '../../types';

/** How many events the rail keeps. Older ones are in the snapshot anyway. */
const MAX_RETAINED = 200;
const FIRST_RETRY_MS = 1_000;
const MAX_RETRY_MS = 30_000;

export type FeedStatus = 'idle' | 'connecting' | 'open' | 'reconnecting';

/**
 * Split a raw SSE buffer into whole events.
 *
 * Returns the events it could complete and the trailing remainder, because a
 * chunk boundary falls wherever the network decides and a half-received
 * `data:` line is not a malformed event — it is an event that has not finished
 * arriving yet.
 */
export const parseEvents = (
  buffer: string,
): { readonly events: ThreadEvent[]; readonly rest: string } => {
  const blocks = buffer.split('\n\n');
  const rest = blocks.pop() ?? '';
  const events: ThreadEvent[] = [];

  for (const block of blocks) {
    const data = block
      .split('\n')
      // A line opening with ':' is a comment — that is what the heartbeat is.
      .filter((line) => line.startsWith('data:'))
      .map((line) => line.slice('data:'.length).trim())
      .join('\n');
    if (!data) continue;
    try {
      events.push(JSON.parse(data) as ThreadEvent);
    } catch {
      // A payload we cannot parse is a contract we do not understand. Dropping
      // it keeps the rail honest; the snapshot remains the source of truth.
    }
  }

  return { events, rest };
};

/** Declared outside the retry loop so it closes over nothing the loop mutates. */
const wait = (retry: {
  ms: number;
  timer: ReturnType<typeof setTimeout> | undefined;
}): Promise<void> =>
  new Promise<void>((resolve) => {
    retry.timer = setTimeout(resolve, retry.ms);
  });

export interface ThreadFeed {
  readonly events: readonly ThreadEvent[];
  readonly status: FeedStatus;
}

/**
 * Subscribe to one Thread's Work Feed.
 *
 * `onEvent` is held in a ref so a caller can pass an inline closure without
 * tearing down and rebuilding the connection on every render.
 */
const NOTHING: readonly ThreadEvent[] = [];

export const useThreadEvents = (
  getToken: TokenSource,
  threadId: string | null,
  cursor: number,
  onEvent?: (event: ThreadEvent) => void,
): ThreadFeed => {
  // The thread each batch belongs to is stored alongside it, so switching
  // threads discards the old feed by *deriving* an empty one rather than by
  // firing a reset from an effect and re-rendering a second time.
  const [feed, setFeed] = useState<{
    readonly threadId: string | null;
    readonly events: readonly ThreadEvent[];
  }>({ threadId: null, events: NOTHING });
  const [status, setStatus] = useState<FeedStatus>('idle');
  const handler = useRef(onEvent);
  handler.current = onEvent;

  useEffect(() => {
    if (!threadId) return undefined;

    const controller = new AbortController();
    const seen = new Set<string>();
    // Held in one const record so the retry closure below captures an object
    // rather than bindings the loop reassigns underneath it.
    const retry = {
      ms: FIRST_RETRY_MS,
      timer: undefined as ReturnType<typeof setTimeout> | undefined,
    };
    let sequence = cursor;
    let stopped = false;

    const connect = async (): Promise<void> => {
      // A fresh token per attempt. Clerk mints short-lived ones, and although
      // the stream itself is only authorised at connect time, a reconnect an
      // hour later must not present the token it opened with.
      const token = await getToken();
      const response = await fetch(`${apiUrl}/v1/threads/${threadId}/events?after=${sequence}`, {
        signal: controller.signal,
        headers: {
          Accept: 'text/event-stream',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
          // Same decimal meaning as `after`, sent so an intermediary that
          // re-establishes the request on our behalf resumes correctly too.
          'Last-Event-ID': String(sequence),
        },
      });

      if (!response.ok || !response.body) {
        throw new Error(`The work feed returned ${response.status}.`);
      }

      setStatus('open');
      retry.ms = FIRST_RETRY_MS;

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const { events: parsed, rest } = parseEvents(buffer);
        buffer = rest;
        if (parsed.length === 0) continue;

        const fresh = parsed.filter((event) => {
          if (seen.has(event.event_id)) return false;
          seen.add(event.event_id);
          return true;
        });
        for (const event of parsed) {
          sequence = Math.max(sequence, event.sequence);
        }
        if (fresh.length === 0) continue;

        for (const event of fresh) handler.current?.(event);
        setFeed((current) => ({
          threadId,
          events: (current.threadId === threadId ? [...current.events, ...fresh] : fresh).slice(
            -MAX_RETAINED,
          ),
        }));
      }
    };

    const run = async (): Promise<void> => {
      while (!stopped) {
        try {
          setStatus((current) => (current === 'open' ? 'reconnecting' : 'connecting'));
          await connect();
        } catch (error) {
          if (controller.signal.aborted) return;
          void error;
        }
        if (stopped || controller.signal.aborted) return;
        // The server closes an idle stream as readily as a network drops it,
        // so a clean end is a reconnect, not a stop.
        setStatus('reconnecting');
        await wait(retry);
        retry.ms = Math.min(retry.ms * 2, MAX_RETRY_MS);
      }
    };

    void run();

    return () => {
      stopped = true;
      controller.abort();
      if (retry.timer) clearTimeout(retry.timer);
    };
    // `cursor` seeds the resume point once; later cursors arrive as sequences
    // on the stream itself, so reconnecting on every snapshot refetch would
    // restart the feed for no reason.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [threadId, getToken]);

  return {
    events: feed.threadId === threadId ? feed.events : NOTHING,
    status: threadId ? status : 'idle',
  };
};
