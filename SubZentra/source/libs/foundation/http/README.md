# Foundation HTTP

`@open-zentra/foundation-http` is the standardized HTTP transport layer for Open Zentra Web.
It provides a typed Axios client, request/response interception, enterprise error mapping, retry logic,
optional circuit-breaker protection, and React provider integration.

## Purpose

This library exists to keep HTTP behavior consistent across the monorepo:

- Unified request headers and auth token injection
- Shared retry and timeout behavior
- Typed `HttpError` hierarchy (instead of ad-hoc `AxiosError` handling)
- Optional per-host circuit breaker for unstable upstreams
- Predictable lifecycle and cleanup for interceptor registration

## Prerequisites

- `react` (`^18.x || ^19.x`)
- `axios` (`^1.x`)
- TypeScript strict mode (already enabled in this workspace)

## Installation

This is an internal workspace package and is consumed through monorepo dependencies.

```json
{
  "dependencies": {
    "@open-zentra/foundation-http": "workspace:*"
  }
}
```

## Quick Start

### 1. Wrap your app with `HttpProvider`

```tsx
import { HttpProvider } from '@open-zentra/foundation-http';

export const AppProviders = ({ children }: { children: React.ReactNode }) => (
  <HttpProvider
    config={{
      baseUrl: 'https://api.example.com',
      auth: { enabled: true },
      retry: { maxRetries: 3 },
      circuitBreaker: { enabled: true },
    }}
    authInternals={{
      getAccessToken: async () => localStorage.getItem('accessToken'),
    }}
  >
    {children}
  </HttpProvider>
);
```

### 2. Use the configured client

```tsx
import { useHttp } from '@open-zentra/foundation-http';

export const Users = () => {
  const { axios, isInitialized } = useHttp();

  if (!isInitialized || !axios) {
    return null;
  }

  // axios instance already has auth/retry/error mapping interceptors wired.
  return <button onClick={() => axios.get('/users')}>Load</button>;
};
```

## Public API

Primary entrypoint:

- `@open-zentra/foundation-http`

This package intentionally does not expose a broad `./internal` mirror entry anymore.
Use only the documented public exports from the root entrypoint.

## Configuration

### `HttpClientConfig`

```ts
interface HttpClientConfig {
  readonly baseUrl: string;
  readonly timeout?: number;
  readonly withCredentials?: boolean;
  readonly defaultHeaders?: Readonly<Record<string, string>>;
  readonly clientHeaders?: ClientHeadersConfig;
  readonly retry?: Partial<HttpRetryConfig>;
  readonly auth?: Partial<AuthConfig>;
  readonly circuitBreaker?: Partial<HttpCircuitBreakerConfig>;
  readonly debug?: boolean;
}
```

### `HttpRetryConfig`

```ts
interface HttpRetryConfig {
  readonly enabled: boolean;
  readonly maxRetries: number;
  readonly initialDelayMs: number;
  readonly maxDelayMs: number;
  readonly backoffMultiplier: number;
  readonly retryableStatusCodes: readonly number[];
  readonly retryOnNetworkError: boolean;
}
```

Default: `DEFAULT_HTTP_RETRY_CONFIG`

### `HttpCircuitBreakerConfig`

```ts
interface HttpCircuitBreakerConfig {
  readonly enabled: boolean;
  readonly failureThreshold: number;
  readonly resetTimeoutMs: number;
  readonly halfOpenMaxRequests: number;
  readonly failureStatusCodes: readonly number[];
  readonly countNetworkErrors: boolean;
  readonly maxHosts: number;
  readonly hostTtlMs: number;
  readonly debug: boolean;
}
```

Default: `DEFAULT_HTTP_CIRCUIT_BREAKER_CONFIG` (`enabled: false`)

### `AuthConfig`

```ts
interface AuthConfig {
  readonly enabled: boolean;
  readonly getAccessToken?: () => Promise<string | null>;
  readonly onUnauthorized?: (statusCode: number, url?: string) => void;
  readonly tokenType?: string;
}
```

## Interceptor Pipeline

Order matters.

### Request interceptors (LIFO at execution)

1. Headers interceptor
2. Params interceptor
3. Auth interceptor
4. Circuit-breaker request interceptor (only when enabled)

### Response interceptors (FIFO at execution)

1. Circuit-breaker response interceptor (only when enabled)
2. Retry interceptor
3. Unauthorized handler interceptor
4. Error normalizer interceptor

## Error Model

All normalized errors extend `HttpError` (which extends `FoundationError`).

Key classes:

- `HttpRequestError`
- `HttpTimeoutError`
- `HttpNetworkError`
- `HttpCancelledError`
- `HttpUnauthorizedError`
- `HttpForbiddenError`
- `HttpNotFoundError`
- `HttpServerError`
- `HttpConfigError`
- `HttpNotInitializedError`
- `HttpSerializationError`

Use type guards such as:

- `isHttpError`
- `isHttpTimeoutError`
- `isHttpUnauthorizedError`
- `isRetryableHttpError`

## Architecture Overview

```text
core/
  constants.ts
  types.ts
  retry-utils.ts
  request-metadata.ts
  config-signature.ts
instance/
  axios-factory.ts
  instance-manager.ts
interceptors/
  setup.ts
  request/*
  response/*
errors/
  http-errors.ts
  type-guards.ts
provider/
  http-provider.tsx
  http-context.ts
  http-internals-context.ts
hooks/
  use-http.ts
  use-http-internals.ts
```

## Breaking Changes

### Same-key instance reconfiguration now throws

`httpInstanceManager.createInstance(config, key)` now throws `HttpConfigError` if:

- an instance already exists for `key`, and
- the new effective config differs from the existing instance config.

This prevents silent configuration drift.

### Removed broad internal mirror entrypoint implementation

The old `src/internal.ts` mirror surface was removed as part of API cleanup.
Consumers should use the root public entrypoint only.

## Performance and Safety Notes

- Circuit breaker host state is bounded (`maxHosts`) and TTL-pruned (`hostTtlMs`) to avoid unbounded memory growth.
- Interceptors are always ejected on disposal to avoid leaks.
- Provider lifecycle uses function-aware config signatures so function changes (like token callbacks) trigger proper re-initialization.

## Testing and Verification

Run checks directly from workspace root:

```bash
npx eslint libs/foundation/http/src --ext .ts,.tsx
npx tsc -p libs/foundation/http/tsconfig.lib.json --noEmit
npx vitest run libs/foundation/http/src --config vitest.config.ts
```

## Contributing Guidelines

- Keep changes scoped to `libs/foundation/http` for HTTP-library work.
- Reuse `foundation-utils` and `foundation-data-model` primitives before adding new local utilities.
- Avoid `fetch` in this library; use Axios and configured instances.
- Keep strict typing; avoid unchecked casts in source files.
- Add/adjust tests for behavior changes (not just type-level changes).
