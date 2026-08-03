import { render } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { useEmitter } from './use-emitter';

const Consumer = () => {
  useEmitter();
  return null;
};

describe('useEmitter', () => {
  it('throws when used outside EmitterProvider', () => {
    expect(() => render(<Consumer />)).toThrowError(
      'useEmitter must be used within an EmitterProvider',
    );
  });
});
