import { describe, expect, it } from 'vitest';

import { extractColumnName, extractTableName, parseMemberRef } from './member-ref';

describe('utils/member-ref', () => {
  it('parses valid member references', () => {
    expect(parseMemberRef('orders.total')).toEqual({
      table: 'orders',
      column: 'total',
    });
  });

  it('returns null for invalid member references', () => {
    expect(parseMemberRef('orders')).toBeNull();
    expect(parseMemberRef('orders.')).toBeNull();
    expect(parseMemberRef('.total')).toBeNull();
  });

  it('extracts table and column safely', () => {
    expect(extractTableName('orders.total')).toBe('orders');
    expect(extractColumnName('orders.total')).toBe('total');
    expect(extractTableName('orders')).toBeNull();
    expect(extractColumnName('orders')).toBeNull();
  });
});
