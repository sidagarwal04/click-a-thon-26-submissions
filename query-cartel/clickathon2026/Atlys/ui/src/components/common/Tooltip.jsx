import { useId } from 'react'

/**
 * Lightweight styled tooltip — wraps any (ideally non-interactive) element and
 * shows rich content on hover / keyboard focus. Pure CSS positioning, no deps.
 *
 * Usage:
 *   <Tooltip content="What this is / why it matters" position="top|bottom|left|right">
 *     <span className="my-chip">…</span>
 *   </Tooltip>
 *
 * `content` may be a string or JSX. The wrapper is focusable so keyboard users
 * get the same info (it's an informational hint, not an interactive control).
 */
export default function Tooltip({ content, position = 'top', children, className = '', wide = false, focusable = true }) {
  const id = useId()
  if (content == null || content === '') return <>{children}</>
  return (
    <span
      className={`tooltip-wrap ${className}`}
      tabIndex={focusable ? 0 : undefined}
      aria-describedby={id}
    >
      {children}
      <span
        className={`tooltip-bubble tooltip-${position}${wide ? ' tooltip-wide' : ''}`}
        role="tooltip"
        id={id}
      >
        {content}
      </span>
    </span>
  )
}
