import { useEffect, useState } from 'react'

/** Subscribes to a CSS media query from JS.
 *
 * The rest of this app is responsive through plain @media rules in index.css, which is the
 * right default — CSS reflows without React re-rendering. This exists for the one case CSS
 * cannot express: swapping a segmented button group for a native <select>. Hiding one of
 * the two with `display: none` would leave BOTH controls in the DOM and in the
 * accessibility tree, so a screen reader would announce the metric picker twice and a
 * keyboard user would tab through a control they cannot see. Rendering exactly one requires
 * knowing the breakpoint in JS.
 *
 * Kept to the one query it needs; not a general breakpoint system.
 */
export function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(() =>
    typeof window === 'undefined' ? false : window.matchMedia(query).matches,
  )

  useEffect(() => {
    if (typeof window === 'undefined') return
    const mql = window.matchMedia(query)
    // Re-read on subscribe: the viewport can change between the initial render and the
    // effect, and missing that would leave the wrong control mounted until the next resize.
    setMatches(mql.matches)
    const onChange = (e: MediaQueryListEvent) => setMatches(e.matches)
    mql.addEventListener('change', onChange)
    return () => mql.removeEventListener('change', onChange)
  }, [query])

  return matches
}
