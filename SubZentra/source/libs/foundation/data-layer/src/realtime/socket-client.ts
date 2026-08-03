import type { AxiosInstance } from 'axios';

import {
  REALTIME_CLIENT_MESSAGE_TYPE,
  REALTIME_CONNECTION_STATE,
  REALTIME_OWNERSHIP_STATE,
  REALTIME_SERVER_MESSAGE_TYPE,
  REALTIME_SUBSCRIPTION_STATE,
  safeParseRealtimeClientMessage,
  safeParseRealtimeServerMessage,
  type RealtimeAckServerMessage,
  type RealtimeClientMessage,
  type RealtimeConnectionSnapshot,
  type RealtimeCursorStore,
  type RealtimeDataServerMessage,
  type RealtimeErrorServerMessage,
  type RealtimeServerMessage,
  type RealtimeSubscriptionMap,
  type RealtimeSubscriptionSnapshot,
  type RealtimeTopicCursor,
  type RealtimeTopicDescriptor,
} from '@open-zentra/foundation-data-model';
import { createDebugLogger, SafeTimer, type Logger } from '@open-zentra/foundation-utils';

import { executeQueryDescriptor } from '../core/http-descriptor';
import type { RealtimeSocketConfig, RealtimeWebSocketTicket } from '../core/types';

export const REALTIME_SOCKET_STATUS = REALTIME_CONNECTION_STATE;

export type RealtimeSocketStatus =
  (typeof REALTIME_SOCKET_STATUS)[keyof typeof REALTIME_SOCKET_STATUS];

type ConnectionListener = (snapshot: RealtimeConnectionSnapshot) => void;
type SubscriptionListener = (subscriptions: RealtimeSubscriptionMap) => void;
type MessageListener = (message: RealtimeServerMessage) => void;

interface PendingRequest {
  readonly resolve: (message: RealtimeAckServerMessage) => void;
  readonly reject: (error: Error) => void;
  readonly timer: SafeTimer;
}

export interface RealtimeSocketClientDependencies {
  readonly axiosInstance: AxiosInstance;
  readonly syncState: {
    readonly getRealtimeCursors?: () => Promise<RealtimeCursorStore | undefined>;
    readonly setRealtimeCursors?: (value: RealtimeCursorStore) => Promise<void>;
  };
  readonly debug?: boolean;
}

const REQUEST_TIMEOUT_MS = 10_000;
const HEARTBEAT_INTERVAL_MS = 15_000;
const HEARTBEAT_TIMEOUT_MS = 45_000;
const RESUME_QUERY_PARAM = 'ticket';

const cloneSubscriptions = (value: RealtimeSubscriptionMap): RealtimeSubscriptionMap => ({
  ...value,
});

const resolveTopicKey = (topic: string, table: string): string => `${table}::${topic}`;

const buildCursorFromMessage = (message: RealtimeDataServerMessage): RealtimeTopicCursor => ({
  topic: message.topic,
  table: message.table,
  seq: message.seq,
  version: message.version ?? null,
  occurredAt: message.occurredAt,
  updatedAt: Date.now(),
});

const createInitialConnectionSnapshot = (
  config: RealtimeSocketConfig,
): RealtimeConnectionSnapshot => ({
  state: REALTIME_CONNECTION_STATE.IDLE,
  ownership:
    config.leaderMode === 'standalone'
      ? REALTIME_OWNERSHIP_STATE.STANDALONE
      : REALTIME_OWNERSHIP_STATE.UNKNOWN,
  protocolVersion: config.protocolVersion ?? '1.0',
  negotiatedProtocolVersion: null,
  connectionId: null,
  leaderTabId: null,
  heartbeatIntervalMs: null,
  lastConnectedAt: null,
  lastReadyAt: null,
  updatedAt: Date.now(),
  lastErrorCode: null,
  lastErrorMessage: null,
});

