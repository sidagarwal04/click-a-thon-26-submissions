import { instrumentationPipelineStages } from "./instrumentation/trackingEvents.js";

export const pipelineStages = [
  ...instrumentationPipelineStages,
  {
    id: "08_analytics_orchestrator",
    name: "Analytics Orchestrator",
    description:
      "Plan Gold analysis and route work to funnel, segment, revenue, and anomaly logic.",
  },
  {
    id: "09_gold_metrics",
    name: "Gold Metrics",
    description:
      "Run SQL and store business-ready metrics and result artifacts.",
  },
  {
    id: "10_insight_writer",
    name: "Insight Writer",
    description:
      "Write PM-facing insights, recommendations, and confidence notes.",
  },
  {
    id: "11_evidence_critic",
    name: "Evidence Critic",
    description:
      "Check that insights are supported by SQL results and context.",
  },
  {
    id: "12_trace_summary",
    name: "Trace Summary",
    description: "Finalize run summary and attach Langfuse trace information.",
  },
] as const;
