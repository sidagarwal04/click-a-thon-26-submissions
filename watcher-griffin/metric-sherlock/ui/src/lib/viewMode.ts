/* Simple or Full.
 *
 * The incident page carries two audiences with incompatible needs. Someone who owns the
 * ad stack wants the chain of reasoning and the number; someone auditing the system
 * wants the spread bars, the band arithmetic and the SQL. Serving both on one screen
 * meant serving the second one, because the dense material is what fills the space.
 *
 * Simple mode does NOT remove anything. Every section still renders, collapsed into a
 * disclosure the reader can open — which matters, because a page that silently drops
 * its evidence when a toggle is flipped is a page whose evidence is optional. What
 * Simple mode changes is what is open by default.
 *
 * `?view=full` in the URL wins over the stored preference, so a link can be shared in a
 * known state — the one a judge should be sent.
 */

import { useCallback, useEffect, useState } from 'react'

export type ViewMode = 'simple' | 'full'

const STORAGE_KEY = 'rca.viewMode'

function readInitial(): ViewMode {
  // URL first: an explicitly shared link must not be overridden by whatever this
  // browser happened to choose last time.
  try {
    const fromUrl = new URLSearchParams(window.location.search).get('view')
    if (fromUrl === 'full' || fromUrl === 'simple') return fromUrl
    const stored = window.localStorage.getItem(STORAGE_KEY)
    if (stored === 'full' || stored === 'simple') return stored
  } catch {
    // Private-browsing modes throw on localStorage. A preference is not worth an
    // exception that blanks the page.
  }
  return 'simple'
}

export function useViewMode(): [ViewMode, (next: ViewMode) => void] {
  const [mode, setMode] = useState<ViewMode>(readInitial)

  useEffect(() => {
    try {
      window.localStorage.setItem(STORAGE_KEY, mode)
    } catch {
      /* preference is best-effort */
    }
  }, [mode])

  const set = useCallback((next: ViewMode) => {
    setMode(next)
    // Keep the URL honest about what is on screen, without adding a history entry —
    // a back button that walks through view toggles is a back button nobody can use.
    try {
      const url = new URL(window.location.href)
      if (next === 'full') url.searchParams.set('view', 'full')
      else url.searchParams.delete('view')
      window.history.replaceState({}, '', url)
    } catch {
      /* URL rewriting is cosmetic */
    }
  }, [])

  return [mode, set]
}
