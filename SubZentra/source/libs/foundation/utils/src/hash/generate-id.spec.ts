import { describe, expect, it } from 'vitest';

import { generateId } from './generate-id';

describe('generateId', () => {
  it('should return a valid UUID v4 format', () => {
    const result = generateId();
    const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
    expect(result).toMatch(uuidRegex);
  });

  it('should generate unique IDs', () => {
    const ids = new Set<string>();
    for (let i = 0; i < 100; i++) {
      ids.add(generateId());
    }
    expect(ids.size).toBe(100);
  });

  it('should return 36-character string', () => {
    const result = generateId();
    expect(result.length).toBe(36);
  });

  it('should have correct structure with dashes', () => {
    const result = generateId();
    const parts = result.split('-');
    expect(parts.length).toBe(5);
    expect(parts[0].length).toBe(8);
    expect(parts[1].length).toBe(4);
    expect(parts[2].length).toBe(4);
    expect(parts[3].length).toBe(4);
    expect(parts[4].length).toBe(12);
  });
});
