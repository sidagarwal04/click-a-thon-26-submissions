/**
 * HTTP mutation adapter for sync queue replay.
 * @module http/adapter
 */

import type { AxiosError, AxiosInstance } from 'axios';

import {
  MUTATION_TYPE,
  type ApiMutationDescriptor,
  type ApiQueryDescriptor,
  type MutationQueueEntry,
  type UnifiedTableConfig,
} from '@open-zentra/foundation-data-model';
import {
  createDebugLogger,
  Disposable,
  getErrorMessage,
} from '@open-zentra/foundation-utils';

import type { MutationExecutorResult } from '../queue/processor';

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value);

const unwrapApiEnvelope = (value: unknown): unknown => {
  if (isRecord(value) && 'data' in value) {
    return value.data;
  }

  return value;
};

const extractServerTimestamp = (value: unknown): number | undefined => {
  if (!isRecord(value)) {
    return undefined;
  }

  if (typeof value.occurredAt === 'number') {
    return value.occurredAt;
  }

  if (typeof value.updatedAt === 'string') {
    const parsed = Date.parse(value.updatedAt);
    return Number.isNaN(parsed) ? undefined : parsed;
  }

  if (isRecord(value.meta) && typeof value.meta.timestamp === 'number') {
    return value.meta.timestamp;
  }

  return undefined;
};

const resolveDescriptorPath = <TArgs>(
  path: string | ((args: TArgs) => string),
  args: TArgs,
): string => (typeof path === 'function' ? path(args) : path);

export interface HttpMutationAdapterConfig {
  readonly axiosInstance: AxiosInstance;
  readonly tables?: ReadonlyArray<UnifiedTableConfig<ApiQueryDescriptor, ApiMutationDescriptor>>;
  readonly debug?: boolean;
}

export class HttpMutationAdapter extends Disposable {
  private readonly axiosInstance: AxiosInstance;
  private readonly logger;
  private readonly tables = new Map<
    string,
    UnifiedTableConfig<ApiQueryDescriptor, ApiMutationDescriptor>
  >();

  constructor(config: HttpMutationAdapterConfig) {
    super();
    this.axiosInstance = config.axiosInstance;
    this.logger = createDebugLogger('HttpMutationAdapter', config.debug ?? false);

    for (const table of config.tables ?? []) {
      this.tables.set(table.name, table);
    }
  }

  private getDescriptor(entry: MutationQueueEntry): ApiMutationDescriptor | undefined {
    const table = this.tables.get(entry.tableName);
    if (!table?.api) {
      return undefined;
    }

    switch (entry.type) {
      case MUTATION_TYPE.CREATE:
        return table.api.create;
      case MUTATION_TYPE.UPDATE:
        return table.api.update;
      case MUTATION_TYPE.DELETE:
        return table.api.delete;
      default:
        return undefined;
    }
  }

  async execute(entry: MutationQueueEntry): Promise<MutationExecutorResult> {
    this.ensureNotDisposed();

    const descriptor = this.getDescriptor(entry);
    if (!descriptor) {
      return {
        success: false,
        error: `No API mutation configured for ${entry.tableName}:${entry.type}`,
      };
    }

    const args = entry.payload as Record<string, unknown>;

    try {
      const response = await this.axiosInstance.request({
        method: descriptor.method,
        url: resolveDescriptorPath(descriptor.path, args),
        params: descriptor.params?.(args),
        data: descriptor.body?.(args),
      });

      const mapped = descriptor.mapResponse
        ? descriptor.mapResponse(response.data)
        : unwrapApiEnvelope(response.data);
      const serverData = mapped;
      const serverId = isRecord(serverData) && typeof serverData.id === 'string' ? serverData.id : undefined;

      return {
        success: true,
        data: mapped,
        serverId,
        serverTimestamp: extractServerTimestamp(response.data) ?? Date.now(),
        serverData,
      };
    } catch (error) {
      this.logger.warn('HTTP mutation replay failed:', error);
      const axiosError = error as AxiosError;
      if (axiosError.response?.status === 409) {
        const serverData = unwrapApiEnvelope(axiosError.response.data);
        return {
          success: false,
          error: getErrorMessage(error),
          serverData,
          serverTimestamp: extractServerTimestamp(axiosError.response.data) ?? Date.now(),
        };
      }

      return {
        success: false,
        error: getErrorMessage(error),
      };
    }
  }

  createMutationExecutor(): (entry: MutationQueueEntry) => Promise<MutationExecutorResult> {
    return (entry) => this.execute(entry);
  }

  protected onDispose(): void {
    this.tables.clear();
  }
}

export const createHttpMutationAdapter = (
  config: HttpMutationAdapterConfig,
): HttpMutationAdapter => new HttpMutationAdapter(config);
