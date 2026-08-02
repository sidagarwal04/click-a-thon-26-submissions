/* Scroll-reveal wrapper.
 *
 * Reveals its children once, when the section first enters the viewport, then stops
 * observing. Deliberately not a repeating animation: this is a console people scroll up
 * and down while working, and content that re-animates every pass is actively unpleasant.
 *
 * Under reduced motion `useReveal` returns shown=true immediately, so the section renders
 * in its final state and never transitions.
 */

import type { ReactNode } from 'react'

import { useReveal } from '../lib/motion'

interface Props {
  children: ReactNode
  /** Extra delay in ms, for orchestrating a few siblings into a sequence. */
  delay?: number
  className?: string
  as?: 'div' | 'section'
}

export default function Reveal({ children, delay = 0, className = '', as = 'section' }: Props) {
  const { ref, shown } = useReveal<HTMLElement>()
  const Tag = as as 'section'

  return (
    <Tag
      ref={ref as React.Ref<HTMLElement>}
      className={`reveal${shown ? ' reveal-in' : ''} ${className}`.trim()}
      style={delay ? { transitionDelay: `${delay}ms` } : undefined}
    >
      {children}
    </Tag>
  )
}
