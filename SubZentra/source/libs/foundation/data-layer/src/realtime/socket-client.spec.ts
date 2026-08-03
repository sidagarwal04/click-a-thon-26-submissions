import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  REALTIME_CONNECTION_STATE,
  REALTIME_SERVER_MESSAGE_TYPE,
  REALTIME_SUBSCRIPTION_STATE,
} from '@open-zentra/foundation-data-model';

import { RealtimeSocketClient } from './socket-client';

class FakeWebSocket {
  static instances: FakeWebSocket[] = [];

  static readonly OPEN = 1;
  static readonly CONNECTING = 0;
  static readonly CLOSED = 3;

  readonly url: string;
  readonly protocols?: string | string[];
  readonly sent: string[] = [];
  readyState = FakeWebSocket.CONNECTING;

  private listeners = new Map<string, Set<(event: unknown) => void>>();

  constructor(url: string, protocols?: string | string[]) {
    this.url = url;
    this.protocols = protocols;
    FakeWebSocket.instances.push(this);
  }

  addEventListener(type: string, listener: (event: unknown) => void): void {
    const existing = this.listeners.get(type) ?? new Set();
    existing.add(listener);
    this.listeners.set(type, existing);
  }

  removeEventListener(type: string, listener: (event: unknown) => void): void {
    this.listeners.get(type)?.delete(listener);
  }

  send(payload: string): void {
    this.sent.push(payload);
  }

  close(): void {
    this.readyState = FakeWebSocket.CLOSED;
    this.emit('close', {});
  }

  emit(type: string, event: Record<string, unknown>): void {
    if (type === 'open') {
      this.readyState = FakeWebSocket.OPEN;
    }

    const listeners = this.listeners.get(type);
    listeners?.forEach((listener) => listener(event));
  }
}

