/** Shared Langfuse deep-link helper for report HTML. */

export function langfuseTraceUrl(traceId: string): string {
  if (!traceId) return "";

  const template = process.env.LANGFUSE_TRACE_URL_TEMPLATE?.trim();
  if (template) {
    return template
      .replaceAll("{trace_id}", traceId)
      .replaceAll("{id}", traceId);
  }

  const base =
    process.env.LANGFUSE_BASE_URL?.replace(/\/$/, "") ||
    process.env.LANGFUSE_HOST?.replace(/\/$/, "") ||
    "http://localhost:3000";

  const projectId = process.env.LANGFUSE_PROJECT_ID?.trim();
  // Direct trace URL (works for public/shared traces). Search URLs require login.
  if (projectId) {
    return `${base}/project/${projectId}/traces/${encodeURIComponent(traceId)}`;
  }

  return `${base}/traces/${encodeURIComponent(traceId)}`;
}