const resolveTicket = async (
  config: RealtimeSocketConfig,
  axiosInstance: AxiosInstance,
): Promise<RealtimeWebSocketTicket> => {
  const auth = config.auth;
  if (!auth) {
    throw new Error('Realtime websocket auth is required and must use ticket mode.');
  }

  if (auth.mode !== 'ticket') {
    throw new Error('Realtime websocket auth supports only ticket mode.');
  }

  const ticketValue =
    (await auth.getTicket?.()) ??
    (auth.ticketEndpoint
      ? await executeQueryDescriptor(axiosInstance, auth.ticketEndpoint, undefined as never)
      : null);

  if (!ticketValue) {
    throw new Error(
      'Realtime websocket ticket auth requires getTicket or ticketEndpoint to return a ticket.',
    );
  }

  if (typeof ticketValue === 'string') {
    return {
      ticket: ticketValue,
      queryParam: auth.queryParam ?? RESUME_QUERY_PARAM,
    };
  }

  return {
    ...ticketValue,
    queryParam: ticketValue.queryParam ?? auth.queryParam ?? RESUME_QUERY_PARAM,
  };
};

const resolveSocketUrl = async (
  config: RealtimeSocketConfig,
  axiosInstance: AxiosInstance,
): Promise<{ readonly url: string; readonly protocols: string[] | undefined }> => {
  const ticket = await resolveTicket(config, axiosInstance);
  const baseUrl = ticket.url ?? config.url;

  const url = new URL(baseUrl);
  url.searchParams.set(ticket.queryParam ?? RESUME_QUERY_PARAM, ticket.ticket);

  return {
    url: url.toString(),
    protocols: ticket.protocols ?? config.protocols,
  };
};

const createSubscriptionSnapshot = (
  topic: string,
  table: string,
  state: RealtimeSubscriptionSnapshot['state'],
): RealtimeSubscriptionSnapshot => ({
  topic,
  table,
  state,
  lastSeq: null,
  lastVersion: null,
  updatedAt: Date.now(),
  errorCode: null,
  errorMessage: null,
});

const parseIncomingRealtimeMessage = (value: unknown) => {
  if (typeof value === 'string') {
    try {
      return safeParseRealtimeServerMessage(JSON.parse(value));
    } catch (error) {
      return {
        success: false as const,
        error: error instanceof Error ? error : new Error(String(error)),
      };
    }
  }

  return safeParseRealtimeServerMessage(value);
};

export class RealtimeSocketClient {
  private socket: WebSocket | null = null;
  private readonly config: RealtimeSocketConfig;
  private readonly deps: RealtimeSocketClientDependencies;
  private readonly logger: Logger;
  private connectionSnapshot: RealtimeConnectionSnapshot;
  private subscriptionMap: RealtimeSubscriptionMap = {};
  private cursorStore: RealtimeCursorStore = {};
  private lastMessage: RealtimeServerMessage | null = null;
  private readonly connectionListeners = new Set<ConnectionListener>();
  private readonly subscriptionListeners = new Set<SubscriptionListener>();
  private readonly messageListeners = new Set<MessageListener>();
  private readonly pendingRequests = new Map<string, PendingRequest>();
  private readonly desiredTopics = new Map<string, RealtimeTopicDescriptor>();
  private reconnectAttempts = 0;
  private reconnectTimer: SafeTimer | null = null;
  private heartbeatIntervalTimer: SafeTimer | null = null;
  private heartbeatTimeoutTimer: SafeTimer | null = null;
  private activeConnectPromise: Promise<void> | null = null;
  private manuallyClosed = false;
  private readonly clientInstanceId = crypto.randomUUID();

  constructor(config: RealtimeSocketConfig, deps: RealtimeSocketClientDependencies) {
    this.config = config;
    this.deps = deps;
    this.logger = createDebugLogger('RealtimeSocketClient', deps.debug ?? false);
    this.connectionSnapshot = createInitialConnectionSnapshot(config);
  }

  getConnectionSnapshot(): RealtimeConnectionSnapshot {
    return this.connectionSnapshot;
  }

