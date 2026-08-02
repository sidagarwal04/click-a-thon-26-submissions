import { Link, Route, Routes, useLocation } from 'react-router-dom'

import DatasetSwitcher from './components/DatasetSwitcher'
import { useDataset } from './lib/dataset'
import { useScrollProgress, useScrolled } from './lib/motion'
import IncidentDetail from './pages/IncidentDetail'
import OpsHome from './pages/OpsHome'
import { InvestigationDetail } from './pages/InvestigationDetail'

/* The header condenses on scroll — the wordmark shrinks and the strapline drops away, so a
 * long page keeps its navigation without spending a fifth of the viewport on it. The
 * hairline underneath tracks scroll position: on a page this tall it is genuinely useful
 * orientation, not decoration. */
function Header() {
  const scrolled = useScrolled(16)
  const progress = useScrollProgress()
  const { pathname } = useLocation()
  const onHome = pathname === '/'

  return (
    <header className={`chrome${scrolled ? ' chrome-condensed' : ''}`}>
      <div className="chrome-inner">
        {/* Wordmark only, no glyph. Two-tone is kept from the previous mark because it is
            what makes a plain string read as a logo rather than as a heading. */}
        <Link to="/" className="wordmark">
          <span className="wordmark-text">
            Metric <span className="wordmark-light">Sherlock</span>
          </span>
        </Link>

        {/* Nav and the dataset switcher share grid column 2, right-aligned, so
            `.chrome-inner`'s `auto 1fr` columns and `.chrome-strap`'s `grid-column: 1/-1`
            stay exactly as they were. The switcher renders on every route including home,
            where there is no nav -- the reader needs to know which world they are looking
            at more on the landing screen than anywhere else. */}
        <div className="chrome-right">
          {!onHome && (
            <nav className="chrome-nav" aria-label="Sections">
              <Link to="/">Operations</Link>
            </nav>
          )}
          <DatasetSwitcher />
        </div>

        <p className="chrome-strap">
          From Alert to Answer — Find the Why. Prove the Cause.
        </p>
      </div>
      <div
        className="chrome-progress"
        style={{ transform: `scaleX(${progress})` }}
        aria-hidden="true"
      />
    </header>
  )
}

function App() {
  const dataset = useDataset()

  return (
    <div className="shell">
      <Header />
      {/* REMOUNTING ON A DATASET CHANGE IS WHAT MAKES THE SWITCH TAKE EFFECT.
          usePolling deliberately holds its fetcher in a ref with a `[]`-dep `run`, so a
          changed dataset would not refetch until the next tick -- up to 30s of the previous
          dataset's numbers under the new dataset's label, which is the worst available
          failure for this control. Keying the subtree also discards local state that does
          not survive the change: an open chat transcript, the funnel's picked stage, and
          any incident id, since ids do not exist across datasets. */}
      <main className="shell-main" key={dataset}>
        <Routes>
          <Route path="/" element={<OpsHome />} />
          <Route path="/incidents/:id" element={<IncidentDetail />} />
          {/* Kept so a stored investigation id still resolves. The old Dashboard route is
              gone: its metric dropdown and two date pickers were the interaction this
              redesign removed. */}
          <Route path="/investigations/:id" element={<InvestigationDetail />} />
          <Route
            path="*"
            element={
              <div className="panel">
                <h2>Not found</h2>
                <p className="muted-note">
                  That page does not exist. <Link to="/">Back to operations</Link>.
                </p>
              </div>
            }
          />
        </Routes>
      </main>
    </div>
  )
}

export default App
