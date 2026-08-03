/* The one control in the header: which dataset the whole console is reading.
 *
 * IT IS ALLOWED ON A PAGE THAT OTHERWISE ASKS FOR NOTHING.
 * The operations screen deliberately has zero form inputs -- no metric picker, no date
 * range -- because the system already knows what moved and when. This control does not
 * break that rule, because it does not ask the operator to specify an ANALYSIS. It selects
 * which body of data is being monitored, which is a fact about the deployment that nothing
 * can infer: the two datasets are separate worlds that reuse the same identifiers, so there
 * is no correct default beyond "the primary one".
 *
 * OPTIONS COME FROM THE SERVER, NEVER FROM A LITERAL HERE.
 * Each label carries the dataset's own date range and row count, read from
 * /api/datasets. A hardcoded "Jul 6 - Jul 10" would be a claim about data this file
 * cannot see, and the first thing to go stale when a new drop is loaded.
 *
 * A dataset that has never been swept is marked rather than hidden. Hiding it would make
 * an unprovisioned deployment look like it has one dataset; showing it unmarked would make
 * an empty dashboard look like a calm one.
 */

import { useEffect } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'

import { listDatasets } from '../api/client'
import { usePolling } from '../hooks/usePolling'
import { reconcile, setDataset, useDataset } from '../lib/dataset'
import { count, dayRange } from '../lib/format'

/** The registry only changes when a dataset is loaded or swept, so this is not on the 30s
 *  loop -- but it is polled rather than fetched once so `provisioned` and the incident
 *  counts catch up after a sweep without a page reload. */
const POLL_MS = 120_000

export default function DatasetSwitcher() {
  const selected = useDataset()
  const { data } = usePolling(listDatasets, POLL_MS)
  const navigate = useNavigate()
  const { pathname } = useLocation()

  /* Switching dataset while on a per-entity page has to leave that page: incident and
   * investigation ids are UUIDs minted per dataset, so the same id never exists in both,
   * and staying put would render a 404 that reads as "this incident was deleted" rather
   * than "you are looking at different data now".
   *
   * Done HERE, in the click handler, rather than in an effect watching the dataset in
   * App. That effect was a real bug and not a subtle one: `useNavigate`'s identity is not
   * guaranteed stable across a location change, so the effect re-ran on ordinary
   * navigation, saw the new `/incidents/:id` path, and bounced straight back to home --
   * incident pages could not be opened at all. Navigation belongs at the point of intent,
   * where there is no dependency array to get wrong. */
  function select(key: string) {
    if (key === selected) return
    setDataset(key)
    if (/^\/(incidents|investigations)\//.test(pathname)) {
      navigate('/', { replace: true })
    }
  }

  // Self-heal a selection the server does not recognise (a renamed dataset, a
  // hand-edited URL, a stale localStorage value). Without this every request 400s
  // forever with no way back except clearing site data.
  useEffect(() => {
    if (data) reconcile(data.datasets.map((d) => d.key), data.default)
  }, [data])

  // Before the registry arrives there is nothing honest to render: the current key is
  // known but its label, span and row count are not, and inventing them is the one thing
  // this component must not do. The header simply has no control for that moment.
  if (!data || data.datasets.length < 2) return null

  return (
    <div className="dsw" role="group" aria-label="Dataset">
      <span className="dsw-label" aria-hidden="true">
        Data
      </span>
      {data.datasets.map((d) => {
        const active = d.key === selected
        // dayRange returns an em dash for a missing bound, which is truthy -- so the
        // presence check is on the inputs, not on its output. A chip that reads
        // "Primary —" would look like a rendering bug rather than absent metadata.
        const span =
          d.min_event_time && d.max_event_time
            ? dayRange(d.min_event_time, d.max_event_time)
            : ''
        // Everything a reader needs to know why the numbers differ, without a second click.
        const title = [
          d.label,
          d.database,
          span,
          d.total_rows != null ? `${count(d.total_rows)} events` : null,
          d.provisioned
            ? `${count(d.incidents ?? 0)} incident(s) from ${count(d.sweeps ?? 0)} sweep(s)`
            : 'not swept yet -- no bands built, so nothing can be detected',
          d.note,
        ]
          .filter(Boolean)
          .join(' · ')

        return (
          <button
            key={d.key}
            type="button"
            className={`pill dsw-pill${active ? ' pill-active' : ''}`}
            aria-pressed={active}
            disabled={!d.available}
            title={d.available ? title : `${d.label} is unreachable: ${d.error ?? 'unknown error'}`}
            onClick={() => select(d.key)}
          >
            {d.label}
            {span && <span className="dsw-span">{span}</span>}
            {/* Marked, not hidden: an unprovisioned dataset renders an empty console, and
                an empty console that does not explain itself reads as "all clear". */}
            {d.available && !d.provisioned && (
              <span className="dsw-flag" title="No baselines built yet">
                not swept
              </span>
            )}
            {!d.available && <span className="dsw-flag">unreachable</span>}
          </button>
        )
      })}
    </div>
  )
}
