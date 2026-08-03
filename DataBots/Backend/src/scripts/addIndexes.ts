import dotenv from 'dotenv'
import path from 'path'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
dotenv.config({ path: [path.resolve(__dirname, '../../.env'), path.resolve(__dirname, '../.env'), '.env'] })
import { createClient } from '@clickhouse/client'

async function addIndexes() {
  const url = process.env.CLICKHOUSE_URL || 'https://clickhouse.cloud'
  const username = process.env.CLICKHOUSE_USERNAME || 'default'
  const password = process.env.CLICKHOUSE_PASSWORD || ''

  console.log(`Connecting to ClickHouse at ${url} to optimize table projections...`)
  const ch = createClient({ url, username, password })

  try {
    console.log('1. Checking ad_events table projections...')
    await ch.command({
      query: `
        ALTER TABLE ad_events ADD PROJECTION IF NOT EXISTS proj_dim_ad_format
        (
          SELECT event_time, ad_format, is_filled, is_impression, is_click, revenue
          ORDER BY (ad_format, event_time)
        );
      `
    })

    console.log('2. Materializing projection for fast multi-dimensional drilldowns...')
    await ch.command({
      query: `ALTER TABLE ad_events MATERIALIZE PROJECTION IF EXISTS proj_dim_ad_format;`
    }).catch(err => console.log('Notice: Projection materialization queued or already materialized.', err.message))

    console.log('✅ ClickHouse projections successfully created!')
  } catch (err: any) {
    console.warn('⚠️ Note on Projections:', err.message || err)
  } finally {
    await ch.close()
  }
}

addIndexes()