  getStatus(): RealtimeSocketStatus {
    return this.connectionSnapshot.state;
  }

  getSubscriptions(): RealtimeSubscriptionMap {
    return cloneSubscriptions(this.subscriptionMap);
  }

  getCursorStore(): RealtimeCursorStore {
    return { ...this.cursorStore };
  }

  async clearResumeState(): Promise<void> {
    this.cursorStore = {};
    await this.deps.syncState.setRealtimeCursors?.({});
  }

  getLastMessage(): RealtimeServerMessage | null {
    return this.lastMessage;
  }

  subscribeConnection(listener: ConnectionListener): () => void {
    this.connectionListeners.add(listener);
    listener(this.connectionSnapshot);
    return () => {
      this.connectionListeners.delete(listener);
    };
  }

  subscribeStatus(listener: (status: RealtimeSocketStatus) => void): () => void {
    return this.subscribeConnection((snapshot) => {
      listener(snapshot.state);
    });
  }

  subscribeSubscriptions(listener: SubscriptionListener): () => void {
    this.subscriptionListeners.add(listener);
    listener(cloneSubscriptions(this.subscriptionMap));
    return () => {
      this.subscriptionListeners.delete(listener);
    };
  }

  subscribeMessages(listener: MessageListener): () => void {
    this.messageListeners.add(listener);
    return () => {
      this.messageListeners.delete(listener);
    };
  }

  setOwnership(
    ownership: RealtimeConnectionSnapshot['ownership'],
    leaderTabId: string | null,
  ): void {
    this.updateConnectionSnapshot({
      ownership,
      leaderTabId,
    });
  }

  ingestConnectionSnapshot(snapshot: RealtimeConnectionSnapshot): void {
    this.connectionSnapshot = snapshot;
    this.notifyConnectionListeners();
  }

  ingestSubscriptionSnapshot(snapshot: RealtimeSubscriptionSnapshot): void {
    this.subscriptionMap = {
      ...this.subscriptionMap,
      [resolveTopicKey(snapshot.topic, snapshot.table)]: snapshot,
    };
    this.notifySubscriptionListeners();
  }

  ingestServerMessage(message: RealtimeServerMessage): void {
    this.handleIncomingMessage(message, false);
  }

  registerTopics(topics: readonly RealtimeTopicDescriptor[]): void {
    this.desiredTopics.clear();
    for (const topic of topics) {
      this.desiredTopics.set(resolveTopicKey(topic.topic, topic.table), topic);
      if (!this.subscriptionMap[resolveTopicKey(topic.topic, topic.table)]) {
        this.subscriptionMap[resolveTopicKey(topic.topic, topic.table)] =
          createSubscriptionSnapshot(
            topic.topic,
            topic.table,
            REALTIME_SUBSCRIPTION_STATE.UNSUBSCRIBED,
          );
      }
    }
    this.notifySubscriptionListeners();
  }

  async connect(): Promise<void> {
    if (
      this.socket &&
      (this.socket.readyState === WebSocket.OPEN || this.socket.readyState === WebSocket.CONNECTING)
    ) {
      return this.activeConnectPromise ?? Promise.resolve();
    }

    if (this.activeConnectPromise) {
      return this.activeConnectPromise;
    }

    this.manuallyClosed = false;
    this.activeConnectPromise = this.doConnect().finally(() => {
      this.activeConnectPromise = null;
    });

    return this.activeConnectPromise;
  }

  disconnect(): void {
    this.manuallyClosed = true;
    this.clearReconnectTimer();
    this.clearHeartbeatTimers();
    this.rejectPendingRequests(new Error('Realtime socket disconnected'));
    this.socket?.close();
    this.socket = null;
    this.updateConnectionSnapshot({
      state: REALTIME_CONNECTION_STATE.CLOSED,
      connectionId: null,
      lastErrorCode: null,
      lastErrorMessage: null,
    });
  }

