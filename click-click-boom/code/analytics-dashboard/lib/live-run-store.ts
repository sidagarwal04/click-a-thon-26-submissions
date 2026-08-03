// Tracks every in-progress (or recently-finished) pipeline run server-side,
// independent of any single browser request.
//
// Why this exists: /api/ingest and /api/analytics stream progress back over
// the SAME HTTP response that started the run (a POST whose body is an SSE
// stream). That works fine while the tab that started it stays open, but the
// stream is tied to that one request/response pair -- a page reload (or
// opening the app in a second tab) has no way to reattach to it. This module
// is fed by both routes as they parse each line, and any client can query
// /api/live-run to discover what's active and reconnect.
//
// Two real incidents shaped this design, in order:
//
// 1. A plain in-memory `let state = {...}` object got reset by Next.js
//    dev-mode hot-reload (which re-evaluates a route module whenever a file
//    in its dependency graph changes) while a run was genuinely still going
//    -- the spawned Python subprocess (a separate OS process) kept writing
//    real progress the reset module could never see again. Fixed by backing
//    state with a file instead of a JS variable.
//
// 2. That file-backed fix then went stale a DIFFERENT way: if the dev server
//    process itself restarts, or the spawned child dies without its `close`
//    handler ever running (killed externally, server crash), nothing calls
//    finishRun() -- and unlike the old in-memory version (which reset to a
//    clean slate for free on every server restart), the file just sits there
//    claiming `active: true` forever, since nothing else ever touches it.
//    There was also a real, separate design gap underneath both bugs: a
//    SINGLE global slot means two simultaneous runs (e.g. an ingestion and a
//    custom analytics investigation started back to back) always collide --
//    the second either gets rejected outright or silently clobbers the
//    first's polling clients.
//
// Fixed by moving to a MAP of runs keyed by runId (so concurrent runs are
// simply different entries, never collide) where every entry also carries
// the spawned process's PID -- staleness is detected by checking whether
// that PID is still alive (`process.kill(pid, 0)`), not by trusting a stored
// boolean that nothing may ever get the chance to flip back. This self-heals
// regardless of *how* a run's tracking went stale (HMR reset is no longer
// possible at all now that it's file-backed, but a killed process is now
// self-diagnosed instead of remembered as a lie).

import fs from 'fs';
import path from 'path';
import os from 'os';
import crypto from 'crypto';

const STATE_FILE = path.join(os.tmpdir(), 'atlys-live-run-state.json');

export type LiveRunKind = 'ingest' | 'analytics';

export interface LiveRunSnapshot {
  runId: string;
  kind: LiveRunKind;
  label: string;          // spec name, or a truncated custom prompt -- display only
  active: boolean;
  pid: number | null;
  startedAt: number;
  events: Record<string, any>[]; // raw trace_event payloads, same shape the routes forward
  result: Record<string, any> | null;
}

type StateFile = Record<string, LiveRunSnapshot>;

function readAll(): StateFile {
  try {
    return JSON.parse(fs.readFileSync(STATE_FILE, 'utf8'));
  } catch {
    return {};
  }
}

function writeAll(map: StateFile): void {
  try {
    fs.writeFileSync(STATE_FILE, JSON.stringify(map));
  } catch {
    // Best-effort -- losing the durability layer shouldn't crash a run.
  }
}

function isPidAlive(pid: number | null): boolean {
  if (pid == null) return false;
  try {
    // Signal 0 sends nothing -- it only checks whether the process exists
    // and is signalable, which is exactly the liveness check needed here.
    process.kill(pid, 0);
    return true;
  } catch {
    return false;
  }
}

// Any run still marked `active` whose pid is no longer alive gets healed to
// `active: false` with a synthetic failure result, lazily, on read -- so a
// stuck entry can never require manual intervention (see incident #2 above).
function heal(map: StateFile): { map: StateFile; changed: boolean } {
  let changed = false;
  for (const run of Object.values(map)) {
    if (run.active && !isPidAlive(run.pid)) {
      run.active = false;
      run.result = run.result ?? {
        status: 'failed',
        error: 'The process behind this run is no longer running (dev server restarted, or it was killed) -- the trace above may be incomplete.',
      };
      changed = true;
    }
  }
  return { map, changed };
}

function readHealed(): StateFile {
  const { map, changed } = heal(readAll());
  if (changed) writeAll(map);
  return map;
}

// Runs older than this are dropped from the file on the next write so it
// doesn't grow forever across a long dev session -- generous, since a
// finished run's own trace lives durably in ClickHouse regardless; this file
// only needs to cover "reconnect to something recent."
const MAX_AGE_MS = 6 * 60 * 60 * 1000;

function prune(map: StateFile): StateFile {
  const cutoff = Date.now() - MAX_AGE_MS;
  const out: StateFile = {};
  for (const [id, run] of Object.entries(map)) {
    if (run.active || run.startedAt >= cutoff) out[id] = run;
  }
  return out;
}

export function startRun(label: string, kind: LiveRunKind): string {
  const runId = crypto.randomUUID();
  const map = prune(readHealed());
  map[runId] = {
    runId, kind, label, active: true, pid: null,
    startedAt: Date.now(), events: [], result: null,
  };
  writeAll(map);
  return runId;
}

export function setPid(runId: string, pid: number): void {
  const map = readAll();
  if (map[runId]) {
    map[runId].pid = pid;
    writeAll(map);
  }
}

export function pushRawEvent(runId: string, event: Record<string, any>): void {
  const map = readAll();
  const run = map[runId];
  if (!run || !run.active) return;
  run.events.push(event);
  writeAll(map);
}

export function finishRun(runId: string, result: Record<string, any>): void {
  const map = readAll();
  if (map[runId]) {
    map[runId].active = false;
    map[runId].result = result;
    writeAll(map);
  }
}

export function getRun(runId: string): LiveRunSnapshot | null {
  return readHealed()[runId] ?? null;
}

// What a client with no runId yet needs to discover what to reconnect to --
// optionally filtered by kind ('ingest' vs 'analytics', since they now run
// independently and a caller usually only cares about one).
export function listActiveRuns(kind?: LiveRunKind): LiveRunSnapshot[] {
  const map = readHealed();
  return Object.values(map)
    .filter(r => r.active && (!kind || r.kind === kind))
    .sort((a, b) => b.startedAt - a.startedAt);
}
