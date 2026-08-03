import { NextRequest, NextResponse } from 'next/server';
import { getRun, listActiveRuns, LiveRunKind } from '@/lib/live-run-store';

export const dynamic = 'force-dynamic';

// Polled by the client on load/reload (and while a run is active) to detect
// and reattach to an in-progress run -- see lib/live-run-store.ts for why
// this exists separately from /api/ingest's/api/analytics's own SSE stream,
// and why it's keyed by runId now instead of a single global slot (multiple
// runs -- e.g. an ingestion and a custom analytics investigation -- can be
// active at once).
//
// Two shapes:
//   ?runId=<id>        -> that one run's full snapshot (or null if unknown)
//   ?kind=ingest|analytics (runId omitted) -> list of currently active runs
//     of that kind, newest first -- what a client with no runId yet needs to
//     discover what (if anything) to reconnect to.
export async function GET(req: NextRequest) {
  const runId = req.nextUrl.searchParams.get('runId');
  if (runId) {
    return NextResponse.json(getRun(runId));
  }
  const kindParam = req.nextUrl.searchParams.get('kind');
  const kind = kindParam === 'ingest' || kindParam === 'analytics' ? (kindParam as LiveRunKind) : undefined;
  return NextResponse.json({ runs: listActiveRuns(kind) });
}
