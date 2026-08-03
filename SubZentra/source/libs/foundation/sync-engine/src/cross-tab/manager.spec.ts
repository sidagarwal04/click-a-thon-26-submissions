import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import { CROSS_TAB_MESSAGE_TYPE } from '@open-zentra/foundation-data-model';

import { CrossTabManager } from './manager';

class FakeBroadcastChannel {
  static instances: FakeBroadcastChannel[] = [];
  static closeCount = 0;

  readonly name: string;
  onmessage: ((event: MessageEvent<unknown>) => void) | null = null;

  constructor(name: string) {
    this.name = name;
    FakeBroadcastChannel.instances.push(this);
  }

  postMessage(_value: unknown): void {
    // no-op for tests
  }

  close(): void {
    FakeBroadcastChannel.closeCount += 1;
  }
}

describe('CrossTabManager', () => {
  const originalBroadcastChannel = globalThis.BroadcastChannel;

  beforeEach(() => {
    FakeBroadcastChannel.instances = [];
    FakeBroadcastChannel.closeCount = 0;
    globalThis.BroadcastChannel = FakeBroadcastChannel as unknown as typeof BroadcastChannel;
  });

  afterEach(() => {
    globalThis.BroadcastChannel = originalBroadcastChannel;
  });

  it('closes channel on stop and reopens cleanly on restart', () => {
    const manager = new CrossTabManager({ debug: false });

    manager.start();
    expect(FakeBroadcastChannel.instances.length).toBe(1);

    manager.stop();
    expect(FakeBroadcastChannel.closeCount).toBe(1);

    manager.start();
    expect(FakeBroadcastChannel.instances.length).toBe(2);

    manager.stop();
    expect(FakeBroadcastChannel.closeCount).toBe(2);
    manager.dispose();
  });

  it('steps down on higher-term heartbeat from another leader', () => {
    const manager = new CrossTabManager({ debug: false });
    manager.start();

    const managerWithInternals = manager as unknown as {
      becomeLeader: (term: number) => void;
      handleMessage: (event: MessageEvent<unknown>) => void;
    };

    managerWithInternals.becomeLeader(1);
    expect(manager.isLeader).toBe(true);

    managerWithInternals.handleMessage({
      data: {
        type: CROSS_TAB_MESSAGE_TYPE.LEADER_HEARTBEAT,
        tabId: 'remote-tab',
        timestamp: Date.now(),
        payload: {
          leaderId: 'remote-tab',
          term: 2,
        },
      },
    } as MessageEvent<unknown>);

    expect(manager.isLeader).toBe(false);

    manager.stop();
    manager.dispose();
  });
});
