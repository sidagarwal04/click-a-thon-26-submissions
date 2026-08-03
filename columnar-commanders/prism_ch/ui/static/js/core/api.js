export async function api(path, body) {
  const r = await fetch(path, body ? {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  } : {});
  return r.json();
}

// Consumes a `text/event-stream` POST response, calling `onEvent` for each
// `data: {...}` frame as it arrives. Fetch + a manual reader rather than
// EventSource: EventSource cannot send a POST body, and the spec/events
// payload an agent run needs can be far too large for a GET query string.
export async function streamApi(path, body, onEvent) {
  const r = await fetch(path, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  });
  if (!r.ok || !r.body) throw new Error(`stream request failed: ${r.status}`);

  const reader = r.body.getReader();
  const decoder = new TextDecoder();
  let buf = '';
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    let sep;
    while ((sep = buf.indexOf('\n\n')) !== -1) {
      const frame = buf.slice(0, sep);
      buf = buf.slice(sep + 2);
      const line = frame.split('\n').find(l => l.startsWith('data: '));
      if (!line) continue;
      try {
        onEvent(JSON.parse(line.slice(6)));
      } catch {
        // A frame split across two reads that hasn't fully arrived yet -
        // the buffer above already holds it back until '\n\n' shows up, so
        // this is truly malformed input, not just a partial chunk. Skip it.
      }
    }
  }
}
