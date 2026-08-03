/// <reference types="vitest/globals" />
import { renderHook, waitFor } from '@testing-library/react';

import type { ThreadEvent } from '../../types';
import { parseEvents, useThreadEvents } from './use-thread-events';

const getToken = async () => 'test-token';

const event = (sequence: number, eventId: string): ThreadEvent => ({
  event_id: eventId,
  tenant_id: '20000000-0000-0000-0000-000000000002',
  thread_id: '43000000-0000-0000-0000-000000000001',
  sequence,
  kind: 'agent.public_update',
  occurred_at: '2026-08-01T09:00:00Z',
  payload: {
    type: 'agent',
    execution_id: '90000000-0000-0000-0000-00000000000a',
    agent_id: 'cube_analyst_v1',
    role: 'cube_analyst',
    capability_id: null,
    from_agent_id: null,
    to_agent_id: null,
    summary: `update ${sequence}`,
    provider: null,
    model: null,
    fallback_count: 0,
    latency_ms: null,
    input_tokens: 0,
    output_tokens: 0,
    cost_usd: '0',
  },
});

const frame = (value: ThreadEvent) =>
  `id: ${value.sequence}\nevent: ${value.kind}\ndata: ${JSON.stringify(value)}\n\n`;

/** A body that yields the given chunks then ends, as a real stream would. */
const streamOf = (chunks: readonly string[]) => {
  const encoder = new TextEncoder();
  let index = 0;
  return {
    getReader: () => ({
      read: async () =>
        index < chunks.length
          ? { done: false, value: encoder.encode(chunks[index++]) }
          : { done: true, value: undefined },
    }),
  };
};

beforeEach(() => {
  vi.restoreAllMocks();
});

describe('parseEvents', () => {
  it('reads several events out of one chunk', () => {
    const { events, rest } = parseEvents(frame(event(1, 'a')) + frame(event(2, 'b')));
    expect(events.map((value) => value.sequence)).toEqual([1, 2]);
    expect(rest).toBe('');
  });

  it('holds a partial event until the rest of it arrives', () => {
    const whole = frame(event(1, 'a'));
    const split = Math.floor(whole.length / 2);

    const first = parseEvents(whole.slice(0, split));
    expect(first.events).toHaveLength(0);

    const second = parseEvents(first.rest + whole.slice(split));
    expect(second.events.map((value) => value.event_id)).toEqual(['a']);
  });

  it('ignores the heartbeat comment', () => {
    const { events } = parseEvents(`: heartbeat\n\n${frame(event(1, 'a'))}`);
    expect(events).toHaveLength(1);
  });

  it('drops a payload it cannot parse rather than throwing', () => {
    const { events } = parseEvents(`data: {not json\n\n${frame(event(1, 'a'))}`);
    expect(events.map((value) => value.event_id)).toEqual(['a']);
  });
});

describe('useThreadEvents', () => {
  it('resumes after the snapshot cursor', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      status: 200,
      body: streamOf([frame(event(8, 'a'))]),
    } as unknown as Response);

    renderHook(() => useThreadEvents(getToken, '43000000-0000-0000-0000-000000000001', 7));

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toContain('after=7');
    expect((init?.headers as Record<string, string>)['Last-Event-ID']).toBe('7');
    expect((init?.headers as Record<string, string>).Authorization).toBe('Bearer test-token');
  });

  it('does not surface an event that a reconnect replayed', async () => {
    // The same event id arrives twice, exactly as a resumed backlog would.
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      status: 200,
      body: streamOf([frame(event(1, 'a')), frame(event(1, 'a')) + frame(event(2, 'b'))]),
    } as unknown as Response);

    const { result } = renderHook(() =>
      useThreadEvents(getToken, '43000000-0000-0000-0000-000000000001', 0),
    );

    await waitFor(() => expect(result.current.events).toHaveLength(2));
    expect(result.current.events.map((value) => value.event_id)).toEqual(['a', 'b']);
  });

  it('stops and reports nothing when there is no thread', () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch');
    const { result } = renderHook(() => useThreadEvents(getToken, null, 0));

    expect(result.current.status).toBe('idle');
    expect(result.current.events).toEqual([]);
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