  async send(message: RealtimeClientMessage): Promise<RealtimeAckServerMessage> {
    const parsed = safeParseRealtimeClientMessage(message);
    if (!parsed.success) {
      throw parsed.error;
    }

    const requestId = parsed.data.requestId;
    if (!requestId) {
      throw new Error(`Realtime message "${parsed.data.type}" requires requestId for send()`);
    }

    return this.sendWithAck(parsed.data);
  }

  async ensureSubscriptions(
    topics: readonly RealtimeTopicDescriptor[],
  ): Promise<ReadonlyArray<RealtimeSubscriptionSnapshot>> {
    this.registerTopics(topics);
    if (this.connectionSnapshot.state !== REALTIME_CONNECTION_STATE.READY) {
      return Object.values(this.subscriptionMap);
    }

    const results = await Promise.all(
      topics.map((topic) =>
        this.sendWithAck({
          type: REALTIME_CLIENT_MESSAGE_TYPE.SUBSCRIBE,
          messageId: crypto.randomUUID(),
          requestId: crypto.randomUUID(),
          topics: [topic],
        }),
      ),
    );

    return results
      .filter((message) => message.type === REALTIME_SERVER_MESSAGE_TYPE.SUBSCRIBED)
      .map((message) => {
        const key = resolveTopicKey(message.topic, message.table);
        return this.subscriptionMap[key];
      })
      .filter((value): value is RealtimeSubscriptionSnapshot => value !== undefined);
  }

  private async doConnect(): Promise<void> {
    this.cursorStore = (await this.deps.syncState.getRealtimeCursors?.()) ?? {};

    this.updateConnectionSnapshot({
      state:
        this.connectionSnapshot.state === REALTIME_CONNECTION_STATE.READY ||
        this.connectionSnapshot.state === REALTIME_CONNECTION_STATE.RECONNECTING
          ? REALTIME_CONNECTION_STATE.RECONNECTING
          : REALTIME_CONNECTION_STATE.CONNECTING,
      lastErrorCode: null,
      lastErrorMessage: null,
    });

    const { url, protocols } = await resolveSocketUrl(this.config, this.deps.axiosInstance);
    const socket = new WebSocket(url, protocols);
    this.socket = socket;

    await new Promise<void>((resolve, reject) => {
      let handshakeResolved = false;

      const cleanup = () => {
        socket.removeEventListener('open', handleOpen);
        socket.removeEventListener('message', handleMessage);
        socket.removeEventListener('error', handleError);
        socket.removeEventListener('close', handleCloseBeforeReady);
      };

      const handleOpen = () => {
        this.reconnectAttempts = 0;
        this.updateConnectionSnapshot({
          state: REALTIME_CONNECTION_STATE.HANDSHAKING,
          lastConnectedAt: Date.now(),
        });
        void this.sendHello()
          .then(() => {
            handshakeResolved = true;
            cleanup();
            this.attachReadySocketListeners(socket);
            resolve();
          })
          .catch((error) => {
            cleanup();
            reject(error);
          });
      };

      const handleMessage = (event: MessageEvent<unknown>) => {
        const parsed = parseIncomingRealtimeMessage(event.data);
        if (!parsed.success) {
          this.handleProtocolError('REALTIME_PROTOCOL_VALIDATION_FAILED', parsed.error.message);
          cleanup();
          reject(parsed.error);
          return;
        }

        this.handleIncomingMessage(parsed.data, true);
      };

      const handleError = () => {
        if (!handshakeResolved) {
          cleanup();
          reject(new Error('Realtime socket handshake failed'));
        }
      };

      const handleCloseBeforeReady = () => {
        if (!handshakeResolved) {
          cleanup();
          reject(new Error('Realtime socket closed before ready'));
        }
      };

      socket.addEventListener('open', handleOpen);
      socket.addEventListener('message', handleMessage);
      socket.addEventListener('error', handleError);
      socket.addEventListener('close', handleCloseBeforeReady);
    });
  }

