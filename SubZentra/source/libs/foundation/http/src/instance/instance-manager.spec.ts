/**
 * Instance Manager Tests
 */

import type { AxiosResponse, InternalAxiosRequestConfig } from 'axios';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import { HttpConfigError } from '../errors/http-errors';
import { httpInstanceManager } from './instance-manager';

describe('httpInstanceManager', () => {
  beforeEach(() => {
    httpInstanceManager.clear();
  });

  afterEach(() => {
    httpInstanceManager.clear();
  });

  it('should apply client headers for manager-created instances', async () => {
    const managed = httpInstanceManager.createInstance(
      {
        baseUrl: 'https://api.example.com',
        clientHeaders: {
          clientId: 'test-client',
          clientVersion: '1.0.0',
        },
      },
      'client-header-test',
    );

    const response = await managed.instance.request({
      url: '/users',
      method: 'get',
      adapter: async (config): Promise<AxiosResponse> => ({
        data: null,
        status: 200,
        statusText: 'OK',
        headers: {},
        config: config as InternalAxiosRequestConfig,
      }),
    });

    expect(response.config.headers['X-Client-ID']).toBe('test-client');
    expect(response.config.headers['X-Client-Version']).toBe('1.0.0');
  });

  it('should throw when creating the same key with a different config', () => {
    httpInstanceManager.createInstance(
      {
        baseUrl: 'https://api.example.com',
        timeout: 1_000,
      },
      'shared-key',
    );

    expect(() =>
      httpInstanceManager.createInstance(
        {
          baseUrl: 'https://api.example.com',
          timeout: 2_000,
        },
        'shared-key',
      ),
    ).toThrow(HttpConfigError);
  });
});
