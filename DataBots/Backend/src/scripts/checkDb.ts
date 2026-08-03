import dotenv from 'dotenv'
import path from 'path'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
dotenv.config({ path: [path.resolve(__dirname, '../../../.env'), path.resolve(__dirname, '../../.env'), path.resolve(__dirname, '../.env'), '.env'] })
import { createClient } from '@clickhouse/client'
import { VERIFY_TABLE_COUNTS_SQL, VERIFY_DICTIONARY_LOOKUP_SQL } from '../db/schema.js'

async function checkDb() {
  const url = process.env.CLICKHOUSE_URL
  const username = process.env.CLICKHOUSE_USERNAME || 'default'
  const password = process.env.CLICKHOUSE_PASSWORD

  if (!url || !password) {
    throw new Error('CLICKHOUSE_URL and CLICKHOUSE_PASSWORD environment variables are required.')
  }

  console.log(`🔍 Checking ClickHouse Database Status at ${url}...\n`)
  const ch = createClient({ url, username, password })

  try {
    console.log('📊 Table Row Counts:')
    const countsRes = await ch.query({ query: VERIFY_TABLE_COUNTS_SQL, format: 'JSONEachRow' })
    const counts = await countsRes.json()
    console.table(counts)

    console.log('🧪 Testing Dictionary Lookups (apps_dict, geo_device_dict, advertisers_dict)...')
    const lookupRes = await ch.query({ query: VERIFY_DICTIONARY_LOOKUP_SQL, format: 'JSONEachRow' })
    const sample = await lookupRes.json()
    console.table(sample)

    console.log('\n✅ All tables, dictionaries, and queries are healthy and operational!')
  } catch (err) {
    console.error('❌ Error checking ClickHouse DB:', err)
    process.exit(1)
  } finally {
    await ch.close()
  }
}

checkDb()
