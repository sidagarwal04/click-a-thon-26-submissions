import dotenv from 'dotenv'
import path from 'path'
import { fileURLToPath } from 'url'
import { createClient } from '@clickhouse/client'
import { CREATE_AD_EVENTS_HOURLY_ROLLUP_TABLE_SQL } from '../db/schema.js'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
dotenv.config({ path: [path.resolve(__dirname, '../../../.env'), path.resolve(__dirname, '../../.env'), path.resolve(__dirname, '../.env'), '.env'] })

async function populateRollup() {
  const url = process.env.CLICKHOUSE_URL
  const username = process.env.CLICKHOUSE_USERNAME || 'default'
  const password = process.env.CLICKHOUSE_PASSWORD

  if (!url || !password) {
    throw new Error('CLICKHOUSE_URL and CLICKHOUSE_PASSWORD environment variables are required.')
  }

  console.log(`Connecting to ClickHouse at ${url}...`)
  const ch = createClient({ url, username, password })

  try {
    console.log('1. Ensuring ad_events_hourly_rollup table exists...')
    await ch.command({ query: CREATE_AD_EVENTS_HOURLY_ROLLUP_TABLE_SQL })

    console.log('2. Truncating ad_events_hourly_rollup to refresh data...')
    await ch.command({ query: 'TRUNCATE TABLE ad_events_hourly_rollup' })

    const dimensionQueries = [
      {
        name: 'ad_format',
        sql: `INSERT INTO ad_events_hourly_rollup SELECT toStartOfHour(event_time) AS event_hour, 'ad_format' AS dim_name, ad_format AS dim_val, countState() AS requests, sumState(is_filled) AS fills, sumState(is_impression) AS impressions, sumState(is_click) AS clicks, sumState(revenue) AS revenue FROM ad_events GROUP BY event_hour, dim_val`,
      },
      {
        name: 'category',
        sql: `INSERT INTO ad_events_hourly_rollup SELECT toStartOfHour(event_time) AS event_hour, 'category' AS dim_name, dictGet('apps_dict', 'category', app_id) AS dim_val, countState() AS requests, sumState(is_filled) AS fills, sumState(is_impression) AS impressions, sumState(is_click) AS clicks, sumState(revenue) AS revenue FROM ad_events GROUP BY event_hour, dim_val`,
      },
      {
        name: 'publisher_tier',
        sql: `INSERT INTO ad_events_hourly_rollup SELECT toStartOfHour(event_time) AS event_hour, 'publisher_tier' AS dim_name, dictGet('apps_dict', 'publisher_tier', app_id) AS dim_val, countState() AS requests, sumState(is_filled) AS fills, sumState(is_impression) AS impressions, sumState(is_click) AS clicks, sumState(revenue) AS revenue FROM ad_events GROUP BY event_hour, dim_val`,
      },
      {
        name: 'vertical',
        sql: `INSERT INTO ad_events_hourly_rollup SELECT toStartOfHour(event_time) AS event_hour, 'vertical' AS dim_name, dictGet('advertisers_dict', 'vertical', advertiser_id) AS dim_val, countState() AS requests, sumState(is_filled) AS fills, sumState(is_impression) AS impressions, sumState(is_click) AS clicks, sumState(revenue) AS revenue FROM ad_events GROUP BY event_hour, dim_val`,
      },
      {
        name: 'campaign_type',
        sql: `INSERT INTO ad_events_hourly_rollup SELECT toStartOfHour(event_time) AS event_hour, 'campaign_type' AS dim_name, dictGet('advertisers_dict', 'campaign_type', advertiser_id) AS dim_val, countState() AS requests, sumState(is_filled) AS fills, sumState(is_impression) AS impressions, sumState(is_click) AS clicks, sumState(revenue) AS revenue FROM ad_events GROUP BY event_hour, dim_val`,
      },
      {
        name: 'region',
        sql: `INSERT INTO ad_events_hourly_rollup SELECT toStartOfHour(event_time) AS event_hour, 'region' AS dim_name, dictGet('geo_device_dict', 'region', geo_device_id) AS dim_val, countState() AS requests, sumState(is_filled) AS fills, sumState(is_impression) AS impressions, sumState(is_click) AS clicks, sumState(revenue) AS revenue FROM ad_events GROUP BY event_hour, dim_val`,
      },
      {
        name: 'country',
        sql: `INSERT INTO ad_events_hourly_rollup SELECT toStartOfHour(event_time) AS event_hour, 'country' AS dim_name, dictGet('geo_device_dict', 'country', geo_device_id) AS dim_val, countState() AS requests, sumState(is_filled) AS fills, sumState(is_impression) AS impressions, sumState(is_click) AS clicks, sumState(revenue) AS revenue FROM ad_events GROUP BY event_hour, dim_val`,
      },
      {
        name: 'device_model',
        sql: `INSERT INTO ad_events_hourly_rollup SELECT toStartOfHour(event_time) AS event_hour, 'device_model' AS dim_name, dictGet('geo_device_dict', 'device_model', geo_device_id) AS dim_val, countState() AS requests, sumState(is_filled) AS fills, sumState(is_impression) AS impressions, sumState(is_click) AS clicks, sumState(revenue) AS revenue FROM ad_events GROUP BY event_hour, dim_val`,
      },
      {
        name: 'os_version',
        sql: `INSERT INTO ad_events_hourly_rollup SELECT toStartOfHour(event_time) AS event_hour, 'os_version' AS dim_name, dictGet('geo_device_dict', 'os_version', geo_device_id) AS dim_val, countState() AS requests, sumState(is_filled) AS fills, sumState(is_impression) AS impressions, sumState(is_click) AS clicks, sumState(revenue) AS revenue FROM ad_events GROUP BY event_hour, dim_val`,
      },
    ]

    for (const dim of dimensionQueries) {
      console.log(`Populating dimension '${dim.name}' into rollup table...`)
      await ch.command({ query: dim.sql })
    }

    const countRes = await ch.query({ query: 'SELECT dim_name, count() AS total FROM ad_events_hourly_rollup GROUP BY dim_name', format: 'JSONEachRow' })
    const rows = await countRes.json()
    console.log('\n✅ Rollup table ad_events_hourly_rollup successfully populated!')
    console.table(rows)
  } catch (err) {
    console.error('❌ Error populating rollup table:', err)
    process.exit(1)
  } finally {
    await ch.close()
  }
}

populateRollup()
