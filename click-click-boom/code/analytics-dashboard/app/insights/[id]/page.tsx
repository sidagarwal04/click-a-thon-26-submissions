'use client';

import { use, useEffect, useState } from 'react';
import Link from 'next/link';
import { ArrowLeft, ExternalLink, Loader2 } from 'lucide-react';

interface InsightMeta {
  insight_id: string;
  spec_name: string;
  title: string;
  trace_url: string | null;
}

export default function InsightReportPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [meta, setMeta] = useState<InsightMeta | null>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    fetch('/api/insights')
      .then((r) => r.json())
      .then((all: InsightMeta[]) => {
        const found = all.find((i) => i.insight_id === id);
        if (found) setMeta(found);
      })
      .catch(() => {});
  }, [id]);

  return (
    <div className="flex h-screen flex-col" style={{ backgroundColor: '#faf8f5' }}>
      <div className="flex flex-shrink-0 items-center gap-3 border-b px-5 py-3" style={{ borderColor: '#e5dfd6', backgroundColor: '#ffffff' }}>
        <Link href="/insights" className="flex items-center gap-1.5 text-xs font-medium hover:opacity-70" style={{ color: '#7a7068' }}>
          <ArrowLeft className="h-3.5 w-3.5" /> All insights
        </Link>
        <div className="mx-2 h-4 w-px" style={{ backgroundColor: '#e5dfd6' }} />
        <span className="truncate text-sm font-semibold" style={{ color: '#1c1814' }}>
          {meta?.title ?? 'Insight report'}
        </span>
        {meta?.trace_url && (
          <a href={meta.trace_url} target="_blank" rel="noopener noreferrer"
            className="ml-auto flex flex-shrink-0 items-center gap-1 text-xs font-medium hover:opacity-70"
            style={{ color: '#2563eb' }}>
            View trace <ExternalLink className="h-3 w-3" />
          </a>
        )}
      </div>

      <div className="relative flex-1">
        {!loaded && (
          <div className="absolute inset-0 flex items-center justify-center gap-2 text-sm" style={{ color: '#9c9088' }}>
            <Loader2 className="h-4 w-4 animate-spin" /> Loading report…
          </div>
        )}
        {/* The report is the agent's own standalone HTML document, loaded via src
            (not injected inline) -- keeps its <style> scoped to itself instead of
            leaking into or colliding with the dashboard's own styles. */}
        <iframe
          src={`/api/insights/${id}/report`}
          onLoad={() => setLoaded(true)}
          className="h-full w-full border-0"
          style={{ opacity: loaded ? 1 : 0, transition: 'opacity 150ms' }}
          title="Insight report"
        />
      </div>
    </div>
  );
}
