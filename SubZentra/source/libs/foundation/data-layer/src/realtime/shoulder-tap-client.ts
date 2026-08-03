/**
 * Minimal shoulder-tap WebSocket client for the OpenZentra gateway.
 *
 * This client speaks the simple JSON envelope the gateway emits:
 *
 *   {"type":"MUTATION","topic":"event.<ws>.<svc>.<agg>","entity_id":"X","action":"UPDATED","ts":"...","seq":N}
 *
 * On every incoming envelope it calls the configured `onShoulderTap` callback
 * (intended to be a thin wrapper around RealtimeEventBridge.apply that triggers
 * TanStack Query invalidation) and persists the timestamp so a reconnect can
 * include `?after=<ts>` and recover events missed while offline.
 *
 * It is intentionally separate from RealtimeSocketClient (which speaks a richer
 * HELLO/SUBSCRIBE/ACK/RESUME protocol the gateway does not currently implement).
 *
 * @module realtime/shoulder-tap-client
 */

export interface ShoulderTapEnvelope {
  readonly type: 'MUTATION';
  readonly topic: string;
  readonly entity_id: string;
  readonly action: string;
  readonly ts: string;
  readonly seq?: number;
}

export interface ShoulderTapEvent {
  readonly topic: string;
  readonly entityId: string;
  readonly action: string;
  readonly table: string;
  readonly timestamp: string;
}

export interface ShoulderTapClientConfig {
  /** Base URL of the gateway, e.g. `https://api.openzentra.local`. No trailing slash. */
  readonly gatewayUrl: string;
  /** Async function that returns the current bearer token for the ticket POST. */
  readonly getAccessToken: () => Promise<string>;
  /** Called with each parsed event so the host app can invalidate queries. */
  readonly onShoulderTap: (event: ShoulderTapEvent) => void;
  /** Optional callback observed when the connection state changes. */
  readonly onStateChange?: (state: ShoulderTapState) => void;
  /** localStorage key used to persist the last seen timestamp. Defaults to `oz.realtime.lastEventTs`. */
  readonly storageKey?: string;
  /** Maximum reconnect delay, in ms. Defaults to 30_000. */
  readonly maxReconnectDelayMs?: number;
}

export type ShoulderTapState =
  | 'idle'
  | 'connecting'
  | 'open'
  | 'reconnecting'
  | 'closed';

const DEFAULT_STORAGE_KEY = 'oz.realtime.lastEventTs';
const DEFAULT_MAX_DELAY_MS = 30_000;
const BASE_DELAY_MS = 500;

interface TicketResponse {
  readonly ticket: string;
  readonly connect_url: string;
}

export class ShoulderTapClient {
  private socket: WebSocket | null = null;
  private state: ShoulderTapState = 'idle';
  private reconnectAttempts = 0;
  private reconnectHandle: ReturnType<typeof setTimeout> | null = null;
  private closed = false;

  constructor(private readonly cfg: ShoulderTapClientConfig) {}

  async connect(): Promise<void> {
    this.closed = false;
    this.setState('connecting');
    try {
      await this.openOnce();
    } catch (err) {
      this.scheduleReconnect();
      throw err;
    }
  }

  disconnect(): void {
    this.closed = true;
    this.clearReconnect();
    this.socket?.close();
    this.socket = null;
    this.setState('closed');
  }

  /** Topic the client wants the gateway to fan out. */
  subscribe(topic: string): void {
    this.socket?.readyState === WebSocket.OPEN &&
      this.socket.send(JSON.stringify({ subscribe: topic }));
  }

  unsubscribe(topic: string): void {
    this.socket?.readyState === WebSocket.OPEN &&
      this.socket.send(JSON.stringify({ unsubscribe: topic }));
  }

  getLastEventTimestamp(): string | null {
    return readStorage(this.storageKey());
  }

  private async openOnce(): Promise<void> {
    const after = readStorage(this.storageKey());
    const ticket = await this.fetchTicket(after);
    const wsUrl = buildWsUrl(this.cfg.gatewayUrl, ticket.connect_url);
    const socket = new WebSocket(wsUrl);

    this.socket = socket;
    socket.onopen = () => {
      this.reconnectAttempts = 0;
      this.setState('open');
    };
    socket.onmessage = (event) => {
      this.handleMessage(event.data);
    };
    socket.onerror = () => {
      /* fall through to onclose */
    };
    socket.onclose = () => {
      this.socket = null;
      if (this.closed) {
        return;
      }
      this.scheduleReconnect();
    };
  }

