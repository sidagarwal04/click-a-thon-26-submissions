import { NodeSDK } from '@opentelemetry/sdk-node'
import { getNodeAutoInstrumentations } from '@opentelemetry/auto-instrumentations-node'
import { OTLPTraceExporter } from '@opentelemetry/exporter-trace-otlp-http'
import { OTLPMetricExporter } from '@opentelemetry/exporter-metrics-otlp-http'
import { OTLPLogExporter } from '@opentelemetry/exporter-logs-otlp-http'
import { PeriodicExportingMetricReader } from '@opentelemetry/sdk-metrics'
import { BatchLogRecordProcessor } from '@opentelemetry/sdk-logs'
import { resourceFromAttributes } from '@opentelemetry/resources'
import {
  ATTR_SERVICE_NAME,
  ATTR_SERVICE_VERSION,
  ATTR_SERVICE_NAMESPACE,
} from '@opentelemetry/semantic-conventions'
import dotenv from "dotenv";

dotenv.config();

// If OTEL_EXPORTER_OTLP_ENDPOINT points to *.app.github.dev inside Codespaces, fallback to local http://localhost:4318 to avoid 401 Auth Proxy errors
let rawEndpoint = process.env.OTEL_EXPORTER_OTLP_ENDPOINT || 'http://localhost:4318'
if (rawEndpoint.includes('app.github.dev')) {
  console.log(`⚠️  Detected GitHub Codespaces public URL (${rawEndpoint}). Swapping to local http://localhost:4318 to avoid 401 Auth Proxy errors.`);
  rawEndpoint = 'http://localhost:4318'
}
const endpoint = rawEndpoint.replace(/\/+$/, '')

const sdk = new NodeSDK({
  resource: resourceFromAttributes({
    [ATTR_SERVICE_NAME]: process.env.OTEL_SERVICE_NAME || 'peekachu-rca-backend',
    [ATTR_SERVICE_NAMESPACE]: 'inmobi.rca',
    [ATTR_SERVICE_VERSION]: '1.0.0',
    'deployment.environment': process.env.NODE_ENV || 'production',
    'inmobi.system': 'peekachu-automated-rca',
  }),

  traceExporter: new OTLPTraceExporter({
    url: `${endpoint}/v1/traces`,
  }),

  metricReader: new PeriodicExportingMetricReader({
    exporter: new OTLPMetricExporter({
      url: `${endpoint}/v1/metrics`,
    }),
  }),

  logRecordProcessor: new BatchLogRecordProcessor({
    exporter: new OTLPLogExporter({
      url: `${endpoint}/v1/logs`,
    }),
  }),

  instrumentations: [
    getNodeAutoInstrumentations({
      '@opentelemetry/instrumentation-fs': { enabled: false }, // avoid verbose file system noise
    }),
  ],
})

sdk.start()

console.log(`✅ Peekachu OpenTelemetry SDK initialized (Service: peekachu-rca-backend) -> exporting OTLP to: ${endpoint}`)

// Ensure telemetry buffers flush on shutdown
process.on('SIGTERM', () => {
  sdk.shutdown()
    .then(() => console.log('OpenTelemetry SDK shut down successfully'))
    .catch((err) => console.error('Error shutting down OpenTelemetry SDK', err))
})