import React from 'react';
import { AnomalyIncident } from '../../types';
import { AlertCircle, Clock, CheckCircle2, Flame, TrendingDown, TrendingUp } from 'lucide-react';

interface AnomalyCardProps {
  anomaly: AnomalyIncident;
  isSelected: boolean;
  onSelect: () => void;
}

const SEVERITY_STYLES: Record<string, { dot: string; label: string }> = {
  CRITICAL: { dot: 'bg-red-500',    label: 'text-red-600' },
  MAJOR:    { dot: 'bg-amber-500',  label: 'text-amber-600' },
  WARNING:  { dot: 'bg-yellow-400', label: 'text-yellow-600' },
};

const REVIEW_CONFIG = {
  APPROVED:     { icon: CheckCircle2, label: 'Approved',   cls: 'badge-green' },
  HALLUCINATION:{ icon: Flame,        label: 'Flagged',    cls: 'badge-red' },
  PENDING:      { icon: AlertCircle,  label: 'Pending',    cls: 'badge-amber' },
};

export const AnomalyCard: React.FC<AnomalyCardProps> = ({ anomaly, isSelected, onSelect }) => {
  const sev = SEVERITY_STYLES[anomaly.severity] ?? SEVERITY_STYLES.WARNING;
  const rev = REVIEW_CONFIG[anomaly.humanReview.status];
  const RevIcon = rev.icon;
  const isDrop = anomaly.pct_change < 0;

  return (
    <div
      onClick={onSelect}
      className={`p-4 rounded-xl cursor-pointer transition-all duration-150 border ${
        isSelected
          ? 'bg-brand-50 border-brand-300 shadow-glow-blue ring-2 ring-brand-100'
          : 'bg-white border-slate-200 hover:bg-slate-50 hover:border-slate-300 shadow-sm hover:shadow-md'
      }`}
    >
      {/* Top row: severity + review status */}
      <div className="flex items-center justify-between gap-2 mb-2.5">
        <div className="flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full shrink-0 ${sev.dot}`} />
          <span className={`text-[11px] font-semibold ${sev.label}`}>{anomaly.severity}</span>
          <span className="text-[10px] font-mono text-slate-400">{anomaly.id}</span>
        </div>
        <span className={`badge ${rev.cls}`}>
          <RevIcon className="w-3 h-3" />
          {rev.label}
        </span>
      </div>

      {/* Title */}
      <h3 className="text-[13px] font-semibold text-slate-900 leading-snug mb-3">{anomaly.title}</h3>

      {/* KPI mini-grid */}
      <div className="grid grid-cols-4 gap-1.5 py-2.5 px-3 rounded-lg bg-slate-50 border border-slate-100 mb-3">
        <div>
          <p className="section-label mb-0.5">Metric</p>
          <p className="text-[12px] font-bold text-slate-900 uppercase">{anomaly.metric}</p>
        </div>
        <div>
          <p className="section-label mb-0.5">Change</p>
          <p className={`text-[12px] font-bold flex items-center gap-0.5 ${isDrop ? 'text-red-600' : 'text-emerald-600'}`}>
            {isDrop ? <TrendingDown className="w-3 h-3" /> : <TrendingUp className="w-3 h-3" />}
            {anomaly.pct_change}%
          </p>
        </div>
        <div>
          <p className="section-label mb-0.5">Z-Score</p>
          <p className="text-[12px] font-mono font-bold text-amber-600">{anomaly.z_score}</p>
        </div>
        <div>
          <p className="section-label mb-0.5 text-emerald-600 font-semibold">Latency</p>
          <p className="text-[12px] font-mono font-bold text-emerald-700 flex items-center gap-0.5">
            {anomaly.evidence?.execution_time_ms || 76}ms
          </p>
        </div>
      </div>

      {/* Timestamp */}
      <div className="flex items-center gap-1.5 text-[11px] text-slate-400">
        <Clock className="w-3 h-3" />
        {anomaly.timestamp}
      </div>
    </div>
  );
};
