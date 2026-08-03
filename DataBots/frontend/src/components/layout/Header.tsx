import React from 'react';
import { ModuleType } from '../../types';
import { ChevronRight, Database, Activity, Bell } from 'lucide-react';

interface HeaderProps {
  activeModule: ModuleType;
  anomaliesCount: number;
  pendingCount: number;
}

const MODULE_TITLES: Record<ModuleType, { title: string; sub: string }> = {
  rca:       { title: 'Root Cause Analysis',  sub: 'Human-in-the-Loop Verification' },
  dashboard: { title: 'Event Stream Dashboard', sub: 'Live AdTech Metrics Monitor' },
};

export const Header: React.FC<HeaderProps> = ({ activeModule, anomaliesCount, pendingCount }) => {
  const { title, sub } = MODULE_TITLES[activeModule];

  return (
    <header className="h-14 bg-white border-b border-slate-200 px-5 flex items-center justify-between shrink-0 sticky top-0 z-20 shadow-sm">
      {/* Left: Breadcrumb */}
      <div className="flex items-center gap-2 text-[13px] min-w-0">
        <span className="text-slate-400 font-medium hidden sm:block">ClickHouse</span>
        <ChevronRight className="w-3.5 h-3.5 text-slate-300 hidden sm:block shrink-0" />
        <span className="text-slate-500 font-medium hidden sm:block">AdTech RCA</span>
        <ChevronRight className="w-3.5 h-3.5 text-slate-300 hidden sm:block shrink-0" />
        <div className="min-w-0">
          <span className="font-semibold text-slate-900 block leading-tight truncate">{title}</span>
          <span className="text-[10px] text-slate-400 block leading-tight truncate hidden sm:block">{sub}</span>
        </div>
      </div>

      {/* Right: Status indicators */}
      <div className="flex items-center gap-2.5 shrink-0">
        {/* DB status */}
        <div className="hidden md:flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-slate-50 border border-slate-200 text-[11px] text-slate-500">
          <Database className="w-3 h-3 text-emerald-500" />
          <span>ClickHouse</span>
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
        </div>

        {/* Pending review badge */}
        {pendingCount > 0 && (
          <div className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-amber-50 border border-amber-200 text-[11px] text-amber-700 font-medium">
            <Bell className="w-3 h-3" />
            <span>{pendingCount} Pending</span>
          </div>
        )}

        {/* User avatar */}
        <div className="flex items-center gap-2 pl-2.5 border-l border-slate-200">
          <div className="w-7 h-7 rounded-full bg-brand-600 border border-brand-500 flex items-center justify-center font-bold text-[11px] text-white">
            U
          </div>
          <div className="hidden lg:block text-left">
            <div className="text-[12px] font-semibold text-slate-900 leading-tight">Umesh</div>
            <div className="text-[10px] text-slate-400 leading-tight">AdOps Operator</div>
          </div>
        </div>
      </div>
    </header>
  );
};
