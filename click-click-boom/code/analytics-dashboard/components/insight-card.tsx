'use client';

import { useState } from 'react';
import { ExternalLink, ChevronDown, ChevronUp, AlertCircle, CheckCircle } from 'lucide-react';
import { cn, formatRelativeTime, getConfidenceColor, getConfidenceBgColor } from '@/lib/utils';
import type { Insight, EvidenceItem } from '@/lib/types';

interface InsightCardProps {
  insight: Insight;
}

export function InsightCard({ insight }: InsightCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  let evidence: EvidenceItem[] = [];
  let contradictions: EvidenceItem[] = [];

  try {
    evidence = JSON.parse(insight.supporting_evidence || '[]');
    contradictions = JSON.parse(insight.contradicting_signals || '[]');
  } catch (e) {
    // Ignore parse errors
  }

  const confidencePercent = Math.round(insight.confidence_score * 100);

  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-6 transition-colors hover:border-zinc-700">
      {/* Header */}
      <div className="space-y-4">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 space-y-2">
            <h3 className="text-lg font-semibold text-white">
              {insight.question}
            </h3>
            <p className="text-zinc-300 leading-relaxed">
              {insight.answer_text}
            </p>
          </div>
          <div
            className={cn(
              'flex shrink-0 flex-col items-center gap-1 rounded-lg border px-3 py-2',
              getConfidenceBgColor(insight.confidence_score)
            )}
          >
            <span className={cn('text-2xl font-bold', getConfidenceColor(insight.confidence_score))}>
              {confidencePercent}%
            </span>
            <span className="text-xs text-zinc-500">confidence</span>
          </div>
        </div>

        {/* Metadata */}
        <div className="flex items-center gap-4 text-sm text-zinc-400">
          <span>{formatRelativeTime(insight.created_at)}</span>
          <span>•</span>
          <span className="text-zinc-500">{insight.spec_id}</span>
          {insight.trace_url && (
            <>
              <span>•</span>
              <a
                href={insight.trace_url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-blue-400 hover:text-blue-300"
              >
                View trace
                <ExternalLink className="h-3 w-3" />
              </a>
            </>
          )}
        </div>
      </div>

      {/* Evidence Section */}
      {(evidence.length > 0 || contradictions.length > 0) && (
        <div className="mt-4 border-t border-zinc-800 pt-4">
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="flex w-full items-center justify-between text-sm font-medium text-zinc-300 hover:text-white"
          >
            <span>
              {evidence.length} supporting • {contradictions.length} contradicting
            </span>
            {isExpanded ? (
              <ChevronUp className="h-4 w-4" />
            ) : (
              <ChevronDown className="h-4 w-4" />
            )}
          </button>

          {isExpanded && (
            <div className="mt-4 space-y-4">
              {/* Supporting Evidence */}
              {evidence.length > 0 && (
                <div className="space-y-2">
                  <div className="flex items-center gap-2 text-sm font-medium text-green-400">
                    <CheckCircle className="h-4 w-4" />
                    <span>Supporting Evidence</span>
                  </div>
                  <div className="space-y-2">
                    {evidence.map((item, i) => (
                      <div
                        key={i}
                        className="rounded-lg border border-green-500/20 bg-green-500/5 p-3"
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div className="flex-1">
                            <p className="text-sm text-zinc-300">{item.description}</p>
                            {item.value !== undefined && (
                              <p className="mt-1 text-xs text-zinc-500">
                                Value: <span className="text-green-400">{item.value}</span>
                              </p>
                            )}
                          </div>
                          <span className="shrink-0 rounded bg-zinc-800 px-2 py-0.5 text-xs text-zinc-400">
                            {item.type}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Contradicting Signals */}
              {contradictions.length > 0 && (
                <div className="space-y-2">
                  <div className="flex items-center gap-2 text-sm font-medium text-yellow-400">
                    <AlertCircle className="h-4 w-4" />
                    <span>Contradicting Signals</span>
                  </div>
                  <div className="space-y-2">
                    {contradictions.map((item, i) => (
                      <div
                        key={i}
                        className="rounded-lg border border-yellow-500/20 bg-yellow-500/5 p-3"
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div className="flex-1">
                            <p className="text-sm text-zinc-300">{item.description}</p>
                            {item.value !== undefined && (
                              <p className="mt-1 text-xs text-zinc-500">
                                Value: <span className="text-yellow-400">{item.value}</span>
                              </p>
                            )}
                          </div>
                          <span className="shrink-0 rounded bg-zinc-800 px-2 py-0.5 text-xs text-zinc-400">
                            {item.type}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
