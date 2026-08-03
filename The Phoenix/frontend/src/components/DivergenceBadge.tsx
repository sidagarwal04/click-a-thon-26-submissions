'use client'

import styles from './DivergenceBadge.module.css'

interface Props {
  sessionPeak: number
  userPeak: number
  sessionReach: number
  userReach: number
}

/**
 * Compare-mode readout. Session count and user count are genuinely different questions, one
 * viewer open on a phone and a TV is two sessions and one person, so this frames the gap as a
 * device multiplier rather than an error, per the problem statement's session-independent view.
 *
 * Two multipliers, not one: peak-to-peak is a single instant and the two peaks can fall on
 * different minutes, while reach-to-reach compares total sessions vs. total users touched
 * anywhere across the whole window, a steadier read on "devices per viewer".
 */
export default function DivergenceBadge({sessionPeak, userPeak, sessionReach, userReach}: Props) {
  const gap = userPeak > 0 ? ((sessionPeak - userPeak) / userPeak) * 100 : 0
  const multiplier = userPeak > 0 ? sessionPeak / userPeak : 1
  const reachMultiplier = userReach > 0 ? sessionReach / userReach : 1

  return (
    <div className={`${styles.badge} corner-ticks`}>
      <span className="mono-label">Sessions vs. users</span>
      <div className={styles.row}>
        <b className={styles.gap}>{gap >= 0 ? '+' : ''}{gap.toFixed(1)}%</b>
        <span className={styles.detail}>
          {multiplier.toFixed(2)}&times; sessions per concurrent viewer at peak, the same person,
          watching on more than one device, is not double-counted in Users mode.
        </span>
      </div>
      <div className={styles.row}>
        <b className={styles.gap}>{reachMultiplier.toFixed(2)}&times;</b>
        <span className={styles.detail}>
          sessions per viewer reached across the whole window ({sessionReach} sessions /{' '}
          {userReach} users), steadier than the peak ratio since it isn't tied to one minute.
        </span>
      </div>
    </div>
  )
}
