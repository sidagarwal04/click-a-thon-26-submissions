import { subscribe, unsubscribe, getRecentEvents } from '@/lib/agent-store';

export const dynamic = 'force-dynamic';

export async function GET() {
  const enc = new TextEncoder();
  let ctrl: ReadableStreamDefaultController<Uint8Array>;

  const stream = new ReadableStream<Uint8Array>({
    start(c) {
      ctrl = c;
      // Replay last 20 events immediately
      for (const ev of [...getRecentEvents(20)].reverse()) {
        c.enqueue(enc.encode(`data: ${JSON.stringify(ev)}\n\n`));
      }
      subscribe(ctrl);
    },
    cancel() { unsubscribe(ctrl); },
  });

  return new Response(stream, {
    headers: {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache, no-transform',
      'Connection': 'keep-alive',
      'X-Accel-Buffering': 'no',
    },
  });
}
