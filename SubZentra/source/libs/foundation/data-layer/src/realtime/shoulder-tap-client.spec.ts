import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  ShoulderTapClient,
  type ShoulderTapEnvelope,
  type ShoulderTapEvent,
} from './shoulder-tap-client';

/**
 * Tiny WebSocket fake whose only contract is what the client touches:
 * onopen / onmessage / onclose / readyState / send / close.
 */
class FakeWebSocket {
  static OPEN = 1;
  onopen: (() => void) | null = null;
  onmessage: ((ev: { data: unknown }) => void) | null = null;
  onerror: (() => void) | null = null;
  onclose: (() => void) | null = null;
  readyState = FakeWebSocket.OPEN;
  sent: string[] = [];

  constructor(public readonly url: string) {
    FakeWebSocket.lastInstance = this;
  }

  send(data: string): void {
    this.sent.push(data);
  }

  close(): void {
    this.readyState = 3;
    this.onclose?.();
  }

  static lastInstance: FakeWebSocket | null = null;
}

const setUpGlobals = () => {
  // jsdom does not include localStorage in some setups; provide a minimal shim.
  const store = new Map<string, string>();
  vi.stubGlobal('window', {
    localStorage: {
      getItem: (k: string) => store.get(k) ?? null,
      setItem: (k: string, v: string) => store.set(k, v),
      removeItem: (k: string) => store.delete(k),
    },
  });
  vi.stubGlobal('WebSocket', FakeWebSocket as unknown as typeof WebSocket);
};

const requireSocket = (): FakeWebSocket => {
  const sock = FakeWebSocket.lastInstance;
  if (!sock) {
    throw new Error('expected a FakeWebSocket instance');
  }
  return sock;
};

const issueTicket = () =>
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => ({
      ok: true,
      json: async () => ({ ticket: 'tkt_1', connect_url: '/ws/connect/tkt_1' }),
    })) as unknown as typeof fetch,
  );

describe('ShoulderTapClient', () => {
  beforeEach(() => {
    setUpGlobals();
    issueTicket();
    FakeWebSocket.lastInstance = null;
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it('parses an envelope and emits a ShoulderTapEvent with a derived table', async () => {
    const calls: ShoulderTapEvent[] = [];
    const client = new ShoulderTapClient({
      gatewayUrl: 'https://api.test',
      getAccessToken: async () => 'token',
      onShoulderTap: (e) => calls.push(e),
    });

    await client.connect();
    requireSocket().onopen?.();

    const envelope: ShoulderTapEnvelope = {
      type: 'MUTATION',
      topic: 'event.ws_A.porygon.object_record.rec_88',
      entity_id: 'rec_88',
      action: 'UPDATED',
      ts: '2026-05-28T14:50:00Z',
      seq: 12,
    };
    requireSocket().onmessage?.({ data: JSON.stringify(envelope) });

    expect(calls).toHaveLength(1);
    expect(calls[0]).toEqual({
      topic: 'event.ws_A.porygon.object_record.rec_88',
      entityId: 'rec_88',
      action: 'updated',
      table: 'object_record',
      timestamp: '2026-05-28T14:50:00Z',
    });
    expect(client.getLastEventTimestamp()).toBe('2026-05-28T14:50:00Z');
  });

  it('ignores malformed messages without throwing', async () => {
    const calls: ShoulderTapEvent[] = [];
    const client = new ShoulderTapClient({
      gatewayUrl: 'https://api.test',
      getAccessToken: async () => 'token',
      onShoulderTap: (e) => calls.push(e),
    });
    await client.connect();
    requireSocket().onopen?.();

    requireSocket().onmessage?.({ data: 'not-json' });
    requireSocket().onmessage?.({ data: '{"type":"OTHER"}' });
    requireSocket().onmessage?.({ data: 123 });

    expect(calls).toHaveLength(0);
  });

  it('appends ?after=<lastTs> on reconnect ticket requests', async () => {
    const fetchMock = vi.fn(async () => ({
      ok: true,
      json: async () => ({ ticket: 'tkt_2', connect_url: '/ws/connect/tkt_2' }),
    })) as unknown as typeof fetch;
    vi.stubGlobal('fetch', fetchMock);

    window.localStorage.setItem('oz.realtime.lastEventTs', '2026-05-28T14:50:00Z');
    const tapSink = vi.fn();
    const client = new ShoulderTapClient({
      gatewayUrl: 'https://api.test',
      getAccessToken: async () => 'token',
      onShoulderTap: tapSink,
    });
    await client.connect();

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const calledWith = (fetchMock as unknown as { mock: { calls: unknown[][] } }).mock.calls[0][0];
    expect(String(calledWith)).toContain('after=2026-05-28T14%3A50%3A00Z');
  });
});
