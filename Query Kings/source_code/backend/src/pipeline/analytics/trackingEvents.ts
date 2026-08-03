export const analyticsTrackingEvents = {
  queryUnderstanding: {
    stageId: "08a_query_understanding",
    stageName: "Query Understanding",
  },
  contextRetrieval: {
    stageId: "08b_pm_context_retrieval",
    stageName: "PM Context Retrieval",
  },
  analysisPlanner: {
    stageId: "08c_analysis_planner",
    stageName: "Analysis Planner",
  },
  planCritic: {
    stageId: "08d_plan_critic",
    stageName: "Plan Critic",
  },
  sqlGenerator: {
    stageId: "08e_sql_generator",
    stageName: "SQL Generator",
  },
  analyticsPrimitives: {
    stageId: "08e2_analytics_primitives",
    stageName: "Analytics Primitives",
  },
  sqlGuardrail: {
    stageId: "08f_sql_guardrail",
    stageName: "SQL Guardrail",
  },
  queryExecutor: {
    stageId: "09_gold_query_executor",
    stageName: "Gold Query Executor",
  },
  resultEvaluator: {
    stageId: "09b_result_evaluator",
    stageName: "Result Evaluator",
  },
  insightSynthesizer: {
    stageId: "10_insight_synthesizer",
    stageName: "Insight Synthesizer",
  },
  evidenceCritic: {
    stageId: "11_evidence_critic",
    stageName: "Evidence Critic",
  },
} as const;
