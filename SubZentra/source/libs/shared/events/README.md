# @open-zentra/shared-events

`@open-zentra/shared-events` provides thin, TypeScript-first React wrappers around:

- `react-hotkeys-hook`
- `eventemitter3`

The library is internal-only and explicitly blocked from publishing.

## Installation

This package is consumed from the workspace:

```bash
npm install
```

## Quickstart

```tsx
import {
  EmitterProvider,
  HotkeysProvider,
  useEmitter,
  useHotkeys,
} from '@open-zentra/shared-events';

type AppEvents = {
  'toast:show': [message: string];
};

const ShortcutButton = () => {
  useHotkeys('ctrl+k', () => console.log('Open command palette'));
  return <button type="button">Open</button>;
};

const ToastPublisher = () => {
  const emitter = useEmitter<AppEvents>();
  return (
    <button type="button" onClick={() => emitter.emit('toast:show', 'Saved')}>
      Emit Toast
    </button>
  );
};

const App = () => (
  <HotkeysProvider initiallyActiveScopes={['global']}>
    <EmitterProvider<AppEvents>>
      <ShortcutButton />
      <ToastPublisher />
    </EmitterProvider>
  </HotkeysProvider>
);
```

## API

### Hotkeys

- `useHotkeys`: typed passthrough to `react-hotkeys-hook`'s `useHotkeys`.
- `HotkeysProvider`: typed passthrough to `react-hotkeys-hook`'s provider.

### Emitter

- `createEmitter<TEvents>()`: creates a typed `eventemitter3` instance.
- `EmitterProvider`: provides a typed emitter through React context.
- `useEmitter<TEvents>()`: consumes emitter from context and throws when provider is missing.
- `TypedEmitter<TEvents>`: exported typed alias for emitter instances.

## TypeScript Usage

```ts
import { createEmitter } from '@open-zentra/shared-events';

type AppEvents = {
  'toast:show': [message: string, level: 'info' | 'error'];
  'modal:open': [id: string];
};

const emitter = createEmitter<AppEvents>();
emitter.emit('toast:show', 'Saved', 'info');
```

## Migration Guidance

1. Replace direct `react-hotkeys-hook` imports with `@open-zentra/shared-events` hotkeys exports.
2. Replace ad-hoc `eventemitter3` instances with `createEmitter<T>()`.
3. Move emitter wiring into `EmitterProvider` and consume via `useEmitter<T>()`.

## Troubleshooting

- `useEmitter must be used within an EmitterProvider`: wrap consuming components in `EmitterProvider`.
- Hotkey callback not firing: verify active scopes and key combination registration.

## Development

```bash
npx nx lint shared-events
npx nx test shared-events
npx nx build shared-events
npx nx typecheck shared-events
```
