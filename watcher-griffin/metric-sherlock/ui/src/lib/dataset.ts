/* Which dataset the console is looking at.
 *
 * The selection has to be readable from TWO places with different rules, which is why this
 * is a tiny external store rather than a hook like lib/viewMode.ts:
 *
 *   - api/client.ts, which is NOT a component and cannot call useContext, has to attach the
 *     dataset to every request;
 *   - the header control and App's route key, which are components and need to re-render.
 *
 * useSyncExternalStore bridges the two: one module-level value, one subscriber list, and a
 * hook over it. A Context alone could not serve the first caller.
 *
 * Resolution order matches viewMode.ts deliberately -- URL, then localStorage, then the
 * default -- so `?dataset=unseen` in a shared link wins over whatever this browser last
 * chose. That matters here more than it does for a view toggle: the link decides which
 * WORLD the reader is looking at, and the two are indistinguishable by eye.
 *
 * There is deliberately NO hardcoded list of valid keys. The server owns the registry
 * (GET /api/datasets) and a second copy here would be free to drift into the most
 * misleading shape available -- an option labelled with a date range the data does not have.
 * A stored key the server rejects is self-healed by reconcile() below rather than guarded
 * against up front.
 */

import { useSyncExternalStore } from 'react'

const STORAGE_KEY = 'rca.dataset'
/** Matches the server's own default. Only used before /api/datasets has answered. */
export const DEFAULT_DATASET = 'main'

function readInitial(): string {
  try {
    const fromUrl = new URLSearchParams(window.location.search).get('dataset')
    if (fromUrl) return fromUrl
    const stored = window.localStorage.getItem(STORAGE_KEY)
    if (stored) return stored
  } catch {
    // Private-browsing modes throw on localStorage. A preference is not worth an
    // exception that blanks the page.
  }
  return DEFAULT_DATASET
}

let current = readInitial()
const listeners = new Set<() => void>()

/** Read outside React -- this is what api/client.ts calls on every request. */
export function getDataset(): string {
  return current
}

function emit() {
  listeners.forEach((l) => l())
}

export function setDataset(next: string): void {
  if (next === current) return
  current = next
  try {
    window.localStorage.setItem(STORAGE_KEY, next)
  } catch {
    /* preference is best-effort */
  }
  // Keep the URL honest about which dataset is on screen, without adding a history
  // entry -- a back button that walks through dataset switches is one nobody can use.
  // Same contract as lib/viewMode.ts.
  try {
    const url = new URL(window.location.href)
    if (next === DEFAULT_DATASET) url.searchParams.delete('dataset')
    else url.searchParams.set('dataset', next)
    window.history.replaceState({}, '', url)
  } catch {
    /* URL rewriting is cosmetic */
  }
  emit()
}

/**
 * Drops a selection the server does not recognise, once the real registry is known.
 *
 * Without this, a stale localStorage value (a renamed dataset, a hand-edited URL) would
 * make EVERY request 400 forever, with no way back except clearing site data. Falling
 * back to the server's own default is safe because it is the same dataset an
 * unparameterised request already gets.
 */
export function reconcile(validKeys: string[], serverDefault: string): void {
  if (validKeys.length === 0 || validKeys.includes(current)) return
  setDataset(validKeys.includes(serverDefault) ? serverDefault : validKeys[0])
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

/** The selected dataset, re-rendering the caller when it changes. */
export function useDataset(): string {
  return useSyncExternalStore(subscribe, getDataset, getDataset)
}
