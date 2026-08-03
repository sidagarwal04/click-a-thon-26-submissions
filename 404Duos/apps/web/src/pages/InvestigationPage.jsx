import { useEffect, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { exportInvestigationBundle, getInvestigation } from '../api/client.js'
import AskInChatButton from '../components/AskInChatButton.jsx'
import CounterfactualCard from '../components/CounterfactualCard.jsx'
import DiagnosisCard from '../components/DiagnosisCard.jsx'
import HypothesesPanel from '../components/HypothesesPanel.jsx'
import MetricTree from '../components/MetricTree.jsx'
import SeasonalityPanel from '../components/SeasonalityPanel.jsx'
import SegmentTable from '../components/SegmentTable.jsx'
import StatusPill from '../components/StatusPill.jsx'
import TraceTimeline from '../components/TraceTimeline.jsx'
import {
  formatAlertViewBaseline,
  formatAlertViewWindow,
  formatMetric,
} from '../utils/format.js'

export default function InvestigationPage() {
  const { investigationId } = useParams()
  const [searchParams] = useSearchParams()
  const view = searchParams.get('view') === 'day' ? 'day' : 'hour'
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)
  const [exporting, setExporting] = useState(false)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    ;(async () => {
      try {
        const inv = await getInvestigation(investigationId)
        if (!cancelled) setData(inv)
      } catch (err) {
        if (!cancelled) setError(err.message || 'Failed to load investigation')
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [investigationId])

  async function onExport() {
    if (!data?.id || exporting) return
    setExporting(true)
    try {
      const bundle = await exportInvestigationBundle(data.id)
      if (!bundle.evidenceHash && !bundle.evidence?.hash) {
        console.warn('Export missing evidenceHash')
      }
      const blob = new Blob([JSON.stringify(bundle, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${data.id}-export.json`
      a.click()
      URL.revokeObjectURL(url)
    } catch (err) {
      setError(err.message || 'Export failed')
    } finally {
      setExporting(false)
    }
  }

  if (loading) return <div className="loading">Running investigation…</div>
  if (error && !data) return <div className="error-box">{error}</div>
  if (!data) return null

  const {
    alert,
    decomposition,
    segments,
    ruledOut = [],
    diagnosis,
    trace,
    seasonality,
    waterfall = [],
    counterfactual,
    hypotheses = [],
    evidence,
  } = data

  return (
    <div className="investigation">
      <div className="inv-nav">
        <Link to="/alerts" className="back-link muted">
          ← Alerts
        </Link>
        <div className="inv-nav-actions">
          <button type="button" className="btn" onClick={onExport} disabled={exporting}>
            {exporting ? 'Exporting…' : 'Export evidence'}
          </button>
          <AskInChatButton
            alertId={alert.id}
            investigationId={data.id}
            question={`Why did ${formatMetric(alert.metric)} move ${alert.pctChange}% on ${alert.windowStart.slice(0, 10)}? Use investigation ${data.id}.`}
          />
        </div>
      </div>

      {error ? <div className="error-box">{error}</div> : null}

      <header className="inv-header panel fade-in">
        <div>
          <div className="inv-title-row">
            <h1 className="page-title" style={{ marginBottom: 0 }}>
              {formatMetric(alert.metric)} {alert.direction === 'down' ? '↓' : '↑'}{' '}
              {Math.abs(alert.pctChange).toFixed(1)}%
            </h1>
            <StatusPill status={alert.severity}>{alert.severity}</StatusPill>
            <StatusPill status={data.status}>{data.status}</StatusPill>
            {seasonality?.status === 'ruled_out_as_seasonality' ? (
              <StatusPill status="info">seasonality — not an incident</StatusPill>
            ) : null}
          </div>
          <p className="inv-window mono muted">{formatAlertViewWindow(alert, view)}</p>
          <p
            className="muted"
            style={{ margin: '0.35rem 0 0' }}
            title={formatAlertViewBaseline(alert, view).hint}
          >
            Compared {formatAlertViewBaseline(alert, view).label}
          </p>
        </div>
      </header>

      <div className="grid-2" style={{ marginTop: '1rem' }}>
        <section className="panel">
          <div className="panel-header">
            <h2 className="panel-title">Metric tree</h2>
            <span className="muted" style={{ fontSize: '0.8rem' }}>
              Identity walk + $ contribution
            </span>
          </div>
          <div className="panel-body">
            <MetricTree decomposition={decomposition} waterfall={waterfall} />
          </div>
        </section>

        <section className="panel">
          <div className="panel-header">
            <h2 className="panel-title">Diagnosis</h2>
          </div>
          <div className="panel-body">
            <DiagnosisCard diagnosis={diagnosis} evidence={evidence} />
            <CounterfactualCard counterfactual={counterfactual} />
            <HypothesesPanel hypotheses={hypotheses} />
          </div>
        </section>
      </div>

      <div className="grid-2" style={{ marginTop: '1rem' }}>
        <section className="panel">
          <div className="panel-header">
            <h2 className="panel-title">Dimension drill-down</h2>
          </div>
          <div className="panel-body">
            <SegmentTable segments={segments} />
          </div>
        </section>

        <div className="grid-stack">
          <section className="panel">
            <div className="panel-header">
              <h2 className="panel-title">Seasonality</h2>
            </div>
            <div className="panel-body">
              <SeasonalityPanel seasonality={seasonality} />
            </div>
          </section>

          <section className="panel">
            <div className="panel-header">
              <h2 className="panel-title">Ruled out</h2>
            </div>
            <div className="panel-body">
              {ruledOut.length === 0 ? (
                <p className="muted">Still checking…</p>
              ) : (
                <ul className="ruled-list">
                  {ruledOut.map((item) => (
                    <li key={item.reason}>
                      <strong>{item.reason}</strong>
                      <p className="muted">{item.detail}</p>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </section>

          <section className="panel">
            <div className="panel-header">
              <h2 className="panel-title">Investigation trace</h2>
            </div>
            <div className="panel-body">
              <TraceTimeline trace={trace} />
            </div>
          </section>
        </div>
      </div>
    </div>
  )
}
