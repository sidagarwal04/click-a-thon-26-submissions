/* The revenue funnel: one selector, one chart, one stage's evidence.
 *
 * WHAT THIS REPLACED, AND WHY
 * This was six stacked cards, each with its own 76px sparkline and its own collapsed
 * evidence block. It was honest and it was unreadable: roughly six screens of scrolling for
 * a section whose entire job is to say which of five stages moved the money, which pushed
 * the incident queue and the trace below the fold. Six small charts also meant no chart was
 * big enough to read — the band, which is the one mark the product exists to show, was a
 * smudge a few pixels tall.
 *
 * One chart at 280px with axes shows the corridor properly, and the six statuses survive as
 * dots on the selector (see MetricSelector). Nothing was removed: the meaning, the reason,
 * the grain ladder and the source query all still render, for the selected stage.
 *
 * WHY SELECTION IS DERIVED, NOT SYNCED
 * The page polls every 30s, so `tree` is a brand-new object six times a minute. Syncing the
 * default into state with an effect would reset the reader's choice on every tick — they
 * would click "Fill rate", read for twenty seconds, and be thrown back to Revenue. So state
 * holds only what the reader explicitly picked, and the effective metric is derived: their
 * pick if it still exists, otherwise the engine's own driver.
 */

import { useCallback, useMemo, useState } from 'react'

import { formatDeviation, resolveMetricFormat } from '../lib/metricConfig'
import { statusStyle } from '../lib/status'
import type { MetricTree, TreeNode } from '../types'
import GrainLadder from './GrainLadder'
import MetricSelector from './MetricSelector'
import type { MetricOption } from './MetricSelector'
import MetricTrendChart from './MetricTrendChart'

const PANEL_ID = 'metric-trend-panel'

/** What the reader sees before touching anything: the stage the engine blamed, falling back
 *  to the root of the identity. The page must answer its question with nothing clicked. */
function defaultMetric(nodes: TreeNode[]): string {
  return (
    nodes.find((n) => n.is_driver)?.metric ??
    nodes.find((n) => n.role === 'root')?.metric ??
    nodes[0]?.metric ??
    ''
  )
}

interface Props {
  tree: MetricTree
}

export default function RevenueFunnel({ tree }: Props) {
  const nodes = tree.nodes
  const [picked, setPicked] = useState<string | null>(null)

  const fallback = useMemo(() => defaultMetric(nodes), [nodes])
  const selected = picked !== null && nodes.some((n) => n.metric === picked) ? picked : fallback

  const items: MetricOption[] = useMemo(
    () =>
      nodes.map((n) => {
        const st = statusStyle(n.status)
        return {
          key: n.metric,
          label: n.label,
          statusColor: st.color,
          statusLabel: st.label,
        }
      }),
    [nodes],
  )

  const onSelect = useCallback((key: string) => setPicked(key), [])

  const node = nodes.find((n) => n.metric === selected)
  if (!node) {
    return <p className="muted-note">No funnel stages were evaluated in the latest sweep.</p>
  }

  const st = statusStyle(node.status)
  const fmt = resolveMetricFormat(node.metric, node.unit)
  const meaning = tree.meanings?.[node.metric]

  return (
    <div className="mts">
      <MetricSelector
        items={items}
        selected={selected}
        onSelect={onSelect}
        panelId={PANEL_ID}
      />

      <MetricTrendChart
        metricKey={node.metric}
        title={node.label}
        points={node.series}
        unit={node.unit}
        formatValue={fmt.formatValue}
        currentValue={node.value}
        expectedValue={node.center}
        deviation={formatDeviation(node, fmt)}
        statusColor={st.color}
        statusLabel={st.label}
        notable={node.status === 'red' || node.status === 'amber'}
        isDriver={node.is_driver}
        accentToken={fmt.accentToken}
        panelId={PANEL_ID}
      >
        {meaning && <p className="fnl-meaning">{meaning}</p>}

        {node.status === 'not_judgeable' && (
          <p className="fnl-nojudge" title={node.reason}>
            Not enough data to judge — deliberately not reported as healthy.
          </p>
        )}

        {/* Everything a sceptic needs, and nothing a scanner does. Collapsed by default.
            The source query line is not optional: a claim a judge cannot re-run is not
            evidence. */}
        <details className="fnl-why">
          <summary>Why {st.label.toLowerCase()}, and across which time frames</summary>
          <p className="fnl-reason">{node.reason}</p>
          <GrainLadder cells={node.grain_ladder} />
          <p className="source-note">
            <code>{node.source_step}</code>
            {node.baseline_method ? ` · ${node.baseline_method}` : ''}
            {node.sample_count ? ` · ${node.sample_count} comparable windows` : ''}
            {node.seasonal_cell ? ` · compared against ${node.seasonal_cell}` : ''}
          </p>
        </details>
      </MetricTrendChart>
    </div>
  )
}
