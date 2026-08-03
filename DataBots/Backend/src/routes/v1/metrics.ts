import { FastifyInstance } from "fastify";
import { DEFAULT_METRIC, SUPPORTED_METRICS } from "../../data/metrics.js";

export default async function metricsRoutes(fastify: FastifyInstance) {
  fastify.get("/v1/metrics", async () => {
    return {
      default_metric: DEFAULT_METRIC,
      data: SUPPORTED_METRICS,
    };
  });
}