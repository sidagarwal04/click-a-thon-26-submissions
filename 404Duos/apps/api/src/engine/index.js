import { createClickHouse, queryMaps, quoteString, quoteTime, asFloat, asString } from './clickhouse.js'
import {
  getDashboardMeta,
  queryDashboard,
  getDashboardFilters,
} from './dashboard.js'
import {
  runInvestigation,
  detectAlerts,
  requestFromInvestigationID,
  buildExportBundle,
  createInvestigationCache,
  cacheGet,
  cachePut,
  looksLikeUUID,
  normalizeAlertID,
} from './investigate.js'
import * as util from './util.js'
import * as rca from './rca.js'

/**
 * Create an in-process engine bound to a ClickHouse client + investigation cache.
 *
 * @param {import('@clickhouse/client').ClickHouseClient} client
 */
export function createEngine(client) {
  const cache = createInvestigationCache()

  return {
    client,
    cache,

    /** @param {'day'|'hour'} [granularity] */
    async detectAlerts(granularity = 'day') {
      return detectAlerts(client, cache, granularity)
    },

    /** Run investigation and store in cache. */
    async runInvestigation(req) {
      const inv = await runInvestigation(client, req)
      cache.put(inv)
      return inv
    },

    /** Cache hit, or rebuild from investigation id. */
    async getInvestigation(id) {
      const cached = cache.get(id)
      if (cached) return cached
      const req = requestFromInvestigationID(id)
      const inv = await runInvestigation(client, req)
      cache.put(inv)
      return inv
    },

    getCachedInvestigation(id) {
      return cache.get(id)
    },

    putInvestigation(inv) {
      return cache.put(inv)
    },

    /** Export bundle (main.go GET /investigations/{id}/export). */
    async exportInvestigation(id) {
      let inv = cache.get(id)
      if (!inv) {
        const req = requestFromInvestigationID(id)
        inv = await runInvestigation(client, req)
        cache.put(inv)
      }
      return buildExportBundle(inv)
    },

    getDashboardMeta: () => getDashboardMeta(client),
    queryDashboard: (body) => queryDashboard(client, body),
    getDashboardFilters: (query) => getDashboardFilters(client, query),

    buildExportBundle,
    requestFromInvestigationID,
  }
}

export {
  createClickHouse,
  queryMaps,
  quoteString,
  quoteTime,
  asFloat,
  asString,
  getDashboardMeta,
  queryDashboard,
  getDashboardFilters,
  runInvestigation,
  detectAlerts,
  requestFromInvestigationID,
  buildExportBundle,
  createInvestigationCache,
  cacheGet,
  cachePut,
  looksLikeUUID,
  normalizeAlertID,
  util,
  rca,
}
