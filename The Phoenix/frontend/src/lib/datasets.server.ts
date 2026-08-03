// WHICH DATASET A CONSOLE IS LOOKING AT: the server-only half, where database names live.
//
// THE DATABASE NAME NEVER COMES FROM THE REQUEST. The client sends an opaque id, 'original' or
// 'unseen', and this module maps it to a database. Anything else falls back to 'original'. That
// is the same guarantee scripts/check_ask_guardrails.sh already asserts for the Ask routes: a
// client that could name a database could read any database the service user can reach.
//
// This replaced the frozen-slice predicate. The old design shipped one database and hid the
// unwanted rows behind `AND minute < {frozen_before:String}` on every serving query. Selecting a
// generation by NAME is the honest version of the same intent: the boundary is now which table
// the query reads, not a timestamp the reader has to trust us about.
//
// Kept apart from lib/datasets.ts because that file is bundled for the browser and this one
// imports lib/env.ts, which reads ../.env with node:fs at module scope.
import {toDatasetId, type DatasetId} from './datasets'
import {CH_DATABASE} from './env'

export interface ResolvedDataset {
  id: DatasetId
  /** Database holding the concurrency engine (v1: deltas, runs, content). */
  concurrency: string
  /** Database holding the insight layer (v2: the ten insight tables). */
  insights: string
}

// The insight layer exists in phoenix_next and in phoenix_unseen. It does NOT exist in phoenix.
const INSIGHT_DATABASE = process.env.CH_INSIGHT_DATABASE || 'phoenix_next'
const UNSEEN_DATABASE = process.env.CH_UNSEEN_DATABASE || 'phoenix_unseen'

const DATABASES: Record<DatasetId, ResolvedDataset> = {
  original: {id: 'original', concurrency: CH_DATABASE, insights: INSIGHT_DATABASE},
  unseen: {id: 'unseen', concurrency: UNSEEN_DATABASE, insights: UNSEEN_DATABASE},
}

/**
 * Resolves the `dataset` search param against the allowlist. Unknown, absent or malformed values
 * resolve to the original corpus rather than throwing: a bad link should show the graded default,
 * not a stack trace, and there is no value in telling a prober which names exist.
 */
export function resolveDataset(searchParams: URLSearchParams): ResolvedDataset {
  return DATABASES[toDatasetId(searchParams.get('dataset'))]
}
