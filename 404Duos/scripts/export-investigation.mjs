#!/usr/bin/env node
/**
 * Investigation evidence export CLI
 *
 *   node scripts/export-investigation.mjs --list
 *   node scripts/export-investigation.mjs --alertId=<UUID> --out=./exports
 *   node scripts/export-investigation.mjs --investigationId=inv-<UUID>
 */
import { mkdir, writeFile } from 'node:fs/promises'
import path from 'node:path'

const API = (process.env.API_URL || 'http://127.0.0.1:4000').replace(/\/$/, '')

function arg(name, fallback = '') {
  const hit = process.argv.find((a) => a.startsWith(`--${name}=`))
  return hit ? hit.slice(name.length + 3) : fallback
}

function hasFlag(name) {
  return process.argv.includes(`--${name}`)
}

function stripPlaceholders(s) {
  return String(s || '')
    .trim()
    .replace(/^<|>$/g, '')
}

async function fetchJSON(url, options) {
  const res = await fetch(url, options)
  if (!res.ok) {
    const body = await res.text()
    throw new Error(`${url} -> ${res.status} ${body.slice(0, 400)}`)
  }
  return res.json()
}

function normalizeAlertId(raw) {
  let id = stripPlaceholders(raw)
  if (!id) return ''
  if (id.startsWith('inv-')) id = id.slice(4)
  return id
}

async function listAlerts() {
  return fetchJSON(`${API}/api/alerts`)
}

async function investigate(alertId) {
  try {
    return await fetchJSON(`${API}/api/investigate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ alertId }),
    })
  } catch (apiErr) {
    const msg = apiErr.message || String(apiErr)
    throw new Error(
      [`Investigate failed for "${alertId}".`, 'List UUIDs with --list', `Detail: ${msg}`].join(
        '\n',
      ),
    )
  }
}

async function exportBundle(investigationId, inv) {
  try {
    return await fetchJSON(
      `${API}/api/investigations/${encodeURIComponent(investigationId)}/export`,
    )
  } catch {
    return {
      exportedAt: new Date().toISOString(),
      purpose: 'investigation-export',
      investigation: inv,
      immutableTrace: inv.trace || [],
      evidenceHash: inv.evidence?.hash || null,
      evidence: inv.evidence || null,
      seasonality: inv.seasonality || null,
      waterfall: inv.waterfall || [],
      counterfactual: inv.counterfactual || null,
      hypotheses: inv.hypotheses || [],
    }
  }
}

async function main() {
  if (hasFlag('help') || hasFlag('h')) {
    console.log(`Usage:
  node scripts/export-investigation.mjs --list
  node scripts/export-investigation.mjs --alertId=UUID --out=./exports
  node scripts/export-investigation.mjs --investigationId=inv-UUID`)
    return
  }

  if (hasFlag('list')) {
    const alerts = await listAlerts()
    if (!Array.isArray(alerts) || alerts.length === 0) {
      console.error('No alerts returned. Check API and alerts_live.')
      process.exit(1)
    }
    console.log(`Found ${alerts.length} alerts:\n`)
    for (const a of alerts.slice(0, 20)) {
      const uuid = String(a.id || '').replace(/^inv-/i, '')
      console.log(
        `- ${uuid}  ${a.metric || '?'}  ${a.advertiserId || ''}  ${a.pctChange ?? ''}%  inv=${a.investigationId || 'inv-' + uuid}`,
      )
    }
    console.log(`\nExample:
  node scripts/export-investigation.mjs --alertId=${String(alerts[0].id).replace(/^inv-/i, '')} --out=./exports`)
    return
  }

  const alertId = normalizeAlertId(arg('alertId'))
  let investigationId = stripPlaceholders(arg('investigationId'))
  const outDir = path.resolve(arg('out', './exports'))

  let inv
  if (alertId) {
    console.log(`Investigating alertId=${alertId}…`)
    inv = await investigate(alertId)
    investigationId = inv.id
  } else if (investigationId) {
    console.log(`Loading investigationId=${investigationId}…`)
    inv = await fetchJSON(`${API}/api/investigations/${encodeURIComponent(investigationId)}`)
  } else {
    console.error('Missing --alertId or --investigationId. Use --list to discover UUIDs.')
    process.exit(1)
  }

  const bundle = await exportBundle(investigationId, inv)
  if (!bundle.evidenceHash && !bundle.evidence?.hash) {
    console.warn('Warning: export has no evidenceHash.')
  }

  await mkdir(outDir, { recursive: true })
  const file = path.join(outDir, `${investigationId}-export.json`)
  await writeFile(file, JSON.stringify(bundle, null, 2))
  console.log('wrote', file)
  console.log('evidenceHash', bundle.evidenceHash || bundle.evidence?.hash || '(none)')
  console.log('seasonality', bundle.seasonality?.status || '(none)')
  console.log(
    'culprit',
    bundle.investigation?.decomposition?.find((d) => d.status === 'culprit')?.factor || '(none)',
  )
}

main().catch((err) => {
  console.error(err.message || err)
  process.exit(1)
})
