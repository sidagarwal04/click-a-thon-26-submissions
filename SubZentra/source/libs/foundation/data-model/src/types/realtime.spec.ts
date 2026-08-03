import { describe, expect, it } from 'vitest';

import {
  REALTIME_CLIENT_MESSAGE_TYPE,
  REALTIME_SERVER_MESSAGE_TYPE,
  safeParseRealtimeClientMessage,
  safeParseRealtimeServerMessage,
} from './realtime';

describe('realtime protocol schemas', () => {
  it('validates a hello client message', () => {
    const result = safeParseRealtimeClientMessage({
      type: REALTIME_CLIENT_MESSAGE_TYPE.HELLO,
      messageId: 'msg_1',
      requestId: 'req_1',
      protocolVersion: '1.0',
      clientInstanceId: 'client_1',
      capabilities: ['resume'],
      cursors: [],
    });

    expect(result.success).toBe(true);
  });

  it('rejects malformed client messages', () => {
    const result = safeParseRealtimeClientMessage({
      type: REALTIME_CLIENT_MESSAGE_TYPE.SUBSCRIBE,
      messageId: 'msg_1',
    });

    expect(result.success).toBe(false);
  });

  it('validates event server messages with required sequencing fields', () => {
    const result = safeParseRealtimeServerMessage({
      type: REALTIME_SERVER_MESSAGE_TYPE.EVENT,
      messageId: 'msg_2',
      topic: 'events',
      table: 'events',
      entityId: 'evt_1',
      seq: 1,
      occurredAt: Date.now(),
      version: 2,
      kind: 'updated',
      payload: { id: 'evt_1', version: 2 },
    });

    expect(result.success).toBe(true);
  });

  it('rejects server data messages that are missing sequencing fields', () => {
    const result = safeParseRealtimeServerMessage({
      type: REALTIME_SERVER_MESSAGE_TYPE.EVENT,
      messageId: 'msg_3',
      topic: 'events',
      table: 'events',
      entityId: 'evt_1',
      kind: 'updated',
      payload: { id: 'evt_1' },
    });

    expect(result.success).toBe(false);
  });
});
