/**
 * Tests for OPFS metadata service.
 */

import { describe, expect, it, vi } from 'vitest';

import { OPFS_FILE_TYPE } from '@open-zentra/foundation-data-model';

import type { DatabaseConfig } from '../core/config';
import { OpfsMetadataService } from './opfs-metadata';

describe('OpfsMetadataService', () => {
  it('should retrieve view definitions using fileType-indexed query path', async () => {
    const expectedViews = [{ fileType: OPFS_FILE_TYPE.VIEW_DEFINITION }];
    const toArray = vi.fn().mockResolvedValue(expectedViews);
    const equals = vi.fn(() => ({ toArray }));
    const where = vi.fn(() => ({ equals }));
    const db = {
      opfsFiles: {
        where,
      },
    };
    const config: DatabaseConfig = {
      name: 'test-db',
      version: 3,
      debug: false,
      queryCacheTTL: 1,
      maxRetryAttempts: 1,
      staleThreshold: 1,
      autoCleanup: false,
      cleanupInterval: 1,
      maxCacheEntries: 0,
      mutationRetentionMs: 1,
    };
    const service = new OpfsMetadataService(db as never, config);

    const views = await service.getViews();
    expect(where).toHaveBeenCalledWith('fileType');
    expect(equals).toHaveBeenCalledWith(OPFS_FILE_TYPE.VIEW_DEFINITION);
    expect(views).toEqual(expectedViews);
  });
});
