/**
 * Config Signature Tests
 */

import { describe, expect, it } from 'vitest';

import { createConfigSignature } from './config-signature';

describe('createConfigSignature', () => {
  it('should produce stable signatures for equal object shapes', () => {
    const first = createConfigSignature({ b: 1, a: { d: 4, c: 3 } });
    const second = createConfigSignature({ a: { c: 3, d: 4 }, b: 1 });

    expect(first).toBe(second);
  });

  it('should include function identity in the signature', () => {
    const functionA = () => 'token-A';
    const functionB = () => 'token-B';

    const signatureA = createConfigSignature({ getAccessToken: functionA });
    const signatureB = createConfigSignature({ getAccessToken: functionB });

    expect(signatureA).not.toBe(signatureB);
  });
});
