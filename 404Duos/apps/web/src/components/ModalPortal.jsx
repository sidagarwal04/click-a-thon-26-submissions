import { useEffect } from 'react'
import { createPortal } from 'react-dom'

/** Render children in document.body so page transforms don't break position:fixed. */
export default function ModalPortal({ children }) {
  useEffect(() => {
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = prev
    }
  }, [])

  if (typeof document === 'undefined') return null
  return createPortal(children, document.body)
}