describe('RealtimeSocketClient', () => {
  const originalWebSocket = globalThis.WebSocket;

  beforeEach(() => {
    FakeWebSocket.instances = [];
    globalThis.WebSocket = FakeWebSocket as unknown as typeof WebSocket;
  });

  afterEach(() => {
    globalThis.WebSocket = originalWebSocket;
  });

  it('completes hello + subscribe handshake and persists cursors', async () => {
    const setRealtimeCursors = vi.fn().mockResolvedValue(undefined);
    const getTicket = vi.fn().mockResolvedValue('ticket_123');
    const client = new RealtimeSocketClient(
      {
        url: 'wss://example.test/realtime',
        protocolVersion: '1.0',
        auth: {
          mode: 'ticket',
          getTicket,
        },
      },
      {
        axiosInstance: { request: vi.fn(), defaults: {} } as never,
        syncState: {
          getRealtimeCursors: vi.fn().mockResolvedValue(undefined),
          setRealtimeCursors,
        },
      },
    );

    client.registerTopics([{ topic: 'events', table: 'events' }]);

    const connectPromise = client.connect();
    await new Promise((resolve) => setTimeout(resolve, 0));
    const socket = FakeWebSocket.instances[0];
    expect(getTicket).toHaveBeenCalledTimes(1);
    expect(socket.url).toContain('ticket=ticket_123');

    socket.emit('open', {});

    const hello = JSON.parse(socket.sent[0]);
    expect(hello.type).toBe('hello');

    socket.emit('message', {
      data: JSON.stringify({
        type: REALTIME_SERVER_MESSAGE_TYPE.HELLO_ACK,
        messageId: 'hello_ack_1',
        requestId: hello.requestId,
        connectionId: 'conn_1',
        protocolVersion: '1.0',
        negotiatedProtocolVersion: '1.0',
        heartbeatIntervalMs: 10_000,
        capabilities: ['resume'],
        resumeAccepted: true,
        serverTime: Date.now(),
      }),
    });

    await new Promise((resolve) => setTimeout(resolve, 0));
    const subscribe = JSON.parse(socket.sent[1]);
    expect(subscribe.type).toBe('subscribe');

    socket.emit('message', {
      data: JSON.stringify({
        type: REALTIME_SERVER_MESSAGE_TYPE.SUBSCRIBED,
        messageId: 'subscribed_1',
        requestId: subscribe.requestId,
        topic: 'events',
        table: 'events',
      }),
    });

    await connectPromise;

    expect(client.getStatus()).toBe(REALTIME_CONNECTION_STATE.READY);
    expect(client.getSubscriptions()['events::events']?.state).toBe(
      REALTIME_SUBSCRIPTION_STATE.SUBSCRIBED,
    );

    socket.emit('message', {
      data: JSON.stringify({
        type: REALTIME_SERVER_MESSAGE_TYPE.EVENT,
        messageId: 'event_1',
        topic: 'events',
        table: 'events',
        entityId: 'evt_1',
        seq: 1,
        occurredAt: Date.now(),
        version: 1,
        kind: 'updated',
        payload: { id: 'evt_1', version: 1 },
      }),
    });

    expect(setRealtimeCursors).toHaveBeenCalledTimes(1);
    expect(client.getCursorStore()['events::events']?.seq).toBe(1);
    client.disconnect();
  });

  it('turns sequence gaps into resync-required state', async () => {
    const getTicket = vi.fn().mockResolvedValue('ticket_gap');
    const client = new RealtimeSocketClient(
      {
        url: 'wss://example.test/realtime',
        protocolVersion: '1.0',
        auth: {
          mode: 'ticket',
          getTicket,
        },
      },
      {
        axiosInstance: { request: vi.fn(), defaults: {} } as never,
        syncState: {
          getRealtimeCursors: vi.fn().mockResolvedValue({
            'events::events': {
              topic: 'events',
              table: 'events',
              seq: 1,
              version: 1,
              occurredAt: Date.now(),
              updatedAt: Date.now(),
            },
          }),
          setRealtimeCursors: vi.fn().mockResolvedValue(undefined),
        },
      },
    );

    const receivedTypes: string[] = [];
    client.subscribeMessages((message) => {
      receivedTypes.push(message.type);
    });

    const connectPromise = client.connect();
    await new Promise((resolve) => setTimeout(resolve, 0));
    const socket = FakeWebSocket.instances[0];
    socket.emit('open', {});

    const hello = JSON.parse(socket.sent[0]);
    socket.emit('message', {
      data: JSON.stringify({
        type: REALTIME_SERVER_MESSAGE_TYPE.HELLO_ACK,
        messageId: 'hello_ack_2',
        requestId: hello.requestId,
        connectionId: 'conn_2',
        protocolVersion: '1.0',
        negotiatedProtocolVersion: '1.0',
        heartbeatIntervalMs: 10_000,
        capabilities: ['resume'],
        resumeAccepted: true,
        serverTime: Date.now(),
      }),
    });

    await connectPromise;

    socket.emit('message', {
      data: JSON.stringify({
        type: REALTIME_SERVER_MESSAGE_TYPE.EVENT,
        messageId: 'event_gap',
        topic: 'events',
        table: 'events',
        entityId: 'evt_1',
        seq: 3,
        occurredAt: Date.now(),
        version: 3,
        kind: 'updated',
        payload: { id: 'evt_1', version: 3 },
      }),
    });

    expect(receivedTypes).toContain(REALTIME_SERVER_MESSAGE_TYPE.RESYNC_REQUIRED);
    expect(client.getSubscriptions()['events::events']?.state).toBe(
      REALTIME_SUBSCRIPTION_STATE.RESYNC_REQUIRED,
    );
    client.disconnect();
  });

  it('fetches tickets through ticketEndpoint when getTicket is not provided', async () => {
    const axiosRequest = vi.fn().mockResolvedValue({
      data: {
        data: {
          ticket: 'endpoint_ticket',
          queryParam: 'rt',
        },
      },
    });

    const client = new RealtimeSocketClient(
      {
        url: 'wss://example.test/realtime',
        protocolVersion: '1.0',
        auth: {
          mode: 'ticket',
          ticketEndpoint: {
            path: '/auth/realtime-ticket',
          },
        },
      },
      {
        axiosInstance: { request: axiosRequest, defaults: {} } as never,
        syncState: {
          getRealtimeCursors: vi.fn().mockResolvedValue(undefined),
          setRealtimeCursors: vi.fn().mockResolvedValue(undefined),
        },
      },
    );

    const connectPromise = client.connect();
    await new Promise((resolve) => setTimeout(resolve, 0));

    const socket = FakeWebSocket.instances[0];
    expect(axiosRequest).toHaveBeenCalledWith(
      expect.objectContaining({
        method: 'GET',
        url: '/auth/realtime-ticket',
      }),
    );
    expect(socket.url).toContain('rt=endpoint_ticket');

    socket.emit('open', {});
    const hello = JSON.parse(socket.sent[0]);
    socket.emit('message', {
      data: JSON.stringify({
        type: REALTIME_SERVER_MESSAGE_TYPE.HELLO_ACK,
        messageId: 'hello_ack_ep',
        requestId: hello.requestId,
        connectionId: 'conn_ep',
        protocolVersion: '1.0',
        negotiatedProtocolVersion: '1.0',
        heartbeatIntervalMs: 10_000,
        capabilities: ['resume'],
        resumeAccepted: true,
        serverTime: Date.now(),
      }),
    });

    await connectPromise;
    client.disconnect();
  });

  it('prefers getTicket over ticketEndpoint when both are configured', async () => {
    const getTicket = vi.fn().mockResolvedValue('preferred_ticket');
    const axiosRequest = vi.fn();

    const client = new RealtimeSocketClient(
      {
        url: 'wss://example.test/realtime',
        protocolVersion: '1.0',
        auth: {
          mode: 'ticket',
          getTicket,
          ticketEndpoint: {
            path: '/auth/realtime-ticket',
          },
        },
      },
      {
        axiosInstance: { request: axiosRequest, defaults: {} } as never,
        syncState: {
          getRealtimeCursors: vi.fn().mockResolvedValue(undefined),
          setRealtimeCursors: vi.fn().mockResolvedValue(undefined),
        },
      },
    );

    const connectPromise = client.connect();
    await new Promise((resolve) => setTimeout(resolve, 0));

    const socket = FakeWebSocket.instances[0];
    expect(getTicket).toHaveBeenCalledTimes(1);
    expect(axiosRequest).not.toHaveBeenCalled();
    expect(socket.url).toContain('ticket=preferred_ticket');

    socket.emit('open', {});
    const hello = JSON.parse(socket.sent[0]);
    socket.emit('message', {
      data: JSON.stringify({
        type: REALTIME_SERVER_MESSAGE_TYPE.HELLO_ACK,
        messageId: 'hello_ack_pref',
        requestId: hello.requestId,
        connectionId: 'conn_pref',
        protocolVersion: '1.0',
        negotiatedProtocolVersion: '1.0',
        heartbeatIntervalMs: 10_000,
        capabilities: ['resume'],
        resumeAccepted: true,
        serverTime: Date.now(),
      }),
    });

    await connectPromise;
    client.disconnect();
  });

  it('fails fast when websocket auth is missing', async () => {
    const client = new RealtimeSocketClient(
      {
        url: 'wss://example.test/realtime',
        protocolVersion: '1.0',
      } as never,
      {
        axiosInstance: { request: vi.fn(), defaults: {} } as never,
        syncState: {
          getRealtimeCursors: vi.fn().mockResolvedValue(undefined),
          setRealtimeCursors: vi.fn().mockResolvedValue(undefined),
        },
      },
    );

    await expect(client.connect()).rejects.toThrow(
      'Realtime websocket auth is required and must use ticket mode.',
    );
  });

  it('fails fast when ticket auth has no ticket source', async () => {
    const client = new RealtimeSocketClient(
      {
        url: 'wss://example.test/realtime',
        protocolVersion: '1.0',
        auth: {
          mode: 'ticket',
        } as never,
      },
      {
        axiosInstance: { request: vi.fn(), defaults: {} } as never,
        syncState: {
          getRealtimeCursors: vi.fn().mockResolvedValue(undefined),
          setRealtimeCursors: vi.fn().mockResolvedValue(undefined),
        },
      },
    );

    await expect(client.connect()).rejects.toThrow(
      'Realtime websocket ticket auth requires getTicket or ticketEndpoint to return a ticket.',
    );
  });
});
