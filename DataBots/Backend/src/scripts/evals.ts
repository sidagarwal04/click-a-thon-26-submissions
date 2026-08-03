import dotenv from 'dotenv'
import path from 'path'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
dotenv.config({ path: [path.resolve(__dirname, '../../.env'), path.resolve(__dirname, '../.env'), '.env'] })

interface TestCase {
  name: string
  metric: string
  window_start: string
  window_end: string
  expected_driver: string
  expected_segment_dim: string
  expected_segment_val: string
  expected_ruled_out_keyword: string
}

interface EvalResult {
  name: string
  passed: boolean
  driverScore: number
  localizationScore: number
  trustworthinessScore: number
  ruledOutScore: number
  latencyMs: number
  details: string
}

const TEST_CASES: TestCase[] = [
  {
    name: 'Anomaly 1: Finance Apps eCPM Drop',
    metric: 'ecpm',
    window_start: '2026-06-19 10:00:00',
    window_end: '2026-06-19 11:00:00',
    expected_driver: 'ecpm',
    expected_segment_dim: 'category',
    expected_segment_val: 'finance',
    expected_ruled_out_keyword: 'ecpm',
  },
  {
    name: 'Anomaly 2: Global Sunday Request Volume Drop',
    metric: 'requests',
    window_start: '2026-06-21 12:00:00',
    window_end: '2026-06-21 13:00:00',
    expected_driver: 'requests',
    expected_segment_dim: 'ad_format', // volume drop across all dims
    expected_segment_val: 'banner',
    expected_ruled_out_keyword: 'ecpm',
  },
  {
    name: 'Anomaly 3: Android 15 Fill Rate Drop',
    metric: 'fill_rate',
    window_start: '2026-06-24 10:00:00',
    window_end: '2026-06-24 11:00:00',
    expected_driver: 'fill_rate',
    expected_segment_dim: 'os_version',
    expected_segment_val: 'Android 15',
    expected_ruled_out_keyword: 'render_rate',
  },
  {
    name: 'Anomaly 4: iOS 18.1 APAC Fill Rate Drop',
    metric: 'fill_rate',
    window_start: '2026-06-29 10:00:00',
    window_end: '2026-06-29 11:00:00',
    expected_driver: 'fill_rate',
    expected_segment_dim: 'os_version',
    expected_segment_val: 'iOS 18.1',
    expected_ruled_out_keyword: 'ecpm',
  },
]

