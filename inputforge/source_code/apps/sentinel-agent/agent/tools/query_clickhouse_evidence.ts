import { defineTool } from "eve/tools";
import { z } from "zod";
import { queryReadOnly, UnsafeQueryError } from "../clickhouse";

export default defineTool({
  description:
    "Query InMobi ClickHouse for read-only follow-up evidence. " +
    "and return at most 500 JSON rows. Only one uncommented SELECT/WITH " +
    "statement is permitted, and it must include a numeric LIMIT.",
  inputSchema: z.object({
    sql: z.string().describe("A ClickHouse SELECT/WITH statement."),
  }),
  async execute({ sql }) {
    try {
      return await queryReadOnly(sql);
    } catch (error) {
      if (error instanceof UnsafeQueryError) return { error: error.message };
      throw error;
    }
  },
});
