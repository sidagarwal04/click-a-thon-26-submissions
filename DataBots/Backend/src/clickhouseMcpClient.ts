import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";
import { FunctionTool } from "llamaindex";
import path from "path";
import dotenv from "dotenv";

dotenv.config({ path: path.resolve(process.cwd(), ".env") });

export interface MCPToolInfo {
  name: string;
  description?: string;
  inputSchema?: Record<string, unknown>;
}

/**
 * ClickHouse MCP Client for LLMs (LlamaIndex, OpenAI, DeepSeek)
 * Connects to ClickHouse MCP Server over stdio and exposes tools to LLMs.
 */
export class ClickHouseMCPLLMClient {
  private client: Client | null = null;
  private transport: StdioClientTransport | null = null;
  private connected = false;

  /**
   * Connect to the ClickHouse MCP Server process over stdio
   */
  public async connect(): Promise<void> {
    if (this.connected) return;

    const wrapperPath = path.resolve(process.cwd(), "mcp_wrapper.py");

    this.transport = new StdioClientTransport({
      command: "python3",
      args: [wrapperPath],
      env: process.env as Record<string, string>,
    });

    this.client = new Client(
      {
        name: "clickhouse-mcp-llm-client",
        version: "1.0.0",
      },
      {
        capabilities: {},
      }
    );

    await this.client.connect(this.transport);
    this.connected = true;
  }

  /**
   * List available ClickHouse MCP tools
   */
  public async listTools(): Promise<MCPToolInfo[]> {
    await this.connect();
    const res = await this.client!.listTools();
    return res.tools.map((t: any) => ({
      name: t.name,
      description: t.description,
      inputSchema: t.inputSchema as Record<string, unknown>,
    }));
  }

  /**
   * Execute an MCP tool by name with arguments
   */
  public async callTool(name: string, args: Record<string, unknown> = {}): Promise<unknown> {
    await this.connect();
    const result = await this.client!.callTool({
      name,
      arguments: args,
    });
    return result;
  }

  /**
   * Convert MCP tools to LlamaIndex FunctionTools array for ReAct LLM Agents
   */
  public async getLlamaIndexTools(): Promise<FunctionTool<any, any>[]> {
    const tools = await this.listTools();

    return tools.map((tool) => {
      return new FunctionTool(
        async (input: Record<string, unknown>) => {
          const res = await this.callTool(tool.name, input);
          return JSON.stringify(res);
        },
        {
          name: tool.name,
          description: tool.description || `ClickHouse MCP Tool: ${tool.name}`,
          parameters: (tool.inputSchema as any) || {
            type: "object",
            properties: {},
          },
        }
      );
    });
  }

  /**
   * Convert MCP tools to OpenAI / DeepSeek function calling definitions
   */
  public async getOpenAITools(): Promise<Array<{ type: "function"; function: { name: string; description: string; parameters: object } }>> {
    const tools = await this.listTools();
    return tools.map((t) => ({
      type: "function" as const,
      function: {
        name: t.name,
        description: t.description || `ClickHouse MCP tool ${t.name}`,
        parameters: (t.inputSchema as object) || { type: "object", properties: {} },
      },
    }));
  }

  /**
   * Sever connection
   */
  public async close(): Promise<void> {
    if (this.transport) {
      await this.transport.close();
      this.connected = false;
      this.client = null;
      this.transport = null;
    }
  }
}

// Helper factory for global singleton instance
let instance: ClickHouseMCPLLMClient | null = null;

export function getClickHouseMCPLLMClient(): ClickHouseMCPLLMClient {
  if (!instance) {
    instance = new ClickHouseMCPLLMClient();
  }
  return instance;
}
