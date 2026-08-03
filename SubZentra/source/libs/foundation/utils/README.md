# Foundation Utils

`@open-zentra/foundation-utils` provides framework-agnostic utilities shared across foundation libraries.

## Scope

Use this library for pure helpers that do not depend on React, app state, or domain-specific concerns.

## Public Modules

- `browser`: environment and browser detection helpers
- `url`: URL sanitization, route extraction, and propagation checks
- `hash`: deterministic hashing and id generation
- `logger`: structured logging primitives
- `concurrency`: mutex/semaphore synchronization
- `singleton`: singleton factory helpers
- `assert`: runtime assertions and type narrowing
- `async`: deferred/timeout/scheduling helpers
- `error`: error normalization and classification
- `object`: deep freeze utilities
- `validation`: numeric and range validators
- `opfs`: OPFS capability and directory helpers
- `algorithm`: dependency graph utilities
- `disposable`: disposable lifecycle primitives
- `timer`: safe timer/interval/debounce utilities
- `constants`: stable empty collection references

## Usage

```ts
import { createLogger, hashPayloadSync, Mutex } from '@open-zentra/foundation-utils';

const logger = createLogger('Example', { level: 'debug' });
const lock = new Mutex();

await lock.runExclusive(async () => {
  const key = hashPayloadSync({ id: '123' });
  logger.debug('Generated key', key);
});
```

## Rules

- Keep utilities side-effect free by default.
- Avoid importing React or app-layer libraries here.
- Move reusable generic logic here only when it is used by multiple libraries.
- Do not place domain entities, API contracts, or feature logic in this package.
