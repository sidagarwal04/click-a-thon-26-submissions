// WHICH DATASET A CONSOLE IS LOOKING AT: the client-safe half.
//
// The submission has to show two answers side by side: the original graded corpus that every
// number in evidence/ was measured against, and the unseen day the organisers released on
// 2026-08-02 (docs/problem/spec.md, 7,000,000 events on 2026-07-31). A judge needs to see that the
// pipeline generalises, which means seeing both without restarting anything.
//
// THIS FILE HAS NO IMPORTS ON PURPOSE. It is pulled into the browser bundle by the switch
// component, and lib/env.ts reads ../.env with node:fs at module scope. Importing env here put
// node:fs in the client chunk and broke the production build. The database names therefore live
// in lib/datasets.server.ts, which never reaches the browser. Labels and ids are safe to ship;
// database names are not something a client needs to know at all.

export type DatasetId = 'original' | 'unseen'

export interface Dataset {
  id: DatasetId
  /** Button text. */
  label: string
  /** One line under the switch, so the control explains itself without a legend. */
  blurb: string
}

export const DATASET_LIST: Dataset[] = [
  {
    id: 'original',
    label: 'Original corpus',
    blurb: 'The 905,558-event dataset every number in evidence/ was measured against.',
  },
  {
    id: 'unseen',
    label: 'Unseen day',
    blurb:
      '7,000,000 events for 2026-07-31, released after the pipeline was built. Same queries, untouched.',
  },
]

/** Narrows an untrusted string to a known id, defaulting to the graded corpus. */
export function toDatasetId(value: string | null | undefined): DatasetId {
  return value === 'unseen' ? 'unseen' : 'original'
}