async function runEvals() {
  const backendUrl = process.env.BACKEND_URL || 'http://localhost:5001/analyze'

  console.log(`\n🧪 =======================================================`)
  console.log(`   AUTOMATED RCA AGENT EVALUATION & TRUSTWORTHINESS SUITE`)
  console.log(`   Testing Endpoint: ${backendUrl}`)
  console.log(`   =======================================================\n`)

  const results: EvalResult[] = []

  for (const tc of TEST_CASES) {
    const startTime = Date.now()
    try {
      const res = await fetch(backendUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          metric: tc.metric,
          window_start: tc.window_start,
          window_end: tc.window_end,
        }),
      })

      const latencyMs = Date.now() - startTime

      if (!res.ok) {
        const errText = await res.text()
        results.push({
          name: tc.name,
          passed: false,
          driverScore: 0,
          localizationScore: 0,
          trustworthinessScore: 0,
          ruledOutScore: 0,
          latencyMs,
          details: `HTTP ${res.status}: ${errText}`,
        })
        continue
      }

      const body = await res.json()
      const evidence = body.evidence || {}
      const diagnosis = body.diagnosis || ''

      // 1. Evaluate Primary Factor Driver
      const factorDecomp = evidence.factor_decomposition || {}
      const primaryDriver = (factorDecomp.primary_driver_factor || factorDecomp.primary_factor || '').toLowerCase()
      const expectedDriver = tc.expected_driver.toLowerCase()
      const driverScore = (primaryDriver === expectedDriver || primaryDriver.includes(expectedDriver) || expectedDriver.includes(primaryDriver)) ? 100 : 0

      // 2. Evaluate Localization & Top Segment Isolation
      const topSegments = evidence.top_contributing_segments || []
      let localizationScore = 0
      for (const seg of topSegments) {
        const dimStr = (seg.dimension || '').toLowerCase()
        const valStr = (seg.value || '').toLowerCase()
        const targetDim = tc.expected_segment_dim.toLowerCase()
        const targetVal = tc.expected_segment_val.toLowerCase()

        if ((dimStr.includes(targetDim) || targetDim.includes(dimStr)) && valStr.includes(targetVal)) {
          localizationScore = 100
          break
        }
      }

      // If global request volume drop, isolated volume factor qualifies localization
      if (tc.expected_driver === 'requests' && driverScore === 100) {
        localizationScore = 100
      }

      // 3. Evaluate Trustworthiness (Verbatim Numbers Verification)
      const numbersInDiagnosis = extractNumbers(diagnosis)
      const evidenceJsonStr = JSON.stringify(evidence)
      let matchedCount = 0
      for (const numStr of numbersInDiagnosis) {
        if (evidenceJsonStr.includes(numStr)) {
          matchedCount++
        }
      }
      const trustworthinessScore = numbersInDiagnosis.length > 0
        ? Math.round((matchedCount / numbersInDiagnosis.length) * 100)
        : 100

      // 4. Evaluate Ruled-Out Section Completeness
      const ruledOut = evidence.ruled_out || []
      const ruledOutScore = ruledOut.length > 0 ? 100 : 0

      const passed = driverScore >= 80 && localizationScore >= 80 && trustworthinessScore >= 80 && ruledOutScore === 100

      results.push({
        name: tc.name,
        passed,
        driverScore,
        localizationScore,
        trustworthinessScore,
        ruledOutScore,
        latencyMs,
        details: `Driver: '${primaryDriver}' (expected '${expectedDriver}') | Top Segments: ${topSegments.length} | Ruled-Out: ${ruledOut.length} items`,
      })
    } catch (err: any) {
      results.push({
        name: tc.name,
        passed: false,
        driverScore: 0,
        localizationScore: 0,
        trustworthinessScore: 0,
        ruledOutScore: 0,
        latencyMs: Date.now() - startTime,
        details: `Fetch Exception: ${err.message || err}`,
      })
    }
  }

  // Print Evaluation Report Summary
  console.table(results.map(r => ({
    Scenario: r.name,
    Passed: r.passed ? '✅ YES' : '❌ NO',
    'Driver Accuracy': `${r.driverScore}%`,
    'Localization Accuracy': `${r.localizationScore}%`,
    'Trustworthiness (Verbatim Numbers)': `${r.trustworthinessScore}%`,
    'Ruled-Out Score': `${r.ruledOutScore}%`,
    'Latency (ms)': `${r.latencyMs} ms`,
  })))

  const totalPassed = results.filter(r => r.passed).length
  const avgLatency = Math.round(results.reduce((acc, r) => acc + r.latencyMs, 0) / results.length)
  const avgTrust = Math.round(results.reduce((acc, r) => acc + r.trustworthinessScore, 0) / results.length)

  console.log(`\n=======================================================`)
  console.log(`  EVALUATION SUMMARY`)
  console.log(`  Scenarios Passed: ${totalPassed} / ${results.length}`)
  console.log(`  Average Trustworthiness (Zero Hallucination): ${avgTrust}%`)
  console.log(`  Average Latency: ${avgLatency} ms`)
  console.log(`=======================================================\n`)
}

function extractNumbers(text: string): string[] {
  const matches = text.match(/-?\d+(\.\d+)?/g)
  if (!matches) return []
  // Filter out single digit integers that might be list numbers or formatting
  return matches.filter(n => n.length > 1 || n.includes('.'))
}

runEvals()
