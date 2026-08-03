import InsightConsole from './InsightConsole'
import './tokens.css'
import styles from './console.module.css'

export const metadata = {
  title: 'PHOENIX Insights // Audience Intelligence',
  description: 'Why concurrency moved, who moved with it, and whether they stayed.',
}

/**
 * The v2 console, reading the insight layer in phoenix_next.
 *
 * A SEPARATE ROUTE, not a tab on the v1 console: the data is a different generation living in a
 * different database, and keeping them apart means the validated concurrency console cannot
 * regress because of anything done here. The look is v1's, though. tokens.css aliases every v2
 * token onto the globals.css palette, so both consoles read as one product.
 */
export default function V2Page() {
  return (
    <div className={`v2 ${styles.page}`}>
      <InsightConsole/>
    </div>
  )
}
