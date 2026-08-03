# Peekachu — ClickStack Telemetry & OpenTelemetry Setup Guide

This document outlines the architecture, setup process, troubleshooting steps, and Docker command for sending OpenTelemetry traces, metrics, and logs from the **Peekachu InMobi RCA Backend** (`peekachu-rca-backend`) to the ClickStack OpenTelemetry Collector.

---

## 1. Running the ClickStack OTLP Collector (Docker)

To ingest OpenTelemetry traces, metrics, and logs into your ClickHouse instance, spin up the `clickstack-otel-collector` Docker container:

```bash
docker run \
  -e CLICKHOUSE_ENDPOINT="<YOUR_CLICKHOUSE_ENDPOINT>" \
  -e CLICKHOUSE_USER="<YOUR_CLICKHOUSE_USER>" \
  -e CLICKHOUSE_PASSWORD="<YOUR_CLICKHOUSE_PASSWORD>" \
  -p 4317:4317 \
  -p 4318:4318 \
  clickhouse/clickstack-otel-collector:latest
```

### Port Mapping Details:
- **`4318`**: OTLP HTTP receiver (used by `@opentelemetry/exporter-*-otlp-http`).
- **`4317`**: OTLP gRPC receiver.

---

## 2. InMobi RCA OpenTelemetry Architecture

### Service Identification & Resource Attributes
- **Service Name (`ATTR_SERVICE_NAME`)**: `peekachu-rca-backend`
- **Service Namespace (`ATTR_SERVICE_NAMESPACE`)**: `inmobi.rca`
- **Service Version**: `1.0.0`
- **System**: `peekachu-automated-rca`

### Setup & Initialization
- **`src/instrumentation.ts`**: Initializes `@opentelemetry/sdk-node` NodeSDK with Node auto-instrumentations (`@opentelemetry/auto-instrumentations-node`), exporting OTLP HTTP traces (`/v1/traces`), metrics (`/v1/metrics`), and logs (`/v1/logs`).
- **`src/index.ts`**: Fastify application entrypoint. `import './instrumentation.js'` is loaded at **Line 1** to hook HTTP, Fastify, and ClickHouse network calls before other modules load.

### Custom InMobi Ad-Tech Telemetry Attributes
Every request or RCA investigation enriches active OpenTelemetry trace spans and log records with domain-specific attributes matching the InMobi Click-a-thon problem statement:

| Telemetry Attribute | Description | Example Values |
|---|---|---|
| `inmobi.metric` | Target ad metric being analyzed | `revenue`, `fill_rate`, `ecpm`, `impressions`, `ctr` |
| `inmobi.dimension` | Dimension dimension slice | `region`, `ad_format`, `publisher_tier`, `vertical`, `device_model` |
| `inmobi.region` | Geolocation region | `NAM`, `EU`, `APAC`, `LATAM`, `MEA` |
| `inmobi.ad_format` | Ad unit format | `banner`, `interstitial`, `native`, `rewarded`, `video` |
| `inmobi.publisher_tier` | Publisher account tier | `tier_1`, `tier_2`, `tier_3` |
| `inmobi.vertical` | Advertiser vertical | `gaming`, `ecommerce`, `finance`, `travel`, `cpg` |
| `inmobi.investigation_id` | Unique correlation ID for RCA run | `rca-inv-171829381` |
| `inmobi.engine_stage` | Execution stage in RCA loop | `ad_funnel`, `rca_analyze`, `detection`, `drilldown` |
| `inmobi.primary_driver` | Identity factor identified as root driver | `fill_rate`, `ecpm`, `requests` |
| `inmobi.top_segment` | Primary segment causing anomaly | `region x ad_format=APAC / rewarded` |
| `inmobi.share_of_delta` | Fraction of total metric drop explained | `0.84` (84%) |

---

## 3. GitHub Codespaces Networking & Troubleshooting

When developing inside GitHub Codespaces:
- Forwarded public URLs (`https://<codespace>-4318.app.github.dev`) are protected by GitHub OAuth authentication proxies (`HTTP 401 Unauthorized`).
- OpenTelemetry SDK HTTP exporters running inside the Node.js container cannot bypass the GitHub 401 Auth tunnel.
- **Solution**: Configure `OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318` in `.env`. Local container traffic accesses the OTLP collector directly via loopback on port `4318` without authentication blocks.

---

## 4. InMobi Ad-Funnel & RCA Anomaly Simulation

Test telemetry collection and RCA anomaly detection using the simulation endpoints:

- **Ad Request**: `POST /ad/request`
- **Ad Fill**: `POST /ad/fill`
- **Ad Impression**: `POST /ad/impression`
- **Ad Click**: `POST /ad/click`
- **Simulate RCA Anomaly Scenario**: `POST /rca/simulate_anomaly`

Example request with InMobi telemetry headers:
```bash
curl -X POST http://localhost:5001/ad/fill \
  -H "Content-Type: application/json" \
  -H "x-inmobi-metric: fill_rate" \
  -H "x-inmobi-region: APAC" \
  -H "x-inmobi-ad-format: rewarded" \
  -H "x-inmobi-publisher-tier: tier_3"
```
