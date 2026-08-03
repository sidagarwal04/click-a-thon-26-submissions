import type { InternalAxiosRequestConfig } from 'axios';
import { describe, expect, it, vi } from 'vitest';

import type {
  AuthTransport,
  ResolvedAuthTransport,
} from '@open-zentra/foundation-auth';

import { createAuthInterceptor } from './auth-interceptor';

const makeConfig = (): InternalAxiosRequestConfig =>
  ({ headers: {}, url: '/reports', method: 'get' } as unknown as InternalAxiosRequestConfig);

describe('createAuthInterceptor', () => {
  it('injects bearer auth from AuthTransport', async () => {
    const transport: AuthTransport = {
      getTransport: vi.fn(
        async (): Promise<ResolvedAuthTransport> => ({
          kind: 'bearer',
          token: 'token-1',
        }),
      ),
      getScope: vi.fn(() => null),
      subscribeScope: vi.fn(() => () => undefined),
      invalidate: vi.fn(async () => undefined),
    };
    const interceptor = createAuthInterceptor({
      auth: { enabled: true, transport },
      getAccessToken: vi.fn(),
    });

    const result = await interceptor(makeConfig());

    expect(result.headers.Authorization).toBe('Bearer token-1');
    expect(transport.getTransport).toHaveBeenCalledWith({
      audience: 'first_party_http',
      url: '/reports',
      method: 'get',
    });
  });

  it('enables credentials without Authorization for cookie transport', async () => {
    const transport: AuthTransport = {
      getTransport: vi.fn(
        async (): Promise<ResolvedAuthTransport> => ({ kind: 'cookie' }),
      ),
      getScope: vi.fn(() => null),
      subscribeScope: vi.fn(() => () => undefined),
      invalidate: vi.fn(async () => undefined),
    };
    const interceptor = createAuthInterceptor({
      auth: { enabled: true, transport },
      getAccessToken: vi.fn(),
    });

    const result = await interceptor(makeConfig());

    expect(result.withCredentials).toBe(true);
    expect(result.headers.Authorization).toBeUndefined();
  });

  it('keeps legacy getAccessToken support', async () => {
    const interceptor = createAuthInterceptor({
      auth: { enabled: true },
      getAccessToken: vi.fn(async () => 'legacy-token'),
    });

    const result = await interceptor(makeConfig());

    expect(result.headers.Authorization).toBe('Bearer legacy-token');
  });
});
