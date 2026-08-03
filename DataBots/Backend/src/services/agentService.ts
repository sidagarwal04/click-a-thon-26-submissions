import { OpenAI, FunctionTool, OpenAIAgent, MetadataMode } from "llamaindex";
import { getClickHouseService } from "./clickhouse.js";
import { getIndex } from "./llamaIndex.js";

// Tool 1: Query ClickHouse SQL
const clickhouseQueryTool = FunctionTool.from(
  async ({ query }: { query: string }) => {
    try {
      const chService = getClickHouseService();
      const cleaned = query.trim();
      if (!/^(SELECT|WITH|SHOW|DESCRIBE|EXPLAIN)/i.test(cleaned)) {
        return JSON.stringify({ error: "Only read-only SELECT/WITH/DESCRIBE queries are permitted." });
      }
      const rows = await chService.query(cleaned);
      const sliced = rows.slice(0, 50);
      return JSON.stringify({ row_count: rows.length, rows: sliced });
    } catch (err: any) {
      return JSON.stringify({ error: err?.message || String(err) });
    }
  },
  {
    name: "query_clickhouse",
    description: "Executes a read-only SQL query against ClickHouse database (ad_events, ad_events_hourly_rollup, approved_rca_findings). Returns row count and JSON array of results.",
    parameters: {
      type: "object",
      properties: {
        query: {
          type: "string",
          description: "The SQL SELECT/WITH query to run against ClickHouse.",
        },
      },
      required: ["query"],
    },
  }
);

