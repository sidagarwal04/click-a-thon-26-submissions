/**
 * Enterprise realtime protocol types and runtime schemas.
 *
 * @module types/realtime
 */

import { z } from 'zod';

import type { ValueOf } from './utility';

// =============================================================================
// Protocol constants
// =============================================================================

export const REALTIME_APPLY_STRATEGY = {
  PATCH_DETAIL: 'patch_detail',
  PATCH_LIST: 'patch_list',
  INVALIDATE: 'invalidate',
} as const;

export type RealtimeApplyStrategy =
  (typeof REALTIME_APPLY_STRATEGY)[keyof typeof REALTIME_APPLY_STRATEGY];

export const REALTIME_OWNERSHIP_STATE = {
  UNKNOWN: 'unknown',
  LEADER: 'leader',
  FOLLOWER: 'follower',
  STANDALONE: 'standalone',
} as const;

export type RealtimeOwnershipState =
  (typeof REALTIME_OWNERSHIP_STATE)[keyof typeof REALTIME_OWNERSHIP_STATE];

export const REALTIME_CONNECTION_STATE = {
  IDLE: 'idle',
  CONNECTING: 'connecting',
  HANDSHAKING: 'handshaking',
  READY: 'ready',
  RECONNECTING: 'reconnecting',
  CLOSED: 'closed',
  ERROR: 'error',
} as const;

export type RealtimeConnectionState =
  (typeof REALTIME_CONNECTION_STATE)[keyof typeof REALTIME_CONNECTION_STATE];

export const REALTIME_SUBSCRIPTION_STATE = {
  PENDING: 'pending',
  SUBSCRIBED: 'subscribed',
  UNSUBSCRIBED: 'unsubscribed',
  ERROR: 'error',
  RESYNC_REQUIRED: 'resync_required',
} as const;

export type RealtimeSubscriptionState =
  (typeof REALTIME_SUBSCRIPTION_STATE)[keyof typeof REALTIME_SUBSCRIPTION_STATE];

export const REALTIME_DATA_KIND = {
  CREATED: 'created',
  UPDATED: 'updated',
  DELETED: 'deleted',
  SNAPSHOT: 'snapshot',
} as const;

export type RealtimeDataKind = (typeof REALTIME_DATA_KIND)[keyof typeof REALTIME_DATA_KIND];

export const REALTIME_CLIENT_MESSAGE_TYPE = {
  HELLO: 'hello',
  RESUME: 'resume',
  SUBSCRIBE: 'subscribe',
  UNSUBSCRIBE: 'unsubscribe',
  ACK: 'ack',
  PING: 'ping',
  PONG: 'pong',
} as const;

export type RealtimeClientMessageType =
  (typeof REALTIME_CLIENT_MESSAGE_TYPE)[keyof typeof REALTIME_CLIENT_MESSAGE_TYPE];

export const REALTIME_SERVER_MESSAGE_TYPE = {
  HELLO_ACK: 'hello_ack',
  SUBSCRIBED: 'subscribed',
  UNSUBSCRIBED: 'unsubscribed',
  EVENT: 'event',
  SNAPSHOT: 'snapshot',
  RESYNC_REQUIRED: 'resync_required',
  ERROR: 'error',
  PING: 'ping',
  PONG: 'pong',
} as const;

export type RealtimeServerMessageType =
  (typeof REALTIME_SERVER_MESSAGE_TYPE)[keyof typeof REALTIME_SERVER_MESSAGE_TYPE];

// =============================================================================
// Shared schemas and types
// =============================================================================

const nonEmptyStringSchema = z.string().min(1);
const nonNegativeNumberSchema = z.number().min(0);
const nullableNonEmptyStringSchema = nonEmptyStringSchema.nullable();

export const realtimeTopicDescriptorSchema = z.object({
  topic: nonEmptyStringSchema,
  table: nonEmptyStringSchema,
});

export type RealtimeTopicDescriptor = z.infer<typeof realtimeTopicDescriptorSchema>;

