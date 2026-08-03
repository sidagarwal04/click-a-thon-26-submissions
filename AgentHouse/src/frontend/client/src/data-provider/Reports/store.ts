import type { AnalyticsBlock, AnalyticsReport } from 'librechat-data-provider';

const STORAGE_KEY = 'librechat.analytics.reports';

function readAll(): AnalyticsReport[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return [];
    }
    const parsed = JSON.parse(raw) as unknown;
    return Array.isArray(parsed) ? (parsed as AnalyticsReport[]) : [];
  } catch {
    return [];
  }
}

function writeAll(reports: AnalyticsReport[]): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(reports));
}

export function listReports(): AnalyticsReport[] {
  return readAll().sort((a, b) => (a.updatedAt < b.updatedAt ? 1 : -1));
}

export function getReport(id: string): AnalyticsReport | undefined {
  return readAll().find((report) => report.id === id);
}

export function createReport(input: {
  title: string;
  conversationId: string;
  blocks: AnalyticsBlock[];
}): AnalyticsReport {
  const now = new Date().toISOString();
  const report: AnalyticsReport = {
    id: crypto.randomUUID(),
    title: input.title.trim() || 'Untitled report',
    conversationId: input.conversationId,
    blocks: input.blocks,
    createdAt: now,
    updatedAt: now,
  };
  writeAll([report, ...readAll()]);
  return report;
}

export function updateReport(
  id: string,
  patch: Partial<Pick<AnalyticsReport, 'title' | 'blocks'>>,
): AnalyticsReport | undefined {
  const reports = readAll();
  const index = reports.findIndex((report) => report.id === id);
  if (index < 0) {
    return undefined;
  }

  const current = reports[index];
  const next: AnalyticsReport = {
    ...current,
    title: patch.title !== undefined ? patch.title.trim() || current.title : current.title,
    blocks: patch.blocks ?? current.blocks,
    updatedAt: new Date().toISOString(),
  };
  reports[index] = next;
  writeAll(reports);
  return next;
}

export function deleteReport(id: string): boolean {
  const reports = readAll();
  const next = reports.filter((report) => report.id !== id);
  if (next.length === reports.length) {
    return false;
  }
  writeAll(next);
  return true;
}