// Tool 2: Trigger Go RCA Engine
const runRcaAnalysisTool = FunctionTool.from(
  async ({ metric, window_start, window_end }: { metric: string; window_start?: string; window_end?: string }) => {
    try {
      const goEngineUrl = process.env.RCA_ENGINE_URL || "http://127.0.0.1:8081";
      const resp = await fetch(`${goEngineUrl}/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ metric, window_start, window_end }),
      });
      if (!resp.ok) {
        return JSON.stringify({ error: `RCA Engine HTTP error: ${resp.status}` });
      }
      const evidence = await resp.json();
      return JSON.stringify(evidence);
    } catch (err: any) {
      return JSON.stringify({ error: `Failed to reach Go RCA Engine: ${err?.message || String(err)}` });
    }
  },
  {
    name: "run_rca_analysis",
    description: "Triggers the Go RCA Engine to perform full root cause analysis on a metric (revenue, fill_rate, render_rate, ecpm, ctr, rpr, requests) and optional window. Returns Z-scores, factor decomposition, and ranked segment contributions.",
    parameters: {
      type: "object",
      properties: {
        metric: {
          type: "string",
          description: "Target metric for RCA (e.g., revenue, fill_rate, ecpm, render_rate, ctr, rpr, requests).",
        },
        window_start: {
          type: "string",
          description: "Optional start time of anomaly window in 'YYYY-MM-DD HH:MM:SS' format.",
          nullable: true,
        },
        window_end: {
          type: "string",
          description: "Optional end time of anomaly window in 'YYYY-MM-DD HH:MM:SS' format.",
          nullable: true,
        },
      },
      required: ["metric"],
    },
  }
);

// Tool 3: Get Approved RCA Findings
const getApprovedFindingsTool = FunctionTool.from(
  async ({ limit }: { limit?: number }) => {
    try {
      const chService = getClickHouseService();
      const lim = limit && limit > 0 ? limit : 5;
      const rows = await chService.query(
        `SELECT id, metric, title, diagnosis, window_start, window_end, baseline_value, current_value, pct_change, z_score, reviewed_by, reviewed_at FROM approved_rca_findings ORDER BY reviewed_at DESC LIMIT ${lim}`
      );
      return JSON.stringify({ count: rows.length, findings: rows });
    } catch (err: any) {
      return JSON.stringify({ findings: [], message: "No approved findings found in database." });
    }
  },
  {
    name: "get_approved_rca_findings",
    description: "Retrieves human-verified and approved RCA findings stored in ClickHouse.",
    parameters: {
      type: "object",
      properties: {
        limit: {
          type: "number",
          description: "Number of recent approved findings to retrieve (default 5).",
          nullable: true,
        },
      },
      required: [],
    },
  }
);

// Tool 4: Inspect Database Schema
const getDatabaseSchemaTool = FunctionTool.from(
  async ({ table_name }: { table_name?: string }) => {
    try {
      const chService = getClickHouseService();
      if (table_name) {
        const cols = await chService.describeTable("default", table_name);
        return JSON.stringify({ table: table_name, columns: cols });
      }
      const tables = await chService.listTables("default");
      return JSON.stringify({
        tables: tables.map((t) => t.name),
        dictionaries: ["apps_dict", "advertisers_dict", "geo_device_dict"],
        key_tables: {
          ad_events: "Raw event table (event_time, ad_format, category, publisher_tier, vertical, campaign_type, region, country, device_model, os_version, is_filled, is_impression, is_click, revenue)",
          ad_events_hourly_rollup: "Pre-aggregated hourly rollups (event_hour, dim_name, dim_val, requests, fills, impressions, clicks, revenue)",
          approved_rca_findings: "Human-reviewed and approved RCA findings",
        },
      });
    } catch (err: any) {
      return JSON.stringify({ error: err?.message || String(err) });
    }
  },
  {
    name: "get_database_schema",
    description: "Inspects ClickHouse tables, column definitions, and available dictionaries.",
    parameters: {
      type: "object",
      properties: {
        table_name: {
          type: "string",
          description: "Optional specific table name to describe.",
          nullable: true,
        },
      },
      required: [],
    },
  }
);

// Tool 5: Search Knowledge Base
const searchKnowledgeBaseTool = FunctionTool.from(
  async ({ query }: { query: string }) => {
    try {
      const index = getIndex();
      if (!index) {
        return JSON.stringify({ info: "Vector store index not loaded yet. Use metrics glossary rules." });
      }
      const retriever = index.asRetriever({ similarityTopK: 3 });
      const nodes = await retriever.retrieve({ query });
      const textResults = nodes.map((n) => n.node.getContent(MetadataMode.NONE));
      return JSON.stringify({ results: textResults });
    } catch (err: any) {
      return JSON.stringify({ info: "Knowledge base search unavailable", error: err?.message });
    }
  },
  {
    name: "search_knowledge_base",
    description: "Queries the LlamaIndex vector store for metrics definitions and documentation.",
    parameters: {
      type: "object",
      properties: {
        query: {
          type: "string",
          description: "Query text to search in knowledge base.",
        },
      },
      required: ["query"],
    },
  }
);

export function createRcaLlamaIndexAgent(): OpenAIAgent {
  const apiKey = process.env.DEEPSEEK_API_KEY || process.env.OPENAI_API_KEY || "sk-e1e69e5126834a5cbef3db3c420d64c6";
  const baseURL = process.env.DEEPSEEK_BASE_URL || "https://api.deepseek.com";
  const model = process.env.DEEPSEEK_MODEL || "deepseek-chat";

  if (!process.env.OPENAI_API_KEY) {
    process.env.OPENAI_API_KEY = apiKey;
  }

  const llm = new OpenAI({
    apiKey,
    additionalSessionOptions: { baseURL },
    model,
    temperature: 0.1,
  });

  const tools = [
    clickhouseQueryTool,
    runRcaAnalysisTool,
    getApprovedFindingsTool,
    getDatabaseSchemaTool,
    searchKnowledgeBaseTool,
  ];

  const systemPrompt = `You are an expert AI Root Cause Analysis (RCA) Analyst for the InMobi AdTech platform.
You are powered by LlamaIndex and connected directly to ClickHouse Cloud analytical database.

CORE INSTRUCTIONS:
1. Always base your answers on empirical data obtained via your ClickHouse tools.
2. NEVER hallucinate or invent numbers, percentages, or assumptions. Every metric figure you state MUST come directly from ClickHouse query results or RCA evidence.
3. Use 'query_clickhouse' to run SQL queries whenever you need exact figures from 'ad_events', 'ad_events_hourly_rollup', or 'approved_rca_findings'.
4. Use 'run_rca_analysis' when asked to detect or investigate root causes for revenue, fill rate, eCPM, render rate, CTR, or request volume anomalies.
5. Use half-open time ranges: event_time >= start AND event_time < end.
6. Calculate actual deltas and contribution shares from ClickHouse.
7. Be concise, structured, and professional in your response.`;

  return new OpenAIAgent({
    tools,
    llm,
    systemPrompt,
    verbose: true,
  });
}