export const realtimeTopicCursorSchema = z.object({
  topic: nonEmptyStringSchema,
  table: nonEmptyStringSchema,
  seq: z.number().int().nonnegative(),
  version: z.number().nullable().optional(),
  occurredAt: nonNegativeNumberSchema,
  updatedAt: nonNegativeNumberSchema,
});

export type RealtimeTopicCursor = z.infer<typeof realtimeTopicCursorSchema>;

export const realtimeCursorStoreSchema = z.record(nonEmptyStringSchema, realtimeTopicCursorSchema);

export type RealtimeCursorStore = z.infer<typeof realtimeCursorStoreSchema>;

export const realtimeConnectionSnapshotSchema = z.object({
  state: z.enum([
    REALTIME_CONNECTION_STATE.IDLE,
    REALTIME_CONNECTION_STATE.CONNECTING,
    REALTIME_CONNECTION_STATE.HANDSHAKING,
    REALTIME_CONNECTION_STATE.READY,
    REALTIME_CONNECTION_STATE.RECONNECTING,
    REALTIME_CONNECTION_STATE.CLOSED,
    REALTIME_CONNECTION_STATE.ERROR,
  ]),
  ownership: z.enum([
    REALTIME_OWNERSHIP_STATE.UNKNOWN,
    REALTIME_OWNERSHIP_STATE.LEADER,
    REALTIME_OWNERSHIP_STATE.FOLLOWER,
    REALTIME_OWNERSHIP_STATE.STANDALONE,
  ]),
  protocolVersion: z.string().nullable(),
  negotiatedProtocolVersion: z.string().nullable(),
  connectionId: z.string().nullable(),
  leaderTabId: z.string().nullable(),
  heartbeatIntervalMs: z.number().int().positive().nullable(),
  lastConnectedAt: z.number().nullable(),
  lastReadyAt: z.number().nullable(),
  updatedAt: nonNegativeNumberSchema,
  lastErrorCode: z.string().nullable().optional(),
  lastErrorMessage: z.string().nullable().optional(),
});

export type RealtimeConnectionSnapshot = z.infer<typeof realtimeConnectionSnapshotSchema>;

export const realtimeSubscriptionSnapshotSchema = z.object({
  topic: nonEmptyStringSchema,
  table: nonEmptyStringSchema,
  state: z.enum([
    REALTIME_SUBSCRIPTION_STATE.PENDING,
    REALTIME_SUBSCRIPTION_STATE.SUBSCRIBED,
    REALTIME_SUBSCRIPTION_STATE.UNSUBSCRIBED,
    REALTIME_SUBSCRIPTION_STATE.ERROR,
    REALTIME_SUBSCRIPTION_STATE.RESYNC_REQUIRED,
  ]),
  lastSeq: z.number().int().nonnegative().nullable(),
  lastVersion: z.number().nullable(),
  updatedAt: nonNegativeNumberSchema,
  errorCode: z.string().nullable().optional(),
  errorMessage: z.string().nullable().optional(),
});

export type RealtimeSubscriptionSnapshot = z.infer<typeof realtimeSubscriptionSnapshotSchema>;

export const realtimeSubscriptionMapSchema = z.record(
  nonEmptyStringSchema,
  realtimeSubscriptionSnapshotSchema,
);

export type RealtimeSubscriptionMap = z.infer<typeof realtimeSubscriptionMapSchema>;

// =============================================================================
// Client messages
// =============================================================================

const realtimeClientMessageBaseSchema = z.object({
  messageId: nonEmptyStringSchema,
  requestId: nonEmptyStringSchema.optional(),
});

export const realtimeHelloClientMessageSchema = realtimeClientMessageBaseSchema.extend({
  type: z.literal(REALTIME_CLIENT_MESSAGE_TYPE.HELLO),
  protocolVersion: nonEmptyStringSchema,
  clientInstanceId: nonEmptyStringSchema,
  capabilities: z.array(nonEmptyStringSchema).default([]),
  cursors: z.array(realtimeTopicCursorSchema).default([]),
});

