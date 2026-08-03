/**
 * Talking to the Connector API.
 *
 * Thin on purpose — these are the four calls the Connections pages make, named
 * after what the operator is doing rather than after the HTTP verb.
 */

import { ApiError, apiUrl, requestJson, type TokenSource } from '../../api';

import type { RegisterSourceRequest, SourceResponse } from './types';

export const listSources = (getToken: TokenSource) =>
  requestJson<SourceResponse[]>('/v1/connector/sources', getToken);

/**
 * Register a source.
 *
 * The API tests the connection before it persists anything, so a resolved
 * promise means the credentials reached the service — there is no separate
 * "test then save", and a rejection means nothing was stored.
 */
export const registerSource = (getToken: TokenSource, body: RegisterSourceRequest) =>
  requestJson<SourceResponse>('/v1/connector/sources', getToken, {
    method: 'POST',
    body: JSON.stringify(body),
  });

/** Re-check a source that is already registered, and record what came back. */
export const testConnection = (getToken: TokenSource, dataSourceId: string) =>
  requestJson<SourceResponse>(
    `/v1/connector/sources/${dataSourceId}/test-connection`,
    getToken,
    { method: 'POST' },
  );

export const deleteSource = async (getToken: TokenSource, dataSourceId: string) => {
  // 204 No Content: there is no body to parse, so this cannot go through
  // `requestJson`.
  const token = await getToken();
  const response = await fetch(`${apiUrl}/v1/connector/sources/${dataSourceId}`, {
    method: 'DELETE',
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
  });
  if (!response.ok) {
    const error = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new ApiError(error?.detail ?? 'ZentraOS could not remove this source.', response.status);
  }
};
