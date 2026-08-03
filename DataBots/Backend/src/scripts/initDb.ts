import dotenv from 'dotenv'
import path from 'path'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
dotenv.config({ path: [path.resolve(__dirname, '../../../.env'), path.resolve(__dirname, '../../.env'), path.resolve(__dirname, '../.env'), '.env'] })
import { createClient } from '@clickhouse/client'
import {
  CREATE_AD_EVENTS_TABLE_SQL,
  CREATE_APPS_TABLE_SQL,
  CREATE_APPS_DICT_SQL,
  CREATE_ADVERTISERS_TABLE_SQL,
  CREATE_ADVERTISERS_DICT_SQL,
  CREATE_GEO_DEVICE_TABLE_SQL,
  CREATE_GEO_DEVICE_DICT_SQL,
  VERIFY_TABLE_COUNTS_SQL,
} from '../db/schema.js'

async function initDb() {
  const url = process.env.CLICKHOUSE_URL
  const username = process.env.CLICKHOUSE_USERNAME || 'default'
  const password = process.env.CLICKHOUSE_PASSWORD

  if (!url || !password) {
    throw new Error('CLICKHOUSE_URL and CLICKHOUSE_PASSWORD environment variables are required.')
  }

  console.log(`Connecting to ClickHouse at ${url}...`)
  const ch = createClient({ url, username, password })

  try {
    console.log('1. Creating MergeTree table ad_events...')
    await ch.command({ query: CREATE_AD_EVENTS_TABLE_SQL })

    console.log('2. Creating apps table and apps_dict dictionary...')
    await ch.command({ query: CREATE_APPS_TABLE_SQL })
    await ch.command({ query: CREATE_APPS_DICT_SQL })

    console.log('3. Creating advertisers table and advertisers_dict dictionary...')
    await ch.command({ query: CREATE_ADVERTISERS_TABLE_SQL })
    await ch.command({ query: CREATE_ADVERTISERS_DICT_SQL })

    console.log('4. Creating geo_device table and geo_device_dict dictionary...')
    await ch.command({ query: CREATE_GEO_DEVICE_TABLE_SQL })
    await ch.command({ query: CREATE_GEO_DEVICE_DICT_SQL })

    console.log('\n--- Verification Row Counts ---')
    const resultSet = await ch.query({ query: VERIFY_TABLE_COUNTS_SQL, format: 'JSONEachRow' })
    const rows = await resultSet.json()
    console.table(rows)

    console.log('\n✅ Database schema and dictionaries successfully initialized!')
  } catch (err) {
    console.error('❌ Error initializing ClickHouse schema:', err)
    process.exit(1)
  } finally {
    await ch.close()
  }
}

initDb()