export type RealtimeHelloClientMessage = z.infer<typeof realtimeHelloClientMessageSchema>;

export const realtimeResumeClientMessageSchema = realtimeClientMessageBaseSchema.extend({
  type: z.literal(REALTIME_CLIENT_MESSAGE_TYPE.RESUME),
  cursors: z.array(realtimeTopicCursorSchema).default([]),
});

export type RealtimeResumeClientMessage = z.infer<typeof realtimeResumeClientMessageSchema>;

export const realtimeSubscribeClientMessageSchema = realtimeClientMessageBaseSchema.extend({
  type: z.literal(REALTIME_CLIENT_MESSAGE_TYPE.SUBSCRIBE),
  topics: z.array(realtimeTopicDescriptorSchema).min(1),
});

export type RealtimeSubscribeClientMessage = z.infer<typeof realtimeSubscribeClientMessageSchema>;

export const realtimeUnsubscribeClientMessageSchema = realtimeClientMessageBaseSchema.extend({
  type: z.literal(REALTIME_CLIENT_MESSAGE_TYPE.UNSUBSCRIBE),
  topics: z.array(nonEmptyStringSchema).min(1),
});

export type RealtimeUnsubscribeClientMessage = z.infer<
  typeof realtimeUnsubscribeClientMessageSchema
>;

export const realtimeAckClientMessageSchema = realtimeClientMessageBaseSchema.extend({
  type: z.literal(REALTIME_CLIENT_MESSAGE_TYPE.ACK),
  receivedMessageId: nonEmptyStringSchema,
  receivedAt: nonNegativeNumberSchema,
});

export type RealtimeAckClientMessage = z.infer<typeof realtimeAckClientMessageSchema>;

export const realtimePingClientMessageSchema = realtimeClientMessageBaseSchema.extend({
  type: z.literal(REALTIME_CLIENT_MESSAGE_TYPE.PING),
  sentAt: nonNegativeNumberSchema,
});

export type RealtimePingClientMessage = z.infer<typeof realtimePingClientMessageSchema>;

export const realtimePongClientMessageSchema = realtimeClientMessageBaseSchema.extend({
  type: z.literal(REALTIME_CLIENT_MESSAGE_TYPE.PONG),
  replyingTo: nonEmptyStringSchema.optional(),
  sentAt: nonNegativeNumberSchema,
});

export type RealtimePongClientMessage = z.infer<typeof realtimePongClientMessageSchema>;

export const realtimeClientMessageSchema = z.discriminatedUnion('type', [
  realtimeHelloClientMessageSchema,
  realtimeResumeClientMessageSchema,
  realtimeSubscribeClientMessageSchema,
  realtimeUnsubscribeClientMessageSchema,
  realtimeAckClientMessageSchema,
  realtimePingClientMessageSchema,
  realtimePongClientMessageSchema,
]);

export type RealtimeClientMessage = z.infer<typeof realtimeClientMessageSchema>;

// =============================================================================
// Server messages
// =============================================================================

const realtimeServerMessageBaseSchema = z.object({
  messageId: nonEmptyStringSchema,
});

export const realtimeHelloAckServerMessageSchema = realtimeServerMessageBaseSchema.extend({
  type: z.literal(REALTIME_SERVER_MESSAGE_TYPE.HELLO_ACK),
  requestId: nonEmptyStringSchema.optional(),
  connectionId: nonEmptyStringSchema,
  protocolVersion: nonEmptyStringSchema,
  negotiatedProtocolVersion: nonEmptyStringSchema,
  heartbeatIntervalMs: z.number().int().positive(),
  capabilities: z.array(nonEmptyStringSchema).default([]),
  resumeAccepted: z.boolean(),
  serverTime: nonNegativeNumberSchema,
});

export type RealtimeHelloAckServerMessage = z.infer<typeof realtimeHelloAckServerMessageSchema>;

