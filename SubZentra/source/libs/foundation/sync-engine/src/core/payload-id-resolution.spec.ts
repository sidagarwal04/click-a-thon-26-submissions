import { describe, expect, it } from 'vitest';

import { resolvePayloadProvisionalIds } from './payload-id-resolution';

describe('resolvePayloadProvisionalIds', () => {
  it('resolves provisional IDs recursively in nested objects and arrays', () => {
    const payload = {
      parentId: 'provisional_parent',
      nested: {
        childIds: ['provisional_child_1', 'server_child_2'],
      },
      mixed: [{ id: 'provisional_item_1' }, 'provisional_item_2', 123],
    };

    const resolved = resolvePayloadProvisionalIds(payload, (id) => {
      if (id.startsWith('provisional_')) {
        return id.replace('provisional_', 'server_');
      }
      return undefined;
    });

    expect(resolved).toEqual({
      parentId: 'server_parent',
      nested: {
        childIds: ['server_child_1', 'server_child_2'],
      },
      mixed: [{ id: 'server_item_1' }, 'server_item_2', 123],
    });
  });
});
