import dotenv from 'dotenv';
import path from 'path';
import { fileURLToPath } from 'url';
import { createClient } from '@clickhouse/client';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
dotenv.config({ path: [path.resolve(__dirname, '../../../.env'), path.resolve(__dirname, '../../.env'), path.resolve(__dirname, '../.env'), '.env'] });

async function benchmark() {
  const url = process.env.CLICKHOUSE_URL;
  const username = process.env.CLICKHOUSE_USERNAME || 'default';
  const password = process.env.CLICKHOUSE_PASSWORD;

  if (!url || !password) {
    throw new Error('CLICKHOUSE_URL and CLICKHOUSE_PASSWORD environment variables are required.');
  }

  console.log(`⚡ Connecting to ClickHouse Cloud at ${url}...`);
  const ch = createClient({ url, username, password });

  try {
    // 1. Get min & max event_time from ad_events
    console.log('📅 Fetching date bounds from ad_events...');
    const boundsRes = await ch.query({
      query: `SELECT min(event_time) AS min_t, max(event_time) AS max_t, count() AS total_rows FROM ad_events`,
      format: 'JSONEachRow',
    });
    const bounds: any = (await boundsRes.json())[0];
    console.log(`   Table contains ${Number(bounds.total_rows).toLocaleString()} events from ${bounds.min_t} to ${bounds.max_t}`);

    const minDate = new Date(bounds.min_t);
    // Use 1 hour window from 2026-06-08 10:00:00 to 2026-06-08 11:00:00
    const startWindow = '2026-06-08 10:00:00';
    const endWindow = '2026-06-08 11:00:00';

    console.log(`\n⏱️ Benchmark Time Window: ${startWindow} to ${endWindow}`);

    // Test 1: Single-Pass GROUP BY GROUPING SETS
    console.log('\n🚀 Test 1: Single-Pass GROUP BY GROUPING SETS Query...');
    const groupingSetsSql = `
      SELECT 
        ad_format,
        dictGet('apps_dict', 'publisher_tier', app_id) AS publisher_tier,
        dictGet('geo_device_dict', 'device_model', geo_device_id) AS device_model,
        dictGet('geo_device_dict', 'region', geo_device_id) AS region,
        count() AS requests,
        sum(is_filled) AS fills,
        sum(is_impression) AS impressions,
        sum(revenue) AS total_revenue,
        sum(is_filled) / count() AS fill_rate,
        sum(revenue) / nullIf(sum(is_impression), 0) * 1000 AS ecpm
      FROM ad_events
      WHERE event_time >= '${startWindow}' AND event_time < '${endWindow}'
      GROUP BY GROUPING SETS (
        (ad_format),
        (publisher_tier),
        (device_model),
        (region)
      );
    `;

    const start1 = performance.now();
    const res1 = await ch.query({ query: groupingSetsSql, format: 'JSONEachRow' });
    const data1: any[] = await res1.json();
    const latency1 = performance.now() - start1;

    console.log(`   ✅ Single-Pass GROUPING SETS Completed in: ${latency1.toFixed(2)} ms (${data1.length} aggregated rows returned)`);

    // Test 2: Separate Queries Fan-Out (Parallel SELECT per dimension)
    console.log('\n🔀 Test 2: Separate Parallel Queries (Fan-Out per dimension)...');
    const dims = [
      { name: 'ad_format', col: 'ad_format' },
      { name: 'publisher_tier', col: "dictGet('apps_dict', 'publisher_tier', app_id)" },
      { name: 'device_model', col: "dictGet('geo_device_dict', 'device_model', geo_device_id)" },
      { name: 'region', col: "dictGet('geo_device_dict', 'region', geo_device_id)" },
    ];

    const start2 = performance.now();
    const parallelQueries = dims.map(dim => {
      const sql = `
        SELECT 
          ${dim.col} AS dim_value,
          count() AS requests,
          sum(is_filled) AS fills,
          sum(is_impression) AS impressions,
          sum(revenue) AS total_revenue
        FROM ad_events
        WHERE event_time >= '${startWindow}' AND event_time < '${endWindow}'
        GROUP BY dim_value
      `;
      return ch.query({ query: sql, format: 'JSONEachRow' }).then(r => r.json());
    });

    const results2: any[] = await Promise.all(parallelQueries);
    const latency2 = performance.now() - start2;
    const totalRows2 = results2.reduce((acc, arr) => acc + arr.length, 0);

    console.log(`   ✅ Parallel Fan-Out Completed in: ${latency2.toFixed(2)} ms (${totalRows2} total rows returned across 4 queries)`);

    console.log('\n📊 BENCHMARK LATENCY SUMMARY (9 Million Events Dataset):');
    console.table([
      { Method: 'Single-Pass GROUPING SETS', Latency_ms: `${latency1.toFixed(2)} ms`, OutputRows: data1.length, Scans: '1 Table Scan' },
      { Method: 'Parallel Queries Fan-Out', Latency_ms: `${latency2.toFixed(2)} ms`, OutputRows: totalRows2, Scans: '4 Table Scans' },
    ]);

    console.log('\n🔍 Sample Output Rows from ClickHouse GROUPING SETS Query:');
    console.table(data1.slice(0, 10));

  } catch (err: any) {
    console.error('❌ Benchmark error:', err);
  } finally {
    await ch.close();
  }
}

benchmark();