export const realtimeSubscribedServerMessageSchema = realtimeServerMessageBaseSchema.extend({
  type: z.literal(REALTIME_SERVER_MESSAGE_TYPE.SUBSCRIBED),
  requestId: nonEmptyStringSchema.optional(),
  topic: nonEmptyStringSchema,
  table: nonEmptyStringSchema,
  cursor: realtimeTopicCursorSchema.nullable().optional(),
});

export type RealtimeSubscribedServerMessage = z.infer<typeof realtimeSubscribedServerMessageSchema>;

export const realtimeUnsubscribedServerMessageSchema = realtimeServerMessageBaseSchema.extend({
  type: z.literal(REALTIME_SERVER_MESSAGE_TYPE.UNSUBSCRIBED),
  requestId: nonEmptyStringSchema.optional(),
  topic: nonEmptyStringSchema,
  table: nonEmptyStringSchema,
});

export type RealtimeUnsubscribedServerMessage = z.infer<
  typeof realtimeUnsubscribedServerMessageSchema
>;

const realtimeDataMessageBaseSchema = realtimeServerMessageBaseSchema.extend({
  topic: nonEmptyStringSchema,
  table: nonEmptyStringSchema,
  entityId: nullableNonEmptyStringSchema,
  seq: z.number().int().nonnegative(),
  occurredAt: nonNegativeNumberSchema,
  version: z.number().nullable().optional(),
  kind: z.enum([
    REALTIME_DATA_KIND.CREATED,
    REALTIME_DATA_KIND.UPDATED,
    REALTIME_DATA_KIND.DELETED,
    REALTIME_DATA_KIND.SNAPSHOT,
  ]),
});

export const realtimeEventServerMessageSchema = realtimeDataMessageBaseSchema.extend({
  type: z.literal(REALTIME_SERVER_MESSAGE_TYPE.EVENT),
  kind: z.enum([
    REALTIME_DATA_KIND.CREATED,
    REALTIME_DATA_KIND.UPDATED,
    REALTIME_DATA_KIND.DELETED,
  ]),
  payload: z.unknown().optional(),
});

export type RealtimeEventServerMessage = z.infer<typeof realtimeEventServerMessageSchema>;

export const realtimeSnapshotServerMessageSchema = realtimeDataMessageBaseSchema.extend({
  type: z.literal(REALTIME_SERVER_MESSAGE_TYPE.SNAPSHOT),
  entityId: z.null(),
  kind: z.literal(REALTIME_DATA_KIND.SNAPSHOT),
  payload: z.unknown(),
});

export type RealtimeSnapshotServerMessage = z.infer<typeof realtimeSnapshotServerMessageSchema>;

export const realtimeResyncRequiredServerMessageSchema = realtimeServerMessageBaseSchema.extend({
  type: z.literal(REALTIME_SERVER_MESSAGE_TYPE.RESYNC_REQUIRED),
  requestId: nonEmptyStringSchema.optional(),
  topic: nonEmptyStringSchema,
  table: nonEmptyStringSchema,
  expectedSeq: z.number().int().nonnegative().optional(),
  actualSeq: z.number().int().nonnegative().optional(),
  reason: nonEmptyStringSchema,
});

export type RealtimeResyncRequiredServerMessage = z.infer<
  typeof realtimeResyncRequiredServerMessageSchema
>;

export const realtimeErrorServerMessageSchema = realtimeServerMessageBaseSchema.extend({
  type: z.literal(REALTIME_SERVER_MESSAGE_TYPE.ERROR),
  requestId: nonEmptyStringSchema.optional(),
  code: nonEmptyStringSchema,
  message: nonEmptyStringSchema,
  recoverable: z.boolean(),
  topic: nonEmptyStringSchema.optional(),
  table: nonEmptyStringSchema.optional(),
});

export type RealtimeErrorServerMessage = z.infer<typeof realtimeErrorServerMessageSchema>;

