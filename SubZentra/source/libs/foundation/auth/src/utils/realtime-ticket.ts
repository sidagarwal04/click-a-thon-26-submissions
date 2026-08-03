import type { AxiosInstance } from 'axios';

import type { ApiQueryDescriptor } from '@open-zentra/foundation-data-model';

export interface RealtimeAuthTicket {
  readonly ticket: string;
  readonly expiresAt?: number;
  readonly queryParam?: string;
  readonly url?: string;
  readonly protocols?: string[];
}

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value);

const resolveDescriptorPath = <TArgs>(
  path: string | ((args: TArgs) => string),
  args: TArgs,
): string => (typeof path === 'function' ? path(args) : path);

const unwrapApiEnvelope = (value: unknown): unknown => {
  if (isRecord(value) && 'data' in value) {
    return value.data;
  }

  return value;
};

const normalizeRealtimeTicket = (value: unknown): RealtimeAuthTicket => {
  if (typeof value === 'string') {
    return { ticket: value };
  }

  if (isRecord(value) && typeof value.ticket === 'string') {
    return {
      ticket: value.ticket,
      expiresAt: typeof value.expiresAt === 'number' ? value.expiresAt : undefined,
      queryParam: typeof value.queryParam === 'string' ? value.queryParam : undefined,
      url: typeof value.url === 'string' ? value.url : undefined,
      protocols: Array.isArray(value.protocols)
        ? value.protocols.filter((item): item is string => typeof item === 'string')
        : undefined,
    };
  }

  throw new Error('Realtime ticket response must be a string or { ticket: string }');
};

export const createRealtimeTicketFetcher =
  <TArgs = void>(
    axiosInstance: AxiosInstance,
    descriptor: ApiQueryDescriptor<TArgs, string | RealtimeAuthTicket>,
    getArgs?: () => TArgs,
  ) =>
  async (): Promise<RealtimeAuthTicket> => {
    const args = (getArgs?.() ?? (undefined as TArgs)) as TArgs;
    const response = await axiosInstance.request({
      method: descriptor.method ?? 'GET',
      url: resolveDescriptorPath(descriptor.path, args),
      params: descriptor.params?.(args),
    });

    const mapped = descriptor.mapResponse
      ? descriptor.mapResponse(response.data)
      : unwrapApiEnvelope(response.data);

    return normalizeRealtimeTicket(mapped);
  };
