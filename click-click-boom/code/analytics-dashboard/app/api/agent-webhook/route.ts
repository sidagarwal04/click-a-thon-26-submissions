import { NextRequest, NextResponse } from 'next/server';
import { pushEvent } from '@/lib/agent-store';

export async function POST(req: NextRequest) {
  const body = await req.json();
  const event = pushEvent({
    agent: body.agent ?? 'unknown',
    spec: body.spec ?? '',
    step: body.step ?? '',
    status: body.status ?? 'running',
    message: body.message ?? '',
    trace_url: body.trace_url,
    proposal_id: body.proposal_id,
  });
  return NextResponse.json({ ok: true, id: event.id });
}
