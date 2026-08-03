import { useEffect, useState } from 'react';

import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { createEmitter } from './create-emitter';
import { EmitterProvider } from './emitter-provider';
import type { TypedEmitter } from './types';
import { useEmitter } from './use-emitter';

type AppEvents = {
  'toast:show': [message: string];
};

describe('EmitterProvider', () => {
  it('uses the injected emitter instance', () => {
    const injectedEmitter = createEmitter<AppEvents>();
    let resolvedEmitter: TypedEmitter<AppEvents> | null = null;

    const Consumer = () => {
      resolvedEmitter = useEmitter<AppEvents>();
      return null;
    };

    render(
      <EmitterProvider emitter={injectedEmitter}>
        <Consumer />
      </EmitterProvider>,
    );

    expect(resolvedEmitter).toBe(injectedEmitter);
  });

  it('keeps a stable auto-created emitter instance across rerenders', () => {
    let firstEmitter: TypedEmitter<AppEvents> | null = null;
    let secondEmitter: TypedEmitter<AppEvents> | null = null;

    const Consumer = () => {
      const currentEmitter = useEmitter<AppEvents>();
      if (!firstEmitter) {
        firstEmitter = currentEmitter;
        return null;
      }

      secondEmitter = currentEmitter;
      return null;
    };

    const { rerender } = render(
      <EmitterProvider>
        <Consumer />
      </EmitterProvider>,
    );

    rerender(
      <EmitterProvider>
        <Consumer />
      </EmitterProvider>,
    );

    expect(firstEmitter).not.toBeNull();
    expect(secondEmitter).toBe(firstEmitter);
  });

  it('supports cross-component publish subscribe communication', () => {
    const Publisher = () => {
      const emitter = useEmitter<AppEvents>();
      const handlePublish = () => emitter.emit('toast:show', 'Connected');

      return <button onClick={handlePublish}>publish</button>;
    };

    const Subscriber = () => {
      const emitter = useEmitter<AppEvents>();
      const [message, setMessage] = useState('Idle');

      useEffect(() => {
        const handleToast = (nextMessage: string) => setMessage(nextMessage);
        emitter.on('toast:show', handleToast);

        return () => {
          emitter.off('toast:show', handleToast);
        };
      }, [emitter]);

      return <p>{message}</p>;
    };

    render(
      <EmitterProvider>
        <Publisher />
        <Subscriber />
      </EmitterProvider>,
    );

    fireEvent.click(screen.getByRole('button', { name: 'publish' }));
    expect(screen.getByText('Connected')).toBeTruthy();
  });
});
