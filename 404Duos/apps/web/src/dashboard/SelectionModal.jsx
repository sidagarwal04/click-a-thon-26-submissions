import { useState } from 'react'
import ModalPortal from '../components/ModalPortal.jsx'

export default function SelectionModal({
  title,
  items,
  selected,
  onChange,
  onClose,
  searchPlaceholder = 'Search…',
}) {
  const [local, setLocal] = useState(selected)
  const [q, setQ] = useState('')

  const filtered = items.filter((item) => {
    const hay = `${item.id} ${item.label}`.toLowerCase()
    return hay.includes(q.trim().toLowerCase())
  })

  function toggle(id) {
    setLocal((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]))
  }

  return (
    <ModalPortal>
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <div
        className="modal-card panel"
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-header">
          <h2 className="panel-title">{title}</h2>
          <button type="button" className="btn" onClick={onClose}>
            Close
          </button>
        </div>
        <div className="modal-body">
          <input
            className="dash-input"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder={searchPlaceholder}
          />
          <div className="modal-actions-row">
            <button
              type="button"
              className="btn"
              onClick={() => setLocal(filtered.map((i) => i.id))}
            >
              Select all
            </button>
            <button type="button" className="btn" onClick={() => setLocal([])}>
              Clear
            </button>
            <span className="muted mono" style={{ marginLeft: 'auto' }}>
              {local.length} selected
            </span>
          </div>
          <ul className="check-list">
            {filtered.map((item) => (
              <li key={item.id}>
                <label className="check-row">
                  <input
                    type="checkbox"
                    checked={local.includes(item.id)}
                    onChange={() => toggle(item.id)}
                  />
                  <span>{item.label}</span>
                  <span className="mono muted">{item.id}</span>
                </label>
              </li>
            ))}
          </ul>
        </div>
        <div className="modal-footer">
          <button type="button" className="btn" onClick={onClose}>
            Cancel
          </button>
          <button
            type="button"
            className="btn btn-primary"
            disabled={local.length === 0}
            onClick={() => {
              onChange(local)
              onClose()
            }}
          >
            Apply
          </button>
        </div>
      </div>
    </div>
    </ModalPortal>
  )
}