  private attachReadySocketListeners(socket: WebSocket): void {
    socket.addEventListener('message', (event) => {
      const parsed = parseIncomingRealtimeMessage(event.data);
      if (!parsed.success) {
        this.handleProtocolError('REALTIME_PROTOCOL_VALIDATION_FAILED', parsed.error.message);
        return;
      }

      this.handleIncomingMessage(parsed.data, true);
    });

    socket.addEventListener('error', () => {
      this.updateConnectionSnapshot({
        state: REALTIME_CONNECTION_STATE.ERROR,
        lastErrorCode: 'REALTIME_PROTOCOL_VALIDATION_FAILED',
        lastErrorMessage: 'Realtime socket encountered an error',
      });
    });

    socket.addEventListener('close', () => {
      this.socket = null;
      this.clearHeartbeatTimers();
      this.rejectPendingRequests(new Error('Realtime socket closed'));
      this.updateConnectionSnapshot({
        state: REALTIME_CONNECTION_STATE.CLOSED,
        connectionId: null,
      });
      if (!this.manuallyClosed) {
        this.scheduleReconnect();
      }
    });
  }

  private async sendHello(): Promise<void> {
    const helloAck = await this.sendWithAck({
      type: REALTIME_CLIENT_MESSAGE_TYPE.HELLO,
      messageId: crypto.randomUUID(),
      requestId: crypto.randomUUID(),
      protocolVersion: this.config.protocolVersion ?? '1.0',
      clientInstanceId: this.clientInstanceId,
      capabilities: ['resume', 'heartbeat', 'subscriptions'],
      cursors: Object.values(this.cursorStore),
    });

    if (helloAck.type === REALTIME_SERVER_MESSAGE_TYPE.ERROR) {
      throw new Error(helloAck.message);
    }

    if (helloAck.type !== REALTIME_SERVER_MESSAGE_TYPE.HELLO_ACK) {
      throw new Error(`Unexpected hello response: ${helloAck.type}`);
    }

    if (
      this.config.resume?.enabled !== false &&
      helloAck.resumeAccepted &&
      Object.keys(this.cursorStore).length > 0
    ) {
      this.sendFireAndForget({
        type: REALTIME_CLIENT_MESSAGE_TYPE.RESUME,
        messageId: crypto.randomUUID(),
        requestId: crypto.randomUUID(),
        cursors: Object.values(this.cursorStore),
      });
    }

    this.startHeartbeat(helloAck.heartbeatIntervalMs);
    if (this.desiredTopics.size > 0) {
      await this.ensureSubscriptions([...this.desiredTopics.values()]);
    }
  }

  private sendWithAck(message: RealtimeClientMessage): Promise<RealtimeAckServerMessage> {
    const requestId = message.requestId;
    if (!requestId) {
      throw new Error('requestId is required for sendWithAck');
    }

    if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
      throw new Error('Realtime socket is not open');
    }

