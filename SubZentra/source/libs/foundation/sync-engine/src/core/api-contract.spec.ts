import { describe, expect, it } from 'vitest';

import { OPERATIONS } from '@open-zentra/foundation-data-model';

import { NETWORK_STATUS_EVENT } from '../network/index';
import { SyncEngineContainer, SyncEngineFactory } from './container';

describe('sync-engine api contract', () => {
  it('removes deprecated synchronous disposal APIs', () => {
    expect('dispose' in SyncEngineContainer.prototype).toBe(false);
    expect('disposeContainer' in SyncEngineFactory.prototype).toBe(false);
    expect('disposeAll' in SyncEngineFactory.prototype).toBe(false);
  });

  it('exports UPPER_SNAKE_CASE network status event constants', () => {
    expect(NETWORK_STATUS_EVENT.ONLINE).toBe('online');
    expect(NETWORK_STATUS_EVENT.OFFLINE).toBe('offline');
    expect(NETWORK_STATUS_EVENT.CONNECTIVITY_CHECK).toBe('connectivity_check');
  });

  it('exports UPPER_SNAKE_CASE CRUD operation constants', () => {
    expect(OPERATIONS.LIST).toBe('list');
    expect(OPERATIONS.GET).toBe('get');
    expect(OPERATIONS.CREATE).toBe('create');
    expect(OPERATIONS.UPDATE).toBe('update');
    expect(OPERATIONS.DELETE).toBe('delete');
  });
});
