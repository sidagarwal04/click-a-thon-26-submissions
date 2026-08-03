import { useCallback, useEffect, useRef, useState } from 'react'

/** Fetches immediately, then again every intervalMs, until unmounted -- this is the
 * UI's "real-time" mechanism (30s by default, matching the backend scanner's own
 * interval). A request already in flight is never overlapped by the next tick.
 *
 * The fetcher is held in a ref rather than captured in the useCallback closure.
 * Previously `run` was `useCallback(..., [])` with an eslint-disable, which pinned the
 * FIRST fetcher forever: any caller passing an inline arrow whose captured values
 * changed would keep polling with the original ones, silently serving stale data with
 * no visible failure. Callers here pass inline arrows (`() => listInvestigations(30)`),
 * so that trap was live.
 *
 * `isRefreshing` is exposed separately from `loading` so a background refresh can be
 * indicated without blanking the screen -- `loading` stays true only until the first
 * settle, which is what lets a polled view avoid flickering every interval.
 */
export function usePolling<T>(fetcher: () => Promise<T>, intervalMs: number) {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [isRefreshing, setIsRefreshing] = useState(false)
  const inFlight = useRef(false)

  // Kept current on every render, so `run` can stay stable without going stale.
  const fetcherRef = useRef(fetcher)
  fetcherRef.current = fetcher

  const run = useCallback(async () => {
    if (inFlight.current) return
    inFlight.current = true
    setIsRefreshing(true)
    try {
      const result = await fetcherRef.current()
      setData(result)
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      inFlight.current = false
      setLoading(false)
      setIsRefreshing(false)
    }
  }, [])

  useEffect(() => {
    run()
    const id = setInterval(run, intervalMs)
    return () => clearInterval(id)
  }, [run, intervalMs])

  return { data, error, loading, isRefreshing, refetch: run }
}
