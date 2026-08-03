'use client'

import styles from './StatReadout.module.css'

interface Props {
  label: string
  value: string
  accent?: 'signal' | 'cool' | 'neutral'
  size?: 'lg' | 'md'
  /** 'panel' (default) is one segment of the corner-ticked instrument strip its parent group
   *  renders, it owns no border of its own, only its accent-colored top cap, so a row of
   *  these reads as one meter cluster rather than a grid of separate cards. 'inline' is a
   *  compact label:value pill for secondary/diagnostic readouts (query latency, rows read)
   *  that shouldn't compete visually with the metrics a viewer actually came here to read. */
  variant?: 'panel' | 'inline'
}

/** A single big-number instrument segment, the console's equivalent of a VU meter readout. */
export default function StatReadout({label, value, accent = 'neutral', size = 'md', variant = 'panel'}: Props) {
  if (variant === 'inline') {
    return (
      <div className={styles.inline}>
        <span className={`mono-label ${styles.inlineLabel}`}>{label}</span>
        <b className={styles.inlineValue}>{value}</b>
      </div>
    )
  }
  const accentClass = accent !== 'neutral' ? styles[accent] : ''
  return (
    <div className={`${styles.readout} ${accentClass}`}>
      <b className={`${styles.value} ${size === 'lg' ? styles.lg : ''}`}>{value}</b>
      <span className={`mono-label ${styles.label}`}>{label}</span>
    </div>
  )
}