  private async fetchTicket(after: string | null): Promise<TicketResponse> {
    const token = await this.cfg.getAccessToken();
    const url = new URL(`${this.cfg.gatewayUrl}/ws/tickets`);
    if (after) {
      url.searchParams.set('after', after);
    }
    const res = await fetch(url.toString(), {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: 'application/json',
      },
    });
    if (!res.ok) {
      throw new Error(`shoulder-tap: ticket request failed (${res.status})`);
    }
    const body = (await res.json()) as TicketResponse;
    if (!body.ticket || !body.connect_url) {
      throw new Error('shoulder-tap: ticket response missing fields');
    }
    return body;
  }

  private handleMessage(raw: unknown): void {
    if (typeof raw !== 'string') {
      return;
    }
    let parsed: unknown;
    try {
      parsed = JSON.parse(raw);
    } catch {
      return;
    }
    if (!isShoulderTapEnvelope(parsed)) {
      return;
    }
    const tap: ShoulderTapEvent = {
      topic: parsed.topic,
      entityId: parsed.entity_id,
      action: parsed.action.toLowerCase(),
      table: tableFromTopic(parsed.topic),
      timestamp: parsed.ts,
    };
    writeStorage(this.storageKey(), parsed.ts);
    this.cfg.onShoulderTap(tap);
  }

  private scheduleReconnect(): void {
    if (this.closed) {
      return;
    }
    this.setState('reconnecting');
    const attempt = ++this.reconnectAttempts;
    const cap = this.cfg.maxReconnectDelayMs ?? DEFAULT_MAX_DELAY_MS;
    const base = Math.min(BASE_DELAY_MS * 2 ** Math.min(attempt, 6), cap);
    const delay = Math.random() * base;
    this.reconnectHandle = setTimeout(() => {
      this.reconnectHandle = null;
      this.openOnce().catch(() => this.scheduleReconnect());
    }, delay);
  }

  private clearReconnect(): void {
    if (this.reconnectHandle !== null) {
      clearTimeout(this.reconnectHandle);
      this.reconnectHandle = null;
    }
  }

  private setState(next: ShoulderTapState): void {
    if (this.state === next) {
      return;
    }
    this.state = next;
    this.cfg.onStateChange?.(next);
  }

  private storageKey(): string {
    return this.cfg.storageKey ?? DEFAULT_STORAGE_KEY;
  }
}

const isShoulderTapEnvelope = (value: unknown): value is ShoulderTapEnvelope => {
  if (typeof value !== 'object' || value === null) {
    return false;
  }
  const v = value as Record<string, unknown>;
  return (
    v.type === 'MUTATION' &&
    typeof v.topic === 'string' &&
    typeof v.entity_id === 'string' &&
    typeof v.action === 'string' &&
    typeof v.ts === 'string'
  );
};

/**
 * Derive a table name from a topic. Topics have the shape
 * `event.<workspace>.<service>.<aggregate_type>.<aggregate_id>.<action>`
 * (or shorter if the envelope uses the aggregate-level summary form
 * `event.<workspace>.<service>.<aggregate_type>`). We treat the
 * aggregate_type segment as the table, which is what TanStack Query
 * keys use throughout the data layer.
 */
const tableFromTopic = (topic: string): string => {
  const parts = topic.split('.');
  if (parts.length < 4 || parts[0] !== 'event') {
    return topic;
  }
  return parts[3];
};

const buildWsUrl = (gatewayUrl: string, connectPath: string): string => {
  const u = new URL(gatewayUrl);
  u.protocol = u.protocol === 'https:' ? 'wss:' : 'ws:';
  u.pathname = connectPath;
  u.search = '';
  return u.toString();
};

const readStorage = (key: string): string | null => {
  if (typeof window === 'undefined' || !window.localStorage) {
    return null;
  }
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
};

const writeStorage = (key: string, value: string): void => {
  if (typeof window === 'undefined' || !window.localStorage) {
    return;
  }
  try {
    window.localStorage.setItem(key, value);
  } catch {
    /* quota errors / private mode — swallow silently */
  }
};
