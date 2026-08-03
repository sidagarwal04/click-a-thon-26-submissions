import { useState } from "react";
import { useInvestigation } from "@/useInvestigation";
import { IncidentList } from "@/components/IncidentList";
import { MetricTree } from "@/components/MetricTree";
import { FunnelChart } from "@/components/FunnelChart";
import { DiagnosisCard } from "@/components/DiagnosisCard";
import { ResponsibleSegment } from "@/components/ResponsibleSegment";
import { RuledOutList } from "@/components/RuledOutList";
import { LatencyBadge } from "@/components/LatencyBadge";
import { CompoundFindings } from "@/components/CompoundFindings";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { TooltipProvider } from "@/components/ui/tooltip";

function App() {
  const { investigation, usingFallback, error, isLoading } = useInvestigation();
  const [selected, setSelected] = useState(0);

  // On the hosted build there is no API by design, so "unreachable" would read
  // as a fault rather than the expected state. VITE_STATIC distinguishes the two:
  // a local run with a configured API that stops responding still says so.
  const isStatic = import.meta.env.VITE_STATIC === "1";
  const fallbackBanner = usingFallback ? (
    isStatic ? (
      <div className="border-b border-sky-500/30 bg-sky-500/10 px-4 py-1.5 text-xs text-sky-700 dark:text-sky-300">
        Static demo — no backend attached. Showing a completed investigation over{" "}
        <span className="font-mono">{investigation?.window_start}</span> →{" "}
        <span className="font-mono">{investigation?.window_end}</span>, exported verbatim
        from a real <span className="font-mono">./investigate.sh</span> run. Every number
        here was computed by the engine from ClickHouse.
      </div>
    ) : (
      <div className="border-b border-amber-500/30 bg-amber-500/10 px-4 py-1.5 text-xs text-amber-600 dark:text-amber-400">
        API unreachable — showing a cached investigation from{" "}
        <span className="font-mono">{investigation?.window_start}</span>. Numbers are
        from a real run, but not a live one.
      </div>
    )
  ) : null;

  if (isLoading) {
    return <Centered>Loading investigation…</Centered>;
  }
  if (error || !investigation) {
    return <Centered>Failed to load investigation — run ./investigate.sh first.</Centered>;
  }
  if (investigation.events.length === 0) {
    return <Centered>No incidents found in this window.</Centered>;
  }

  const event = investigation.events[Math.min(selected, investigation.events.length - 1)];
  const narration = investigation.narrations[String(selected + 1)];

  // Compound findings carry a `day`, events carry a datetime range, and nothing
  // joins them — so an event can be labelled "no dimension met the attribution
  // bar" while the run's largest finding sits in its window. Count the overlap
  // per event so the card can point at it. Date-prefix comparison is safe here:
  // both sides are ISO-ordered, and `day` is exactly the first 10 chars.
  const compoundCounts = investigation.events.map((e) => {
    const from = e.start.slice(0, 10);
    const to = e.end.slice(0, 10);
    return investigation.compound_findings.filter((c) => c.day >= from && c.day <= to).length;
  });

  return (
    <TooltipProvider delayDuration={200}>
      <div className="flex h-svh flex-col">
        {fallbackBanner}
        <header className="flex items-center justify-between border-b border-border px-5 py-3">
          <div>
            <h1 className="text-sm font-semibold text-foreground">InMobi RCA — Incident</h1>
            <p className="text-xs text-muted-foreground">
              {investigation.window_start} → {investigation.window_end}
            </p>
          </div>
        </header>

        <div className="flex flex-1 overflow-hidden">
          <aside className="w-80 shrink-0 border-r border-border">
            <IncidentList
              events={investigation.events}
              selected={selected}
              onSelect={setSelected}
              compoundCounts={compoundCounts}
            />
          </aside>

          <main className="flex-1 overflow-y-auto p-5">
            <div className="flex w-full flex-col gap-4">
              <LatencyBadge investigation={investigation} />

              <Tabs key={selected} defaultValue="metric-tree">
                <TabsList>
                  <TabsTrigger value="metric-tree">Metric tree</TabsTrigger>
                  <TabsTrigger value="funnel">Funnel</TabsTrigger>
                  <TabsTrigger value="diagnosis">Diagnosis</TabsTrigger>
                  <TabsTrigger value="ruled-out">Checked &amp; ruled out</TabsTrigger>
                </TabsList>

                <TabsContent value="metric-tree">
                  <MetricTree
                    decomposition={event.decomposition}
                    classification={event.classification}
                    responsible={event.responsible}
                  />
                </TabsContent>
                <TabsContent value="funnel">
                  <FunnelChart actual={event.decomposition.actual} baseline={event.decomposition.baseline} />
                </TabsContent>
                <TabsContent value="diagnosis">
                  <DiagnosisCard narration={narration} signature={event.signature} />
                </TabsContent>
                <TabsContent value="ruled-out" className="flex flex-col gap-4">
                  <ResponsibleSegment responsible={event.responsible} />
                  <RuledOutList ruledOut={event.ruled_out} />
                </TabsContent>
              </Tabs>

              <CompoundFindings findings={investigation.compound_findings} />
            </div>
          </main>
        </div>
      </div>
    </TooltipProvider>
  );
}

function Centered({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-svh items-center justify-center text-sm text-muted-foreground">
      {children}
    </div>
  );
}

export default App;
