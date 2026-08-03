// In-memory SSE event bus — persists across requests in the same Node.js process (dev)
export interface AgentEvent {
  id: string;
  ts: number;
  agent: string;
  spec: string;
  step: string;
  status: 'running' | 'done' | 'error';
  message: string;
  trace_url?: string;
  proposal_id?: string;
}

type Ctrl = ReadableStreamDefaultController<Uint8Array>;

const store: { events: AgentEvent[]; controllers: Set<Ctrl> } = {
  events: [],
  controllers: new Set(),
};

const enc = new TextEncoder();

export function pushEvent(ev: Omit<AgentEvent, 'id' | 'ts'>): AgentEvent {
  const full: AgentEvent = { ...ev, id: crypto.randomUUID(), ts: Date.now() };
  store.events = [full, ...store.events].slice(0, 100);
  const chunk = enc.encode(`data: ${JSON.stringify(full)}\n\n`);
  for (const ctrl of store.controllers) {
    try { ctrl.enqueue(chunk); } catch { store.controllers.delete(ctrl); }
  }
  return full;
}

export function getRecentEvents(limit = 30): AgentEvent[] {
  return store.events.slice(0, limit);
}

export function subscribe(ctrl: Ctrl): void { store.controllers.add(ctrl); }
export function unsubscribe(ctrl: Ctrl): void { store.controllers.delete(ctrl); }
