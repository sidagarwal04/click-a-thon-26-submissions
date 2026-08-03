import type { AxiosInstance } from 'axios';

import type {
  ApiMutationDescriptor,
  ApiQueryDescriptor,
} from '@open-zentra/foundation-data-model';

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value);

export const resolveDescriptorPath = <TArgs>(
  path: string | ((args: TArgs) => string),
  args: TArgs,
): string => (typeof path === 'function' ? path(args) : path);

export const unwrapApiEnvelope = <TData>(value: unknown): TData => {
  if (isRecord(value) && 'data' in value) {
    return value.data as TData;
  }

  return value as TData;
};

export const executeQueryDescriptor = async <TArgs, TData>(
  axiosInstance: AxiosInstance,
  descriptor: ApiQueryDescriptor<TArgs, TData>,
  args: TArgs,
): Promise<TData> => {
  const response = await axiosInstance.request({
    method: descriptor.method ?? 'GET',
    url: resolveDescriptorPath(descriptor.path, args),
    params: descriptor.params?.(args),
  });

  if (descriptor.mapResponse) {
    return descriptor.mapResponse(response.data);
  }

  return unwrapApiEnvelope<TData>(response.data);
};

export const executeMutationDescriptor = async <TArgs, TData>(
  axiosInstance: AxiosInstance,
  descriptor: ApiMutationDescriptor<TArgs, TData>,
  args: TArgs,
): Promise<TData> => {
  const response = await axiosInstance.request({
    method: descriptor.method,
    url: resolveDescriptorPath(descriptor.path, args),
    params: descriptor.params?.(args),
    data: descriptor.body?.(args),
  });

  if (descriptor.mapResponse) {
    return descriptor.mapResponse(response.data);
  }

  return unwrapApiEnvelope<TData>(response.data);
};
