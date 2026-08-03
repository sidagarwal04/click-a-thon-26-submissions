// Ask AI for the v1 concurrency console, pinned to the graded `phoenix` database.
//
// The handler is thin on purpose: validation, the system prompt, the database pin and the rate
// limit all live in lib/ask.ts, which /api/v2/ask uses too. Two consoles asking two questions of
// two databases is a difference of one constant, and everything that makes this safe is shared.
import {NextRequest, NextResponse} from 'next/server'
import {AskCredentialError, askAgent, askConfigError, requestCredential, V1_SCOPE, validateThread, withinRateLimit} from '@/lib/ask'
import type {AskResponse, ApiError} from '@/lib/types'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

export async function POST(req: NextRequest): Promise<NextResponse<AskResponse | ApiError>> {
  if (!withinRateLimit()) {
    return NextResponse.json({error: 'too many questions in the last minute'}, {status: 429})
  }

  let body: unknown
  try {
    body = await req.json()
  } catch {
    return NextResponse.json({error: 'body must be JSON'}, {status: 400})
  }

  // Validated BEFORE the deployment check, so a malformed or oversized thread is rejected the same
  // way whether or not LibreChat happens to be configured. The reverse order makes the guardrails
  // untestable on a machine that has not set the agent up yet, which is every machine at first run.
  const check = validateThread(body)
  if (!check.ok) return NextResponse.json({error: check.error}, {status: check.status})

  // Read from headers, so the key never enters a URL, an access log or system.query_log.
  // A supplied-but-invalid key now throws rather than silently falling back to the server's
  // credential, so the user is told instead of being billed to someone else's account.
  let cred
  try {
    cred = requestCredential(req)
  } catch (e) {
    if (e instanceof AskCredentialError) return NextResponse.json({error: e.message}, {status: 400})
    throw e
  }
  const configError = askConfigError(cred)
  if (configError) return NextResponse.json({error: configError}, {status: 400})

  try {
    return NextResponse.json(await askAgent(V1_SCOPE, check.messages, cred))
  } catch (e) {
    const message =
      e instanceof Error && e.name === 'AbortError' ? 'LibreChat agent timed out' : (e as Error).message
    return NextResponse.json({error: message}, {status: 500})
  }
}