export const realtimePingServerMessageSchema = realtimeServerMessageBaseSchema.extend({
  type: z.literal(REALTIME_SERVER_MESSAGE_TYPE.PING),
  requestId: nonEmptyStringSchema.optional(),
  sentAt: nonNegativeNumberSchema,
});

export type RealtimePingServerMessage = z.infer<typeof realtimePingServerMessageSchema>;

export const realtimePongServerMessageSchema = realtimeServerMessageBaseSchema.extend({
  type: z.literal(REALTIME_SERVER_MESSAGE_TYPE.PONG),
  requestId: nonEmptyStringSchema.optional(),
  replyingTo: nonEmptyStringSchema.optional(),
  sentAt: nonNegativeNumberSchema,
});

export type RealtimePongServerMessage = z.infer<typeof realtimePongServerMessageSchema>;

export const realtimeServerMessageSchema = z.discriminatedUnion('type', [
  realtimeHelloAckServerMessageSchema,
  realtimeSubscribedServerMessageSchema,
  realtimeUnsubscribedServerMessageSchema,
  realtimeEventServerMessageSchema,
  realtimeSnapshotServerMessageSchema,
  realtimeResyncRequiredServerMessageSchema,
  realtimeErrorServerMessageSchema,
  realtimePingServerMessageSchema,
  realtimePongServerMessageSchema,
]);

export type RealtimeServerMessage = z.infer<typeof realtimeServerMessageSchema>;

export type RealtimeDataServerMessage = RealtimeEventServerMessage | RealtimeSnapshotServerMessage;

export type RealtimeAckServerMessage =
  | RealtimeHelloAckServerMessage
  | RealtimeSubscribedServerMessage
  | RealtimeUnsubscribedServerMessage
  | RealtimePongServerMessage
  | RealtimeErrorServerMessage;

export const isRealtimeDataServerMessage = (
  message: RealtimeServerMessage,
): message is RealtimeDataServerMessage =>
  message.type === REALTIME_SERVER_MESSAGE_TYPE.EVENT ||
  message.type === REALTIME_SERVER_MESSAGE_TYPE.SNAPSHOT;

export const isRealtimeAckServerMessage = (
  message: RealtimeServerMessage,
): message is RealtimeAckServerMessage =>
  message.type === REALTIME_SERVER_MESSAGE_TYPE.HELLO_ACK ||
  message.type === REALTIME_SERVER_MESSAGE_TYPE.SUBSCRIBED ||
  message.type === REALTIME_SERVER_MESSAGE_TYPE.UNSUBSCRIBED ||
  message.type === REALTIME_SERVER_MESSAGE_TYPE.PONG ||
  message.type === REALTIME_SERVER_MESSAGE_TYPE.ERROR;

export const parseRealtimeClientMessage = (value: unknown): RealtimeClientMessage =>
  realtimeClientMessageSchema.parse(value);

export const parseRealtimeServerMessage = (value: unknown): RealtimeServerMessage =>
  realtimeServerMessageSchema.parse(value);

export const safeParseRealtimeClientMessage = (value: unknown) =>
  realtimeClientMessageSchema.safeParse(value);

export const safeParseRealtimeServerMessage = (value: unknown) =>
  realtimeServerMessageSchema.safeParse(value);

// =============================================================================
// Convenience types
// =============================================================================

export interface RealtimeRuntimeState {
  readonly connection: RealtimeConnectionSnapshot;
  readonly subscriptions: RealtimeSubscriptionMap;
  readonly lastMessage: RealtimeServerMessage | null;
}

export type RealtimeProtocolVersion = string;

export type RealtimeCapability = string;

export type RealtimeCapabilityMap = Record<string, boolean>;

export type RealtimeMessageId = string;

export type RealtimeRequestId = string;

export type RealtimeSchemaValue<TSchema extends z.ZodTypeAny> = z.infer<TSchema>;

export type RealtimeSchema = z.ZodTypeAny;

export type RealtimeDataMessageKind = ValueOf<typeof REALTIME_DATA_KIND>;
