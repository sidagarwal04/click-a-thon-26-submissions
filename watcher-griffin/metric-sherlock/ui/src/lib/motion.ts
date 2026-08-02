/* Motion primitives.
 *
 * Two rules govern everything here:
 *
 * 1. REVEAL ONCE. A scroll animation that replays every time an element re-enters the
 *    viewport is nauseating on a page you scroll up and down while working, and this is
 *    a monitoring console — people scan it repeatedly. Every observer unsubscribes after
 *    it fires.
 *
 * 2. REDUCED MOTION MEANS NO MOTION, NOT LESS. When the user has asked for it, elements
 *    start in their final state rather than animating faster. Anything else still moves.
 */

import { useEffect, useRef, useState } from 'react'

export function prefersReducedMotion(): boolean {
  if (typeof window === 'undefined' || !window.matchMedia) return false
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

/** Attach to a section: it reveals once, when it first scrolls into view.
 *
 *  Returns a ref and a boolean. Under reduced motion the boolean starts true, so the
 *  element renders in its final state and never transitions. */
export function useReveal<T extends HTMLElement = HTMLDivElement>(
  options: { threshold?: number; rootMargin?: string } = {},
) {
  const ref = useRef<T | null>(null)
  const [shown, setShown] = useState(() => prefersReducedMotion())

  useEffect(() => {
    if (shown) return
    const el = ref.current
    if (!el) return

    // No IntersectionObserver (old browser, some test environments) means the content
    // must still be visible — failing open is the only acceptable default for a
    // progressive enhancement.
    if (typeof IntersectionObserver === 'undefined') {
      setShown(true)
      return
    }

    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            setShown(true)
            observer.disconnect() // once, never again
          }
        }
      },
      {
        threshold: options.threshold ?? 0.08,
        // Start the reveal slightly before the element is on screen, so it has
        // finished by the time it is actually being read.
        rootMargin: options.rootMargin ?? '0px 0px -8% 0px',
      },
    )
    observer.observe(el)
    return () => observer.disconnect()
  }, [shown, options.threshold, options.rootMargin])

  return { ref, shown }
}

/** Counts a number up to its target on first render.
 *
 *  Used only on the two hero figures. Counting every number on a monitoring screen
 *  would be noise, and worse, it would delay the one thing a reader came for.
 *
 *  Uses requestAnimationFrame with an expo-out ease so it decelerates into the final
 *  value rather than stopping dead. Always lands exactly on `target` — a count-up that
 *  ends at 34.88 when the value is 34.89 would be a fabricated figure. */
export function useCountUp(target: number, durationMs = 900): number {
  const [value, setValue] = useState(() => (prefersReducedMotion() ? target : 0))
  const frame = useRef<number>(0)
  const startedAt = useRef<number>(0)

  useEffect(() => {
    if (prefersReducedMotion() || !Number.isFinite(target)) {
      setValue(target)
      return
    }
    startedAt.current = 0

    const tick = (now: number) => {
      if (!startedAt.current) startedAt.current = now
      const elapsed = now - startedAt.current
      const t = Math.min(1, elapsed / durationMs)
      const eased = 1 - Math.pow(1 - t, 4)
      if (t >= 1) {
        setValue(target) // land exactly, never on a rounded approximation
        return
      }
      setValue(target * eased)
      frame.current = requestAnimationFrame(tick)
    }

    frame.current = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame.current)
  }, [target, durationMs])

  return value
}

/** True once the window has scrolled past `threshold` px.
 *
 *  Drives the header condensing on scroll. Passive listener, and it only re-renders on
 *  the transition rather than on every scroll event. */
export function useScrolled(threshold = 12): boolean {
  const [scrolled, setScrolled] = useState(false)

  useEffect(() => {
    const onScroll = () => {
      const next = window.scrollY > threshold
      setScrolled((prev) => (prev === next ? prev : next))
    }
    onScroll()
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [threshold])

  return scrolled
}

/** Fraction of the page scrolled, 0..1, for the progress hairline under the header. */
export function useScrollProgress(): number {
  const [progress, setProgress] = useState(0)

  useEffect(() => {
    const onScroll = () => {
      const doc = document.documentElement
      const scrollable = doc.scrollHeight - doc.clientHeight
      setProgress(scrollable <= 0 ? 0 : Math.min(1, doc.scrollTop / scrollable))
    }
    onScroll()
    window.addEventListener('scroll', onScroll, { passive: true })
    window.addEventListener('resize', onScroll)
    return () => {
      window.removeEventListener('scroll', onScroll)
      window.removeEventListener('resize', onScroll)
    }
  }, [])

  return progress
}

/** Inline style for a staggered entrance. Index-based delay, capped so a long list
 *  never leaves the reader waiting on the tail. */
export function stagger(index: number, stepMs = 45, capMs = 360): React.CSSProperties {
  return { animationDelay: `${Math.min(index * stepMs, capMs)}ms` }
}