    return new Promise<RealtimeAckServerMessage>((resolve, reject) => {
      const timer = new SafeTimer({
        delay: this.config.requestTimeoutMs ?? REQUEST_TIMEOUT_MS,
        callback: () => {
          this.pendingRequests.delete(requestId);
          reject(new Error(`Realtime request timed out: ${message.type}`));
        },
        autoStart: true,
      });

      this.pendingRequests.set(requestId, {
        resolve,
        reject,
        timer,
      });

      this.socket?.send(JSON.stringify(message));
    });
  }

  private sendFireAndForget(message: RealtimeClientMessage): void {
    const parsed = safeParseRealtimeClientMessage(message);
    if (!parsed.success) {
      throw parsed.error;
    }

    if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
      throw new Error('Realtime socket is not open');
    }

    this.socket.send(JSON.stringify(parsed.data));
  }

  private handleIncomingMessage(message: RealtimeServerMessage, fromSocket: boolean): void {
    if (fromSocket) {
      this.resetHeartbeatTimeout();
    }

    this.lastMessage = message;

    switch (message.type) {
      case REALTIME_SERVER_MESSAGE_TYPE.HELLO_ACK:
        this.updateConnectionSnapshot({
          state: REALTIME_CONNECTION_STATE.READY,
          connectionId: message.connectionId,
          negotiatedProtocolVersion: message.negotiatedProtocolVersion,
          heartbeatIntervalMs: message.heartbeatIntervalMs,
          lastReadyAt: Date.now(),
          lastErrorCode: null,
          lastErrorMessage: null,
        });
        this.resolvePendingRequest(message.requestId, message);
        break;

      case REALTIME_SERVER_MESSAGE_TYPE.SUBSCRIBED: {
        const key = resolveTopicKey(message.topic, message.table);
        const current = this.subscriptionMap[key];
        this.subscriptionMap = {
          ...this.subscriptionMap,
          [key]: {
            topic: message.topic,
            table: message.table,
            state: REALTIME_SUBSCRIPTION_STATE.SUBSCRIBED,
            lastSeq: message.cursor?.seq ?? current?.lastSeq ?? null,
            lastVersion: message.cursor?.version ?? current?.lastVersion ?? null,
            updatedAt: Date.now(),
            errorCode: null,
            errorMessage: null,
          },
        };
        this.notifySubscriptionListeners();
        this.resolvePendingRequest(message.requestId, message);
        break;
      }

      case REALTIME_SERVER_MESSAGE_TYPE.UNSUBSCRIBED: {
        const key = resolveTopicKey(message.topic, message.table);
        this.subscriptionMap = {
          ...this.subscriptionMap,
          [key]: {
            topic: message.topic,
            table: message.table,
            state: REALTIME_SUBSCRIPTION_STATE.UNSUBSCRIBED,
            lastSeq: this.subscriptionMap[key]?.lastSeq ?? null,
            lastVersion: this.subscriptionMap[key]?.lastVersion ?? null,
            updatedAt: Date.now(),
            errorCode: null,
            errorMessage: null,
          },
        };
        this.notifySubscriptionListeners();
        this.resolvePendingRequest(message.requestId, message);
        break;
      }

      case REALTIME_SERVER_MESSAGE_TYPE.EVENT:
      case REALTIME_SERVER_MESSAGE_TYPE.SNAPSHOT:
        if (this.handleDataMessageOrdering(message)) {
          return;
        }
        this.recordCursor(message);
        if (fromSocket) {
          this.sendFireAndForget({
            type: REALTIME_CLIENT_MESSAGE_TYPE.ACK,
            messageId: crypto.randomUUID(),
            receivedMessageId: message.messageId,
            receivedAt: Date.now(),
          });
        }
        break;

      case REALTIME_SERVER_MESSAGE_TYPE.RESYNC_REQUIRED: {
        const key = resolveTopicKey(message.topic, message.table);
        this.subscriptionMap = {
          ...this.subscriptionMap,
          [key]: {
            topic: message.topic,
            table: message.table,
            state: REALTIME_SUBSCRIPTION_STATE.RESYNC_REQUIRED,
            lastSeq: this.subscriptionMap[key]?.lastSeq ?? null,
            lastVersion: this.subscriptionMap[key]?.lastVersion ?? null,
            updatedAt: Date.now(),
            errorCode: 'REALTIME_RESYNC_REQUIRED',
            errorMessage: message.reason,
          },
        };
        this.notifySubscriptionListeners();
        break;
      }

      case REALTIME_SERVER_MESSAGE_TYPE.ERROR:
        this.applyErrorMessage(message);
        this.resolvePendingRequest(message.requestId, message);
        break;

      case REALTIME_SERVER_MESSAGE_TYPE.PING:
        if (fromSocket) {
          this.sendFireAndForget({
            type: REALTIME_CLIENT_MESSAGE_TYPE.PONG,
            messageId: crypto.randomUUID(),
            requestId: message.requestId,
            replyingTo: message.messageId,
            sentAt: Date.now(),
          });
        }
        break;

      case REALTIME_SERVER_MESSAGE_TYPE.PONG:
        this.resolvePendingRequest(message.requestId, message);
        break;
    }

    this.messageListeners.forEach((listener) => listener(message));
  }

  private applyErrorMessage(message: RealtimeErrorServerMessage): void {
    if (message.topic && message.table) {
      const key = resolveTopicKey(message.topic, message.table);
      this.subscriptionMap = {
        ...this.subscriptionMap,
        [key]: {
          topic: message.topic,
          table: message.table,
          state: REALTIME_SUBSCRIPTION_STATE.ERROR,
          lastSeq: this.subscriptionMap[key]?.lastSeq ?? null,
          lastVersion: this.subscriptionMap[key]?.lastVersion ?? null,
          updatedAt: Date.now(),
          errorCode: message.code,
          errorMessage: message.message,
        },
      };
      this.notifySubscriptionListeners();
    }

    this.updateConnectionSnapshot({
      lastErrorCode: message.code,
      lastErrorMessage: message.message,
    });
  }

  private resolvePendingRequest(
    requestId: string | undefined,
    message: RealtimeAckServerMessage,
  ): void {
    if (!requestId) {
      return;
    }

    const pending = this.pendingRequests.get(requestId);
    if (!pending) {
      return;
    }

    pending.timer.dispose();
    this.pendingRequests.delete(requestId);
    pending.resolve(message);
  }

  private rejectPendingRequests(error: Error): void {
    for (const [requestId, pending] of this.pendingRequests.entries()) {
      pending.timer.dispose();
      pending.reject(error);
      this.pendingRequests.delete(requestId);
    }
  }

  private recordCursor(message: RealtimeDataServerMessage): void {
    const key = resolveTopicKey(message.topic, message.table);
    const previous = this.cursorStore[key];
    if (previous && previous.seq >= message.seq) {
      return;
    }

    const cursor = buildCursorFromMessage(message);
    this.cursorStore = {
      ...this.cursorStore,
      [key]: cursor,
    };

    const currentSubscription = this.subscriptionMap[key];
    if (currentSubscription) {
      this.subscriptionMap = {
        ...this.subscriptionMap,
        [key]: {
          ...currentSubscription,
          lastSeq: cursor.seq,
          lastVersion: cursor.version ?? null,
          updatedAt: Date.now(),
        },
      };
      this.notifySubscriptionListeners();
    }

    if (this.config.resume?.persistCursors !== false) {
      void this.deps.syncState.setRealtimeCursors?.(this.cursorStore);
    }
  }

  private handleDataMessageOrdering(message: RealtimeDataServerMessage): boolean {
    const key = resolveTopicKey(message.topic, message.table);
    const previous = this.cursorStore[key];
    if (!previous) {
      return false;
    }

    if (message.seq <= previous.seq) {
      this.logger.debug('Ignoring duplicate or stale realtime message', message.topic, message.seq);
      return true;
    }

    if (message.seq > previous.seq + 1) {
      this.subscriptionMap = {
        ...this.subscriptionMap,
        [key]: {
          topic: message.topic,
          table: message.table,
          state: REALTIME_SUBSCRIPTION_STATE.RESYNC_REQUIRED,
          lastSeq: previous.seq,
          lastVersion: previous.version ?? null,
          updatedAt: Date.now(),
          errorCode: 'REALTIME_RESYNC_REQUIRED',
          errorMessage: `Gap detected in realtime stream at sequence ${message.seq}`,
        },
      };
      this.notifySubscriptionListeners();

      const resyncMessage: RealtimeServerMessage = {
        type: REALTIME_SERVER_MESSAGE_TYPE.RESYNC_REQUIRED,
        messageId: `gap-${crypto.randomUUID()}`,
        topic: message.topic,
        table: message.table,
        expectedSeq: previous.seq + 1,
        actualSeq: message.seq,
        reason: `Gap detected in realtime stream at sequence ${message.seq}`,
      };
      this.lastMessage = resyncMessage;
      this.messageListeners.forEach((listener) => listener(resyncMessage));
      return true;
    }

    return false;
  }

  private startHeartbeat(serverIntervalMs: number): void {
    this.clearHeartbeatTimers();

    if (this.config.heartbeat?.enabled === false) {
      return;
    }

    const intervalMs =
      this.config.heartbeat?.intervalMs ?? serverIntervalMs ?? HEARTBEAT_INTERVAL_MS;
    const timeoutMs = this.config.heartbeat?.timeoutMs ?? HEARTBEAT_TIMEOUT_MS;

    const schedulePing = () => {
      this.heartbeatIntervalTimer?.dispose();
      this.heartbeatIntervalTimer = new SafeTimer({
        delay: intervalMs,
        autoStart: true,
        callback: () => {
          if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
            return;
          }

          void this.sendWithAck({
            type: REALTIME_CLIENT_MESSAGE_TYPE.PING,
            messageId: crypto.randomUUID(),
            requestId: crypto.randomUUID(),
            sentAt: Date.now(),
          }).catch((error) => {
            this.handleProtocolError('REALTIME_HEARTBEAT_TIMEOUT', error.message);
          });

          schedulePing();
        },
      });
    };

    this.heartbeatTimeoutTimer = new SafeTimer({
      delay: timeoutMs,
      autoStart: true,
      callback: () => {
        this.handleProtocolError('REALTIME_HEARTBEAT_TIMEOUT', 'Realtime heartbeat timed out');
      },
    });

    schedulePing();
  }

  private resetHeartbeatTimeout(): void {
    if (!this.heartbeatTimeoutTimer) {
      return;
    }

    this.heartbeatTimeoutTimer.restart();
  }

  private clearHeartbeatTimers(): void {
    this.heartbeatIntervalTimer?.dispose();
    this.heartbeatTimeoutTimer?.dispose();
    this.heartbeatIntervalTimer = null;
    this.heartbeatTimeoutTimer = null;
  }

  private scheduleReconnect(): void {
    const reconnect = this.config.reconnect;
    if (reconnect?.enabled === false) {
      return;
    }

    const maxAttempts = reconnect?.maxAttempts ?? Infinity;
    if (this.reconnectAttempts >= maxAttempts) {
      return;
    }

    const initialDelayMs = reconnect?.initialDelayMs ?? 1_000;
    const maxDelayMs = reconnect?.maxDelayMs ?? 30_000;
    const delay = Math.min(initialDelayMs * 2 ** this.reconnectAttempts, maxDelayMs);
    this.reconnectAttempts += 1;

    this.updateConnectionSnapshot({
      state: REALTIME_CONNECTION_STATE.RECONNECTING,
    });

    this.reconnectTimer = new SafeTimer({
      delay,
      autoStart: true,
      callback: () => {
        this.reconnectTimer = null;
        void this.connect().catch((error) => {
          this.logger.warn('Reconnect failed', error);
        });
      },
    });
  }

  private clearReconnectTimer(): void {
    this.reconnectTimer?.dispose();
    this.reconnectTimer = null;
  }

  private handleProtocolError(code: string, message: string): void {
    this.updateConnectionSnapshot({
      state: REALTIME_CONNECTION_STATE.ERROR,
      lastErrorCode: code,
      lastErrorMessage: message,
    });
    this.socket?.close();
  }

  private updateConnectionSnapshot(partial: Partial<RealtimeConnectionSnapshot>): void {
    this.connectionSnapshot = {
      ...this.connectionSnapshot,
      ...partial,
      updatedAt: Date.now(),
    };
    this.notifyConnectionListeners();
  }

  private notifyConnectionListeners(): void {
    this.connectionListeners.forEach((listener) => listener(this.connectionSnapshot));
  }

  private notifySubscriptionListeners(): void {
    const snapshot = cloneSubscriptions(this.subscriptionMap);
    this.subscriptionListeners.forEach((listener) => listener(snapshot));
  }
}
