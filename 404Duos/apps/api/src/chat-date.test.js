import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { parseDateWindowFromText, parseOneDayToken } from './chatDates.js'

describe('parseOneDayToken', () => {
  it('parses 22June without space or year', () => {
    assert.equal(parseOneDayToken('How is APAC revenue on 22June?', 2026), '2026-06-22')
  })
  it('parses 22 June without year', () => {
    assert.equal(parseOneDayToken('APAC revenue on 22 June', 2026), '2026-06-22')
  })
  it('parses June 22 without year', () => {
    assert.equal(parseOneDayToken('June22 APAC', 2026), '2026-06-22')
  })
  it('parses full year forms', () => {
    assert.equal(parseOneDayToken('21 June 2026'), '2026-06-21')
  })
})

describe('parseDateWindowFromText', () => {
  it('builds a single-day window for 22June', () => {
    const w = parseDateWindowFromText('How is APAC revenue on 22June?', 2026)
    assert.equal(w.start, '2026-06-22T00:00:00.000Z')
    assert.equal(w.end, '2026-06-22T23:59:59.000Z')
  })
})
