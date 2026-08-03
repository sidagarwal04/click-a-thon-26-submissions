import { esc } from './dom.js';

// Renders the `step_start` / `step_end` events a run streams over SSE
// (see prism_ch/tracing.py's progress sink) as a live activity log: each
// in-flight step gets a ticking elapsed-time counter that freezes at the
// real duration once its `step_end` arrives. Shared by every tab that runs
// an agent pipeline, so the timer behaves identically everywhere.
export class ActivityLog {
  constructor(containerId, bodyId) {
    this.container = document.getElementById(containerId);
    this.body = document.getElementById(bodyId);
    this.start = 0;
    // agent:action -> queue of in-flight rows, oldest first. A queue (not a
    // single slot) because the same step name can legitimately run more than
    // once in a run (e.g. `load_events` retried after a repair) - steps run
    // strictly sequentially today, so FIFO always pairs the right start/end.
    this.inflight = new Map();
  }

  reset() {
    this.start = Date.now();
    this.container.style.display = 'block';
    this.body.innerHTML = '';
    for (const queue of this.inflight.values()) {
      for (const entry of queue) clearInterval(entry.tickHandle);
    }
    this.inflight.clear();
  }

  _elapsed() {
    return ((Date.now() - this.start) / 1000).toFixed(1) + 's';
  }

  // A plain, non-timed line: upload notes, a terminal summary, and the like.
  line(text, state = 'run') {
    const mark = state === 'done' ? '✓' : state === 'fail' ? '✕' : '•';
    this.body.insertAdjacentHTML('beforeend',
      `<div class="ev ${state}"><span class="t">${this._elapsed()}</span>` +
      `<span class="s">${mark}</span><span>${esc(text)}</span></div>`);
    this.body.scrollTop = this.body.scrollHeight;
  }

  stepStart(agent, action) {
    const key = `${agent}:${action}`;
    const label = action.replace(/_/g, ' ');
    const startedAt = Date.now();
    const id = `step-${Math.random().toString(36).slice(2)}`;
    this.body.insertAdjacentHTML('beforeend',
      `<div class="ev run" id="${id}"><span class="t">${this._elapsed()}</span>` +
      `<span class="s"><span class="spin"></span></span>` +
      `<span>${esc(label)} <span class="ticker">0.0s</span></span></div>`);
    this.body.scrollTop = this.body.scrollHeight;

    const row = document.getElementById(id);
    const ticker = row.querySelector('.ticker');
    const tickHandle = setInterval(() => {
      ticker.textContent = ((Date.now() - startedAt) / 1000).toFixed(1) + 's';
    }, 100);

    if (!this.inflight.has(key)) this.inflight.set(key, []);
    this.inflight.get(key).push({ row, tickHandle });
  }

  stepEnd(agent, action, durationMs, ok) {
    const key = `${agent}:${action}`;
    const label = action.replace(/_/g, ' ');
    const secs = (durationMs / 1000).toFixed(2) + 's';
    const queue = this.inflight.get(key);
    const entry = queue && queue.shift();

    if (!entry) {
      // step_end with no matching step_start (a stream that connected mid-run) -
      // still worth a line, just not a ticking one.
      this.line(`${label} — ${secs}`, ok ? 'done' : 'fail');
      return;
    }
    clearInterval(entry.tickHandle);
    entry.row.className = `ev ${ok ? 'done' : 'fail'}`;
    entry.row.innerHTML =
      `<span class="t">${this._elapsed()}</span>` +
      `<span class="s">${ok ? '✓' : '✕'}</span>` +
      `<span>${esc(label)} <span class="muted">(${secs})</span></span>`;
  }
}
