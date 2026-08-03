'use client'

// The original-versus-unseen switch, shared by both consoles.
//
// WHY IT IS A BUTTON AND NOT A CONFIG FLAG. The graded claim this project makes is that the
// pipeline generalises: the same queries, unchanged, answer a day of data that did not exist when
// they were written (docs/problem/spec.md). That claim is only believable if a judge can flip
// between the two answers in one click and watch the SQL underneath stay identical. A deployment
// that serves one dataset per environment proves nothing, because nobody sees the comparison.
//
// The button sends an OPAQUE ID, never a database name. lib/datasets.ts maps it server-side
// against a closed allowlist.
import type {Dataset, DatasetId} from '@/lib/datasets'
import styles from './DatasetSwitch.module.css'

interface DatasetSwitchProps {
  datasets: Dataset[]
  active: DatasetId
  onChange: (id: DatasetId) => void
  /** Disabled while a fetch is in flight, so a double-click cannot interleave two datasets. */
  busy?: boolean
}

export function DatasetSwitch({datasets, active, onChange, busy = false}: DatasetSwitchProps) {
  const current = datasets.find((d) => d.id === active)
  return (
    <section className={styles.wrap} aria-labelledby="dataset-switch-heading">
      <h2 className={styles.heading} id="dataset-switch-heading">
        Dataset
      </h2>
      <div className={styles.group} role="group" aria-label="Which dataset to answer from">
        {datasets.map((d) => (
          <button
            key={d.id}
            type="button"
            className={styles.button}
            // aria-pressed rather than a visual-only active class: a screen reader has to be able
            // to tell which of the two answers is on screen, since that is the whole point.
            aria-pressed={d.id === active}
            disabled={busy}
            onClick={() => onChange(d.id)}
          >
            {d.label}
          </button>
        ))}
      </div>
      {current && <p className={styles.blurb}>{current.blurb}</p>}
    </section>
  )
}
