/* What to do next — assembled, not authored.
 *
 * NOTHING HERE IS ADVICE THE SYSTEM INVENTED
 * Every line is a restatement of something already computed and already on this page: the
 * owner's standing action from the rule table, the mechanism sentence, the segments carrying
 * the largest measured share of the exposure, and the alternatives the engine already tested.
 * The language model is not consulted, because recommendations are not in the evidence
 * bundle — and a model asked for advice it has no evidence for will produce some anyway.
 *
 * The "already ruled out" list is the most valuable part and the least obvious: it stops the
 * reader spending the first twenty minutes re-checking seasonality that the engine cleared
 * before the incident was ever raised.
 *
 * The post-mortem verdict lives here because recording the outcome IS the last step — it is
 * what eventually lets the band thresholds be tuned from evidence instead of judgement.
 */

import { usd } from '../lib/format'
import { scopeValue } from '../lib/format'
import { OWNER_ACTION } from '../lib/status'
import type { IncidentDetail } from '../types'

/** How many contributing segments to name as a starting point. Two, because a list of
 *  "start here" items long enough to need scanning is not a starting point. */
const START_WITH = 2

interface Props {
  detail: IncidentDetail
}

export default function Recommendations({ detail: d }: Props) {
  const action = OWNER_ACTION[d.owner] ?? OWNER_ACTION.unassigned
  const parts = d.impact_breakdown?.parts?.slice(0, START_WITH) ?? []

  return (
    <div className="rec">
      <ol className="rec-list">
        <li>
          <span className="rec-step">Owner</span>
          <span>
            <strong>{d.owner || 'unassigned'}</strong> — {action}
          </span>
        </li>

        {parts.length > 0 && (
          <li>
            <span className="rec-step">Start with</span>
            <span>
              {parts.map((p, i) => (
                <span key={`${p.scope_type}-${p.scope_value}-${i}`}>
                  {i > 0 && ', then '}
                  <strong>{scopeValue(p.scope_value)}</strong>{' '}
                  <span className="muted-inline">
                    ({p.scope_type}, {usd(Math.abs(p.impact_usd))},{' '}
                    {(p.share_of_impact * 100).toFixed(0)}% of exposure)
                  </span>
                </span>
              ))}
            </span>
          </li>
        )}

        {d.mechanism && (
          <li>
            <span className="rec-step">Because</span>
            <span>{d.mechanism}</span>
          </li>
        )}

        {d.ruled_out && d.ruled_out.length > 0 && (
          <li>
            <span className="rec-step">Do not re-check</span>
            <span>
              These were tested and cleared before this was raised:
              <ul className="rec-ruled">
                {d.ruled_out.map((r) => (
                  <li key={r.check}>
                    <strong>{r.check}</strong> — {r.reason}
                  </li>
                ))}
              </ul>
            </span>
          </li>
        )}
      </ol>

    </div>
  )
}
