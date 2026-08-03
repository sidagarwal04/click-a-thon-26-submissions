import { FastifyInstance, FastifyRequest } from "fastify";
import { trace } from "@opentelemetry/api";

function extractAndEnrichTelemetry(req: FastifyRequest) {
  const metric = (req.headers["x-inmobi-metric"] as string) || "revenue";
  const dimension = (req.headers["x-inmobi-dimension"] as string) || "region";
  const region = (req.headers["x-inmobi-region"] as string) || "NAM";
  const adFormat = (req.headers["x-inmobi-ad-format"] as string) || "rewarded";
  const publisherTier = (req.headers["x-inmobi-publisher-tier"] as string) || "tier_1";
  const vertical = (req.headers["x-inmobi-vertical"] as string) || "gaming";
  const requestId = (req.headers["x-request-id"] as string) || `rca-inv-${Date.now()}`;
  const engineStage = (req.headers["x-inmobi-stage"] as string) || "ad_funnel";

  // Structured logging for ClickHouse / ClickStack log ingestion
  req.log.info({
    "inmobi.metric": metric,
    "inmobi.dimension": dimension,
    "inmobi.region": region,
    "inmobi.ad_format": adFormat,
    "inmobi.publisher_tier": publisherTier,
    "inmobi.vertical": vertical,
    "inmobi.investigation_id": requestId,
    "inmobi.engine_stage": engineStage,
    path: req.url,
    method: req.method,
  });

  // Enrich active OpenTelemetry trace span with InMobi Ad-Tech RCA domain context
  const activeSpan = trace.getActiveSpan();
  if (activeSpan) {
    activeSpan.setAttribute("inmobi.metric", metric);
    activeSpan.setAttribute("inmobi.dimension", dimension);
    activeSpan.setAttribute("inmobi.region", region);
    activeSpan.setAttribute("inmobi.ad_format", adFormat);
    activeSpan.setAttribute("inmobi.publisher_tier", publisherTier);
    activeSpan.setAttribute("inmobi.vertical", vertical);
    activeSpan.setAttribute("inmobi.investigation_id", requestId);
    activeSpan.setAttribute("inmobi.engine_stage", engineStage);
    activeSpan.setAttribute("service.name", "peekachu-rca-backend");
    activeSpan.setAttribute("http.route", req.url);
  }

  return { metric, dimension, region, adFormat, publisherTier, vertical, requestId, engineStage };
}

export default async function simulationRoutes(fastify: FastifyInstance) {
  // Hook to automatically extract and enrich telemetry for all simulation routes
  fastify.addHook("onRequest", async (req) => {
    extractAndEnrichTelemetry(req);
  });

  // 1. Ad Request (Top of Funnel)
  fastify.all("/ad/request", async (req) => {
    const { region, adFormat, publisherTier, requestId } = extractAndEnrichTelemetry(req);
    return {
      status: "success",
      event: "ad_request",
      requestId,
      region,
      adFormat,
      publisherTier,
      timestamp: new Date().toISOString(),
    };
  });

  // 2. Ad Fill
  fastify.all("/ad/fill", async (req) => {
    const { region, adFormat, publisherTier, requestId } = extractAndEnrichTelemetry(req);
    // Simulate intermittent fill drop in APAC
    const isFilled = region === "APAC" && adFormat === "rewarded" ? Math.random() > 0.4 : Math.random() > 0.1;
    return {
      status: "success",
      event: "ad_fill",
      requestId,
      isFilled,
      fillRate: isFilled ? 1.0 : 0.0,
      timestamp: new Date().toISOString(),
    };
  });

  // 3. Ad Impression
  fastify.all("/ad/impression", async (req) => {
    const { region, adFormat, publisherTier, vertical, requestId } = extractAndEnrichTelemetry(req);
    const ecpm = publisherTier === "tier_1" ? 14.5 : 4.2;
    const revenue = ecpm / 1000;
    return {
      status: "success",
      event: "ad_impression",
      requestId,
      isImpression: true,
      ecpm,
      revenue,
      vertical,
      timestamp: new Date().toISOString(),
    };
  });

  // 4. Ad Click
  fastify.all("/ad/click", async (req) => {
    const { requestId } = extractAndEnrichTelemetry(req);
    const isClick = Math.random() < 0.08;
    return {
      status: "success",
      event: "ad_click",
      requestId,
      isClick,
      timestamp: new Date().toISOString(),
    };
  });

  // 5. RCA Anomaly Simulation Endpoint
  fastify.post("/rca/simulate_anomaly", async (req) => {
    const body = (req.body as any) || {};
    const metric = body.metric || "fill_rate";
    const region = body.region || "APAC";
    const adFormat = body.ad_format || "rewarded";
    const targetSegment = `${region} / ${adFormat}`;

    return {
      status: "anomaly_simulated",
      anomaly: {
        metric,
        window: "2026-03-12T14:00:00Z to 2026-03-12T15:00:00Z",
        baseline_value: 0.88,
        current_value: 0.52,
        pct_change: -40.9,
        z_score: -4.8,
        primary_driver: "fill_rate",
        top_contributing_segment: {
          dimension: "region x ad_format",
          value: targetSegment,
          share_of_delta: 0.84,
        },
        ruled_out: [
          { dimension: "request_volume", reason: "Request volume normal (z-score = 0.2)" },
          { dimension: "seasonality", reason: "Trailing 4-week hourly baseline verified" },
        ],
      },
    };
  });

  // 6. Metrics Funnel Summary
  fastify.get("/metrics/summary", async () => {
    return {
      platform: "InMobi Ad Exchange",
      metrics: [
        { name: "requests", label: "Ad Requests", formula: "count(*)" },
        { name: "fills", label: "Fills", formula: "sum(is_filled)" },
        { name: "fill_rate", label: "Fill Rate", formula: "sum(is_filled) / count(*)" },
        { name: "impressions", label: "Impressions", formula: "sum(is_impression)" },
        { name: "ecpm", label: "eCPM", formula: "sum(revenue) / sum(is_impression) * 1000" },
        { name: "revenue", label: "Revenue", formula: "sum(revenue)" },
      ],
      dimensions: ["ad_format", "category", "publisher_tier", "vertical", "campaign_type", "region", "country", "device_model", "os_version"],
    };
  });
}
