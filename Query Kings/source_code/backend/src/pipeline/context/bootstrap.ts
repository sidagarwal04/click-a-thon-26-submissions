import { readFile } from "node:fs/promises";
import path from "node:path";
import { ensureContextTables } from "./tables.js";
import { readGeneratedContext } from "./read.js";
import { ingestBaseContextDocuments } from "./write.js";
import { ContextBundle } from "./types.js";

export async function loadContextBundle(
  repoRoot: string,
): Promise<ContextBundle> {
  await ensureContextTables();
  const [baseContext, existingDdl, instrumentationNotes] = await Promise.all([
    readFile(path.join(repoRoot, "base_context.md"), "utf8"),
    readFile(path.join(repoRoot, "data", "ddl.sql"), "utf8"),
    readFile(path.join(repoRoot, "data", "instrumentation_notes.md"), "utf8"),
  ]);

  await ingestBaseContextDocuments({
    repoRoot,
    jobId: "bootstrap",
    baseContext,
    existingDdl,
    instrumentationNotes,
  });

  return {
    baseContext,
    existingDdl,
    instrumentationNotes,
    generatedContext: await readGeneratedContext(),
  };
}

export async function bootstrapContext(repoRoot: string) {
  await ensureContextTables();
  const [baseContext, existingDdl, instrumentationNotes] = await Promise.all([
    readFile(path.join(repoRoot, "base_context.md"), "utf8"),
    readFile(path.join(repoRoot, "data", "ddl.sql"), "utf8"),
    readFile(path.join(repoRoot, "data", "instrumentation_notes.md"), "utf8"),
  ]);

  await ingestBaseContextDocuments({
    repoRoot,
    jobId: `bootstrap_${new Date()
      .toISOString()
      .replace(/[-:]/g, "")
      .replace(/\..+/, "")}`,
    baseContext,
    existingDdl,
    instrumentationNotes,
  });

  return readGeneratedContext();
}
