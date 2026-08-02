/* Owner badge: which team acts on this.
 *
 * This is the business-logic bridge. A metric moving is an observation; a team that
 * owns it is a next step. The owner is derived deterministically — either from the
 * signature rule that matched, or, when no mechanism matched, from the metric itself
 * (fill is demand, show rate is engineering, eCPM is pricing, requests is growth, CTR
 * is creative). So even an unexplained breach still routes somewhere, which is the
 * point: "we don't know why" should not mean "nobody looks at it".
 *
 * Coloured from the categorical series palette rather than the status palette, so the
 * badge never implies that one team's problem is more severe than another's.
 */

import { OWNER_ACTION, ownerColor } from '../lib/status'

interface Props {
  owner: string
  showAction?: boolean
}

export default function OwnerBadge({ owner, showAction = false }: Props) {
  const color = ownerColor(owner)
  const action = OWNER_ACTION[owner] ?? OWNER_ACTION.unassigned

  return (
    <span className="owner-wrap">
      <span
        className="owner-badge"
        style={{ borderColor: color, color }}
        title={action}
      >
        {owner}
      </span>
      {showAction && <span className="owner-action">{action}</span>}
    </span>
  )
}
