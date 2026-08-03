import { useCallback, useEffect, useState } from "react";
import { AlertCircle, ClipboardList } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { CandidateTable } from "@/components/CandidateTable";
import { ContributionChart } from "@/components/ContributionChart";
import { GlobalMetricChart } from "@/components/GlobalMetricChart";
import { RcaFilterToolbar } from "@/components/RcaFilterToolbar";
import { RcaList } from "@/components/RcaList";
import { RcaSection } from "@/components/RcaSection";
import { RuledOutList } from "@/components/RuledOutList";
import { SegmentTrendChart } from "@/components/SegmentTrendChart";
import { TriggerCard } from "@/components/TriggerCard";
import {
  API_BASE,
  fetchRcaDashboard,
  fetchReport,
  fetchReports,
} from "@/lib/api";
import type {
  ContributionRow,
  GlobalSeriesRow,
  RcaFilters,
  RcaReport,
  RcaReportSummary,
  SegmentSeriesRow,
} from "@/lib/types";

function defaultFilters(report: RcaReport | null): RcaFilters {
  if (!report) {
    return {
      from: "2026-06-20T00:00:00",
      to: "2026-06-30T23:59:59",
      os_versions: [],
      granularity: "day",
    };
  }
  const culprit = report.candidates[0]?.dim_value;
  return {
    from: report.trigger.window.start,
    to: report.trigger.window.end,
    os_versions: culprit ? [culprit] : [],
    granularity: "hour",
  };
}

