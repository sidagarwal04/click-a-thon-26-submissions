import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { evaluateSeasonality } from './rca.js'

function bag({ revenue = 0, requests = 1000 } = {}) {
  return { requests, fills: requests * 0.8, impressions: requests * 0.7, clicks: 10, revenue }
}

describe('evaluateSeasonality', () => {
  it('rules out weekend-like drops that look bad vs a naive average but match same-weekday baseline', () => {
    // Saturday softness: ~20% below mixed trailing week, ~1% vs prior Saturdays.
    const observed = bag({ revenue: 80 })
    const seasonal = bag({ revenue: 81 })
    const naive = bag({ revenue: 100 })
    const out = evaluateSeasonality('revenue', observed, seasonal, naive)
    assert.equal(out.status, 'ruled_out_as_seasonality')
    assert.ok(Math.abs(out.flatDeltaPct) >= 5)
    assert.ok(Math.abs(out.seasonalDeltaPct) < 3)
    assert.match(out.detail, /seasonality/i)
  })

  it('keeps residual when like-for-like baseline still shows a real move', () => {
    const observed = bag({ revenue: 70 })
    const seasonal = bag({ revenue: 100 })
    const naive = bag({ revenue: 105 })
    const out = evaluateSeasonality('revenue', observed, seasonal, naive)
    assert.equal(out.status, 'residual_remains')
    assert.ok(Math.abs(out.seasonalDeltaPct) >= 5)
  })

  it('ignores a misleading caller-supplied pct (alerts_live flat expectation)', () => {
    const observed = bag({ revenue: 80 })
    const seasonal = bag({ revenue: 81 })
    const naive = bag({ revenue: 100 })
    // Old bug: large live pct was treated as the seasonal residual.
    const out = evaluateSeasonality('revenue', observed, seasonal, naive, -45)
    assert.equal(out.status, 'ruled_out_as_seasonality')
  })

  it('skips when both naive and seasonal residuals are within noise', () => {
    const observed = bag({ revenue: 100 })
    const seasonal = bag({ revenue: 101 })
    const naive = bag({ revenue: 102 })
    const out = evaluateSeasonality('revenue', observed, seasonal, naive)
    assert.equal(out.status, 'skipped')
  })
})
