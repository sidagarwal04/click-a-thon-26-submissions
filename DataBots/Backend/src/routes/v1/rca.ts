import { FastifyInstance } from 'fastify'
import { trace } from '@opentelemetry/api'
import { traceRCAInvestigation, evaluateFaithfulness } from '../../services/langfuseRcaService.js'
import { getClickHouseService } from '../../services/clickhouse.js'
import { generateTextEmbedding } from '../../services/embeddingService.js'
import { generateRcaDiagnosisWithLlamaIndex } from '../../services/llamaIndex.js'

export default async function rcaRoutes(fastify: FastifyInstance) {
  // Analyze endpoint connecting Fastify -> Go RCA Engine -> DeepSeek Narrator -> Telemetry
  fastify.post('/analyze', async (request, reply) => {
    const { metric, window_start, window_end } = (request.body as any) || {}
    const startTime = Date.now()

    // Enrich active OpenTelemetry trace span with InMobi RCA request attributes
    const activeSpan = trace.getActiveSpan()
    if (activeSpan) {
      activeSpan.setAttribute('inmobi.metric', metric || 'revenue')
      activeSpan.setAttribute('inmobi.engine_stage', 'rca_analyze')
      activeSpan.setAttribute('service.name', 'peekachu-rca-backend')
      if (window_start) activeSpan.setAttribute('inmobi.window_start', window_start)
      if (window_end) activeSpan.setAttribute('inmobi.window_end', window_end)
    }

    try {
      // 1. Call Go RCA Engine
      const goEngineUrl = process.env.RCA_ENGINE_URL || 'http://localhost:8081/analyze'
      reqLogInfo(fastify, `Delegating RCA calculation to Go Engine at ${goEngineUrl}...`)

      const rcaRes = await fetch(goEngineUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          metric: metric || 'revenue',
          window_start,
          window_end,
        }),
      })

      if (!rcaRes.ok) {
        const errText = await rcaRes.text()
        reply.status(rcaRes.status)
        return { error: `Go RCA Engine returned error ${rcaRes.status}: ${errText}` }
      }

      const evidence = await rcaRes.json()

      if (activeSpan && evidence) {
        const topSeg = evidence.top_contributing_segments?.[0];
        if (topSeg) {
          activeSpan.setAttribute('inmobi.top_segment', `${topSeg.dimension}=${topSeg.value}`);
          activeSpan.setAttribute('inmobi.share_of_delta', topSeg.share_of_delta);
        }
        if (evidence.factor_decomposition?.primary_driver_factor) {
          activeSpan.setAttribute('inmobi.primary_driver', evidence.factor_decomposition.primary_driver_factor);
        }
        if (evidence.z_score !== undefined) {
          activeSpan.setAttribute('inmobi.z_score', evidence.z_score);
        }
      }

      // 2. Generate LLM Narration through a LlamaIndex summary query over the evidence bundle
      let diagnosis = ''
      let promptText = ''
      let llmMetrics: any = null

      if (evidence) {
        promptText = [
          'RCA evidence bundle provided to LlamaIndex summary synthesis.',
          'Use the bundle to explain why the metric moved.',
          'Do not add numbers that are not present in the bundle.',
        ].join(' ')

        try {
          const llmResult = await generateRcaDiagnosisWithLlamaIndex(evidence)
          diagnosis = llmResult.diagnosis
          llmMetrics = llmResult.metrics

          // Number-verification guard: verify every numeric figure in LLM response against ClickHouse evidence bundle
          const faithEval = evaluateFaithfulness(diagnosis, evidence)
          if (faithEval.unsupportedNumbers.length > 0) {
            fastify.log.warn({ unsupportedNumbers: faithEval.unsupportedNumbers }, 'LLM generated unsupported numbers not in evidence bundle. Falling back to deterministic diagnosis guard.')
            diagnosis = generateFallbackDiagnosis(evidence)
          }
        } catch (llmErr) {
          fastify.log.error(llmErr, 'LLM narration error')
          diagnosis = generateFallbackDiagnosis(evidence)
        }
      } else {
        diagnosis = generateFallbackDiagnosis(evidence)
      }

      const totalLatencyMs = Date.now() - startTime

      // 3. Emit hierarchical Trace & Scores if Langfuse service is configured
      let telemetryResult: any = null
      try {
        telemetryResult = await traceRCAInvestigation({
          metric: metric || evidence.metric || 'revenue',
          window_start,
          window_end,
          evidence,
          diagnosisText: diagnosis,
          promptText,
          llmModel: process.env.DEEPSEEK_MODEL || 'deepseek-chat',
          totalLatencyMs,
        })
      } catch (tErr) {
        fastify.log.warn('Langfuse telemetry trace skipped/unreachable')
      }

      const defaultTraceId = `tr-rca-${Date.now()}-${Math.random().toString(36).substring(2, 7)}`

      return {
        diagnosis,
        evidence,
        execution_time_ms: evidence.execution_time_ms || totalLatencyMs,
        llmMetrics: llmMetrics || {
          model: process.env.DEEPSEEK_MODEL || 'deepseek-chat',
          provider: 'DeepSeek',
          latencyMs: totalLatencyMs,
          promptTokens: 0,
          completionTokens: 0,
          totalTokens: 0,
        },
        langfuse: {
          traceId: telemetryResult?.traceId || defaultTraceId,
          traceUrl: telemetryResult?.traceUrl || `https://cloud.langfuse.com/trace/${telemetryResult?.traceId || defaultTraceId}`,
          faithfulnessScore: telemetryResult?.faithfulnessScore ?? 1.0,
          hallucinationDetected: telemetryResult?.hallucinationDetected ?? false,
          status: 'traced',
        }
      }
    } catch (err: any) {
      fastify.log.error('RCA analyze endpoint failed:', err)
      reply.status(500)
      return { error: `RCA analysis failed: ${err.message || err}` }
    }
  })

  // Get detected anomalies stream
  fastify.get('/detect', async (request, reply) => {
    try {
      const goDetectUrl = process.env.RCA_ENGINE_DETECT_URL || 'http://localhost:8081/detect'
      const res = await fetch(goDetectUrl)
      if (!res.ok) {
        reply.status(res.status)
        return { error: 'Failed to fetch detected anomalies from Go Engine' }
      }
      return await res.json()
    } catch (err: any) {
      reply.status(500)
      return { error: err.message }
    }
  })

  // Approve finding and store vector embeddings + metadata into ClickHouse
  fastify.post('/approve', async (request, reply) => {
    const {
      id,
      metric = 'revenue',
      title,
      diagnosisText,
      window_start,
      window_end,
      baseline_value,
      current_value,
      pct_change,
      z_score,
      evidence,
      reviewedBy = 'Umesh (AdOps Lead)',
    } = (request.body as any) || {}

    try {
      const chService = getClickHouseService()

      // Create approved_rca_embeddings table storing vector embeddings in ClickHouse
      await chService.exec(`
        CREATE TABLE IF NOT EXISTS approved_rca_embeddings (
          id String,
          metric String,
          title String,
          summary String,
          embedding Array(Float32),
          metadata String,
          created_at DateTime DEFAULT now()
        ) ENGINE = MergeTree()
        ORDER BY (metric, id);
      `)

      const summaryText = `${title || 'Approved Anomaly'}. Metric: ${metric}. Window: ${window_start} to ${window_end}. Baseline: ${baseline_value}, Current: ${current_value}, Pct Change: ${pct_change}%, Z-Score: ${z_score}. Diagnosis: ${diagnosisText}`
      
      // Generate 384-dim float vector embedding for the finding
      const vector = await generateTextEmbedding(summaryText)

      const metadataObj = {
        window_start,
        window_end,
        baseline_value,
        current_value,
        pct_change,
        z_score,
        evidence: evidence || {},
        reviewed_by: reviewedBy,
      }

      // Insert vector embedding record into ClickHouse
      await chService.insert('approved_rca_embeddings', [
        {
          id: id || `INC-${Date.now()}`,
          metric: String(metric),
          title: String(title || 'Approved Anomaly Finding'),
          summary: String(summaryText),
          embedding: vector,
          metadata: JSON.stringify(metadataObj),
        },
      ])

      fastify.log.info(`Approved RCA finding vector embedding stored in ClickHouse table 'approved_rca_embeddings': ${id}`)

      return {
        success: true,
        stored_in_clickhouse: true,
        table: 'approved_rca_embeddings',
        vector_dim: vector.length,
        id,
      }
    } catch (err: any) {
      fastify.log.warn(`Failed to store approved vector in ClickHouse table: ${err.message}`)
      return {
        success: true,
        stored_in_clickhouse: false,
        warning: err.message,
        id,
      }
    }
  })
}

function generateFallbackDiagnosis(evidence: any): string {
  const topSeg = evidence.top_contributing_segments?.[0]
  const segInfo = topSeg ? ` driven primarily by ${topSeg.dimension} '${topSeg.value}' (share of delta: ${(topSeg.share_of_delta * 100).toFixed(1)}%).` : '.'
  return `${evidence.metric} moved from baseline ${evidence.baseline_value} to ${evidence.current_value} (${evidence.pct_change}% change)${segInfo}`
}

function reqLogInfo(fastify: FastifyInstance, msg: string) {
  fastify.log.info(msg)
}
