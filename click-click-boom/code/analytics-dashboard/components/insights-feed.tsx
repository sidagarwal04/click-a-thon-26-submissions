'use client';

import { useEffect, useState } from 'react';
import { Loader2, Filter, TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { InsightCard } from './insight-card';
import type { Insight } from '@/lib/types';

export function InsightsFeed() {
  const [insights, setInsights] = useState<Insight[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [filter, setFilter] = useState<'all' | 'high' | 'medium' | 'low'>('all');

  useEffect(() => {
    fetchInsights();
  }, []);

  const fetchInsights = async () => {
    try {
      const response = await fetch('/api/insights');
      const data = await response.json();
      // Ensure we always set an array, even if there's an error
      setInsights(Array.isArray(data) ? data : []);
    } catch (error) {
      console.error('Failed to fetch insights:', error);
      setInsights([]);
    } finally {
      setIsLoading(false);
    }
  };

  const filteredInsights = insights.filter((insight) => {
    if (filter === 'all') return true;
    if (filter === 'high') return insight.confidence_score >= 0.8;
    if (filter === 'medium') return insight.confidence_score >= 0.6 && insight.confidence_score < 0.8;
    if (filter === 'low') return insight.confidence_score < 0.6;
    return true;
  });

  const stats = {
    total: insights.length,
    high: insights.filter((i) => i.confidence_score >= 0.8).length,
    medium: insights.filter((i) => i.confidence_score >= 0.6 && i.confidence_score < 0.8).length,
    low: insights.filter((i) => i.confidence_score < 0.6).length,
    avgConfidence: insights.length > 0
      ? Math.round((insights.reduce((sum, i) => sum + i.confidence_score, 0) / insights.length) * 100)
      : 0,
  };

  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="flex items-center gap-2 text-zinc-400">
          <Loader2 className="h-5 w-5 animate-spin" />
          <span>Loading insights...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Stats Bar */}
      <div className="grid grid-cols-4 gap-4">
        <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-4">
          <div className="text-2xl font-bold text-white">{stats.total}</div>
          <div className="text-sm text-zinc-400">Total Insights</div>
        </div>
        <div className="rounded-lg border border-green-500/20 bg-green-500/5 p-4">
          <div className="flex items-center gap-2">
            <TrendingUp className="h-5 w-5 text-green-500" />
            <span className="text-2xl font-bold text-green-500">{stats.high}</span>
          </div>
          <div className="text-sm text-zinc-400">High Confidence</div>
        </div>
        <div className="rounded-lg border border-yellow-500/20 bg-yellow-500/5 p-4">
          <div className="flex items-center gap-2">
            <Minus className="h-5 w-5 text-yellow-500" />
            <span className="text-2xl font-bold text-yellow-500">{stats.medium}</span>
          </div>
          <div className="text-sm text-zinc-400">Medium Confidence</div>
        </div>
        <div className="rounded-lg border border-red-500/20 bg-red-500/5 p-4">
          <div className="flex items-center gap-2">
            <TrendingDown className="h-5 w-5 text-red-500" />
            <span className="text-2xl font-bold text-red-500">{stats.low}</span>
          </div>
          <div className="text-sm text-zinc-400">Low Confidence</div>
        </div>
      </div>

      {/* Filter Bar */}
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-white">
          Recent Insights
        </h2>
        <div className="flex items-center gap-2">
          <Filter className="h-4 w-4 text-zinc-400" />
          <select
            value={filter}
            onChange={(e) => setFilter(e.target.value as any)}
            className="rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-1.5 text-sm text-white focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            <option value="all">All ({stats.total})</option>
            <option value="high">High Confidence ({stats.high})</option>
            <option value="medium">Medium Confidence ({stats.medium})</option>
            <option value="low">Low Confidence ({stats.low})</option>
          </select>
        </div>
      </div>

      {/* Insights List */}
      {filteredInsights.length === 0 ? (
        <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-12 text-center">
          <p className="text-zinc-400">No insights found matching the selected filter.</p>
        </div>
      ) : (
        <div className="space-y-4">
          {filteredInsights.map((insight) => (
            <InsightCard key={insight.insight_id} insight={insight} />
          ))}
        </div>
      )}
    </div>
  );
}
