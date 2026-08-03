/**
 * Talking to the Investigation API.
 *
 * Extracted from `app.tsx` so the Draft Finding panel can follow a claim to
 * its evidence without importing the whole app — and so a failed request
 * carries its status. A caller that cannot tell 404 from 500 cannot tell
 * "you may not see this" from "something broke", and the two are different
 * things to tell a reader.
 */

export const apiUrl =
  (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, '') ??
  'http://localhost:8000';

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    /**
     * The stable error code, where the endpoint publishes one — the Thread and
     * Workspace routes answer `{code, message}` rather than FastAPI's
     * `{detail}`. A caller that only reads the status cannot tell
     * `thread_conflict` (ask again once the Investigation finishes) from a
     * conflict it should give up on, and those are different things to say.
     */
    readonly code: string | null = null,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

export type TokenSource = () => Promise<string | null>;

export const requestJson = async <T>(
  url: string,
  getToken: TokenSource,
  options?: RequestInit,
): Promise<T> => {
  const token = await getToken();
  const response = await fetch(`${apiUrl}${url}`, {
    ...options,
    headers: {
      ...(options?.body ? { 'Content-Type': 'application/json' } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options?.headers,
    },
  });
  if (!response.ok) {
    const error = (await response.json().catch(() => null)) as {
      detail?: string;
      code?: string;
      message?: string;
    } | null;
    throw new ApiError(
      error?.detail ?? error?.message ?? 'ZentraOS could not complete this request.',
      response.status,
      error?.code ?? null,
    );
  }
  // 204 carries no body, and asking `json()` for one throws.
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
};
