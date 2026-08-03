import { useEffect, useState } from 'react'
import ModalPortal from '../components/ModalPortal.jsx'
import { getDashboardFilterValues } from '../api/client.js'
import { dimensionLabel } from './config.js'

export default function FiltersModal({
  meta,
  filters,
  onChange,
  onClose,
  start,
  end,
}) {
  const dims = meta?.dimensions || []
  const [panel, setPanel] = useState(dims[0]?.id || 'ad_format')
  const [values, setValues] = useState([])
  const [loading, setLoading] = useState(false)
  const [local, setLocal] = useState(filters || {})
  const [q, setQ] = useState('')

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      setLoading(true)
      try {
        const vals = await getDashboardFilterValues({ dimension: panel, start, end })
        if (!cancelled) setValues(vals)
      } catch {
        if (!cancelled) setValues([])
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [panel, start, end])

  const selected = local[panel] || []
  const filtered = values.filter((v) => v.toLowerCase().includes(q.trim().toLowerCase()))

  function toggleValue(v) {
    setLocal((prev) => {
      const cur = prev[panel] || []
      const next = cur.includes(v) ? cur.filter((x) => x !== v) : [...cur, v]
      const copy = { ...prev }
      if (next.length === 0) delete copy[panel]
      else copy[panel] = next
      return copy
    })
  }

  return (
    <ModalPortal>
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <div className="modal-card panel modal-wide" role="dialog" aria-modal="true" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2 className="panel-title">Filters</h2>
          <button type="button" className="btn" onClick={onClose}>
            Close
          </button>
        </div>
        <div className="modal-body filters-layout">
          <aside className="filter-panels">
            {dims.map((d) => (
              <button
                key={d.id}
                type="button"
                className={`filter-panel-btn ${(local[d.id] || []).length ? 'has-values' : ''} ${panel === d.id ? 'is-active' : ''}`}
                onClick={() => {
                  setPanel(d.id)
                  setQ('')
                }}
              >
                <span>{d.label}</span>
                {(local[d.id] || []).length ? (
                  <span className="mono">{local[d.id].length}</span>
                ) : null}
              </button>
            ))}
          </aside>
          <div className="filter-values">
            <div className="modal-actions-row">
              <strong>{dimensionLabel(meta, panel)}</strong>
              <input
                className="dash-input"
                style={{ maxWidth: '14rem' }}
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder="Search values…"
              />
            </div>
            {loading ? (
              <p className="muted">Loading values…</p>
            ) : (
              <ul className="check-list">
                {filtered.map((v) => (
                  <li key={v}>
                    <label className="check-row">
                      <input
                        type="checkbox"
                        checked={selected.includes(v)}
                        onChange={() => toggleValue(v)}
                      />
                      <span>{v}</span>
                    </label>
                  </li>
                ))}
                {filtered.length === 0 ? <li className="muted">No values</li> : null}
              </ul>
            )}
          </div>
        </div>
        <div className="modal-footer">
          <button
            type="button"
            className="btn"
            onClick={() => setLocal({})}
          >
            Clear all
          </button>
          <button type="button" className="btn" onClick={onClose}>
            Cancel
          </button>
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => {
              onChange(local)
              onClose()
            }}
          >
            Apply filters
          </button>
        </div>
      </div>
    </div>
    </ModalPortal>
  )
}
