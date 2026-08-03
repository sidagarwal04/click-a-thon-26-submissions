// ONE PLACE THAT TURNS A THROWN ERROR INTO A RESPONSE.
//
// Every data route used to do `{error: (e as Error).message}`, and lib/clickhouse.ts throws
// `body.slice(0, 500)` -- the raw ClickHouse response. Measured: a bad `as_of` returned
// "Code: 41. DB::Exception: ... In scope per_session. (CANNOT_PARSE_DATETIME) (version
// 26.2.1.525)", leaking the server version, internal exception codes and a fragment of the query
// plan. Worse, an undici DNS or TLS failure yields "getaddrinfo ENOTFOUND <host>", which would
// have put our ClickHouse Cloud hostname on screen, because both consoles render `error` directly.
//
// The detail is not discarded: it is logged server-side, where it is useful, and withheld from the
// browser, where it is only a gift to whoever is probing.
import {NextResponse} from 'next/server'
import type {ApiError} from './types'

/** Errors whose message is written FOR the user and is safe to show verbatim. */
export class PublicError extends Error {
  constructor(message: string, readonly status: number = 400) {
    super(message)
  }
}

export function errorResponse(where: string, e: unknown): NextResponse<ApiError> {
  if (e instanceof PublicError) {
    return NextResponse.json<ApiError>({error: e.message}, {status: e.status})
  }

  const detail = e instanceof Error ? e.message : String(e)
  // Server-side only. This is the line an operator greps for when a judge reports a blank panel.
  console.error(`[${where}] ${detail}`)

  // A timeout is worth naming, because "it is still running" and "it is broken" call for
  // different reactions from whoever is watching.
  const timedOut = e instanceof Error && (e.name === 'TimeoutError' || e.name === 'AbortError')
  return NextResponse.json<ApiError>(
    {
      error: timedOut
        ? 'the query took too long and was cancelled. Narrow the time window or the filters.'
        : 'the query could not be completed. The server log has the detail.',
    },
    {status: timedOut ? 504 : 500},
  )
}