export default function App() {
  const [reports, setReports] = useState<RcaReportSummary[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [report, setReport] = useState<RcaReport | null>(null);
  const [draftFilters, setDraftFilters] = useState<RcaFilters>(defaultFilters(null));
  const [loading, setLoading] = useState(false);
  const [chartLoading, setChartLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [globalSeries, setGlobalSeries] = useState<GlobalSeriesRow[]>([]);
  const [segmentSeries, setSegmentSeries] = useState<SegmentSeriesRow[]>([]);
  const [contributions, setContributions] = useState<ContributionRow[]>([]);

  useEffect(() => {
    fetchReports()
      .then((list) => {
        setReports(list);
        if (list.length > 0) setSelectedId(list[0].id);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load reports"));
  }, []);

  useEffect(() => {
    if (!selectedId) return;
    setLoading(true);
    setError(null);
    fetchReport(selectedId)
      .then(async (r) => {
        setReport(r);
        const f = defaultFilters(r);
        setDraftFilters(f);
        setChartLoading(true);
        try {
          const data = await fetchRcaDashboard(selectedId, f);
          setGlobalSeries(data.globalSeries);
          setSegmentSeries(data.segmentSeries);
          setContributions(data.contributions);
        } catch (e) {
          setError(
            e instanceof Error
              ? `${e.message}. Is the API running at ${API_BASE}?`
              : "Chart request failed",
          );
        } finally {
          setChartLoading(false);
        }
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load report"))
      .finally(() => setLoading(false));
  }, [selectedId]);

  const refreshCharts = useCallback(async () => {
    if (!selectedId) return;
    setChartLoading(true);
    try {
      const data = await fetchRcaDashboard(selectedId, draftFilters);
      setGlobalSeries(data.globalSeries);
      setSegmentSeries(data.segmentSeries);
      setContributions(data.contributions);
    } catch (e) {
      setError(
        e instanceof Error
          ? `${e.message}. Is the API running at ${API_BASE}?`
          : "Chart request failed",
      );
    } finally {
      setChartLoading(false);
    }
  }, [selectedId, draftFilters]);

  const culprit = report?.candidates[0]?.dim_value;

  return (
    <div className="dark min-h-screen bg-background">
      <header className="border-b border-border px-4 py-4">
        <div className="mx-auto flex max-w-[1600px] flex-wrap items-start justify-between gap-3">
          <div>
            <div className="mb-1 flex items-center gap-2">
              <Badge variant="outline" className="text-[10px] font-normal uppercase tracking-wider">
                RCA Viewer
              </Badge>
              <Badge variant="secondary" className="text-[10px] font-normal">
                Template
              </Badge>
            </div>
            <h1 className="text-foreground">InMobi Root Cause Reports</h1>
            <p className="mt-1 max-w-xl text-sm leading-relaxed text-muted-foreground">
              Evidence-backed diagnoses from the RCA agent ledger. Charts are filterable; all
              numbers trace to computed findings, not LLM invention.
            </p>
          </div>
          <code className="rounded bg-muted px-2 py-1 font-mono text-xs text-muted-foreground">
            {API_BASE}
          </code>
        </div>
      </header>

      <div className="mx-auto grid max-w-[1600px] lg:grid-cols-[280px_1fr]">
        <RcaList reports={reports} selectedId={selectedId} onSelect={setSelectedId} />

        <div className="min-w-0">
          {error && (
            <Alert variant="destructive" className="m-4">
              <AlertCircle className="h-4 w-4" />
              <AlertTitle>Error</AlertTitle>
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          {loading || !report ? (
            <p className="p-8 text-sm text-muted-foreground">Loading report…</p>
          ) : (
            <>
              <div className="border-b border-border px-4 py-3">
                <h2 className="text-base font-semibold text-foreground">{report.title}</h2>
                <p className="mt-0.5 font-mono text-xs text-muted-foreground">{report.id}</p>
              </div>

              <RcaFilterToolbar
                filters={draftFilters}
                onChange={setDraftFilters}
                onApply={refreshCharts}
                loading={chartLoading}
                defaultOs={culprit}
              />

              <main className="space-y-4 p-4">
                <TriggerCard trigger={report.trigger} status={report.status} />

                <RcaSection title="What went wrong">
                  {report.sections.what_went_wrong}
                </RcaSection>

                <RcaSection title="Why it happened">
                  {report.sections.why_it_happened || "No finding — nothing to explain."}
                  {report.holdout && (
                    <div className="mt-3 rounded-sm border border-border bg-muted/20 p-3 font-mono text-xs text-muted-foreground">
                      {/* residual_actual/residual_delta are null when the holdout complement
                          matched zero rows (candidate is ~all the traffic in this window) —
                          the comparison genuinely couldn't be made, not just "no finding" */}
                      Holdout: residual{" "}
                      {report.holdout.residual_actual !== null
                        ? report.holdout.residual_actual.toFixed(4)
                        : "n/a"}{" "}
                      (Δ{" "}
                      {report.holdout.residual_delta !== null
                        ? report.holdout.residual_delta.toFixed(4)
                        : "n/a"}
                      ) · candidate Δ {report.holdout.candidate_delta.toFixed(4)} · verdict{" "}
                      {report.holdout.verdict}
                    </div>
                  )}
                </RcaSection>

                {report.sections.supporting_data_summary && (
                  <RcaSection
                    title="Supporting data"
                    icon={<ClipboardList className="h-4 w-4 text-muted-foreground" aria-hidden />}
                  >
                    {report.sections.supporting_data_summary}
                  </RcaSection>
                )}

                {report.candidates.length > 0 && (
                  <>
                    <div className="grid gap-4 lg:grid-cols-2">
                      <GlobalMetricChart
                        title={`Global ${report.trigger.metric_id} — actual vs expected`}
                        rows={globalSeries}
                        loading={chartLoading}
                      />
                      <SegmentTrendChart rows={segmentSeries} loading={chartLoading} />
                    </div>

                    <div className="grid gap-4 lg:grid-cols-2">
                      <ContributionChart rows={contributions} loading={chartLoading} />
                      <CandidateTable rows={report.candidates} />
                    </div>

                    <RuledOutList
                      items={report.ruled_out}
                      candidatesTested={report.candidates.length}
                    />
                  </>
                )}
              </main>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
