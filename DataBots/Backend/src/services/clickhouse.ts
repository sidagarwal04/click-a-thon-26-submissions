import { createClient, ClickHouseClient } from "@clickhouse/client";
import dotenv from "dotenv";

dotenv.config();

export interface ClickHouseDatabaseInfo {
  name: string;
  engine: string;
  comment?: string;
}

export interface ClickHouseTableInfo {
  name: string;
  database: string;
  engine: string;
}

export interface ClickHouseColumnInfo {
  name: string;
  type: string;
  default_type?: string;
  default_expression?: string;
  comment?: string;
}

export class ClickHouseService {
  private client: ClickHouseClient;

  constructor(options?: { url?: string; username?: string; password?: string; database?: string }) {
    const url = options?.url || process.env.CLICKHOUSE_URL || "https://v8k6il94hg.ap-south-1.aws.clickhouse.cloud:8443";
    const username = options?.username || process.env.CLICKHOUSE_USERNAME || process.env.CLICKHOUSE_USER || "default";
    const password = options?.password || process.env.CLICKHOUSE_PASSWORD || "i2D_29fLWj8i3";
    const database = options?.database || process.env.CLICKHOUSE_DATABASE || "default";

    this.client = createClient({
      url,
      username,
      password,
      database,
      clickhouse_settings: {
        async_insert: 1,
        wait_for_async_insert: 1,
      },
    });
  }

  /**
   * Get raw underlying ClickHouse client instance
   */
  public getRawClient(): ClickHouseClient {
    return this.client;
  }

  /**
   * Ping ClickHouse database server
   */
  public async ping(): Promise<boolean> {
    try {
      const result = await this.client.ping();
      return result.success;
    } catch (error) {
      console.error("ClickHouse ping failed:", error);
      return false;
    }
  }

  /**
   * Execute a read query and return JSON rows typed as T[]
   */
  public async query<T = Record<string, unknown>>(
    query: string,
    query_params?: Record<string, unknown>
  ): Promise<T[]> {
    try {
      const resultSet = await this.client.query({
        query,
        query_params,
        format: "JSONEachRow",
      });
      return await resultSet.json<T>();
    } catch (error) {
      console.error("ClickHouse query error:", error);
      throw error;
    }
  }

  /**
   * Execute a DDL or DML command (e.g. CREATE TABLE, ALTER, DROP)
   */
  public async exec(query: string): Promise<void> {
    try {
      await this.client.exec({ query });
    } catch (error) {
      console.error("ClickHouse exec error:", error);
      throw error;
    }
  }

  /**
   * Bulk insert records into a target table
   */
  public async insert<T extends Record<string, unknown>>(
    table: string,
    values: T[]
  ): Promise<void> {
    try {
      await this.client.insert({
        table,
        values,
        format: "JSONEachRow",
      });
    } catch (error) {
      console.error(`ClickHouse insert error on table ${table}:`, error);
      throw error;
    }
  }

  /**
   * List all available databases
   */
  public async listDatabases(): Promise<ClickHouseDatabaseInfo[]> {
    return this.query<ClickHouseDatabaseInfo>(
      "SELECT name, engine, comment FROM system.databases ORDER BY name"
    );
  }

  /**
   * List all tables in target database
   */
  public async listTables(database = "default"): Promise<ClickHouseTableInfo[]> {
    return this.query<ClickHouseTableInfo>(
      "SELECT name, database, engine FROM system.tables WHERE database = {db: String} ORDER BY name",
      { db: database }
    );
  }

  /**
   * Describe schema of a table
   */
  public async describeTable(database: string, table: string): Promise<ClickHouseColumnInfo[]> {
    return this.query<ClickHouseColumnInfo>(
      `SELECT name, type, default_kind AS default_type, default_expression, comment 
       FROM system.columns 
       WHERE database = {db: String} AND table = {tbl: String} 
       ORDER BY position`,
      { db: database, tbl: table }
    );
  }

  /**
   * Gracefully close client connection
   */
  public async close(): Promise<void> {
    await this.client.close();
  }
}

// Singleton default client instance
let defaultServiceInstance: ClickHouseService | null = null;

export function getClickHouseService(): ClickHouseService {
  if (!defaultServiceInstance) {
    defaultServiceInstance = new ClickHouseService();
  }
  return defaultServiceInstance;
}
