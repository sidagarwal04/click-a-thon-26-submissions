import React from 'react';
import { ModuleType } from '../../types';
import {
  LayoutDashboard,
  BrainCircuit,
  ChevronLeft,
  ChevronRight,
  CheckCircle2,
  AlertCircle,
  Database,
} from 'lucide-react';

interface SidebarProps {
  activeModule: ModuleType;
  setActiveModule: (mod: ModuleType) => void;
  collapsed: boolean;
  setCollapsed: (col: boolean) => void;
  anomaliesCount: number;
  pendingCount: number;
}

export const Sidebar: React.FC<SidebarProps> = ({
  activeModule,
  setActiveModule,
  collapsed,
  setCollapsed,
  anomaliesCount,
  pendingCount,
}) => {
  const navItems = [
    {
      id: 'rca' as ModuleType,
      label: 'RCA & Human Loop',
      sublabel: 'Anomaly Investigation',
      icon: BrainCircuit,
      badge: pendingCount > 0 ? pendingCount : null,
      badgeVariant: 'amber' as const,
    },
    {
      id: 'dashboard' as ModuleType,
      label: 'Event Dashboard',
      sublabel: 'Live Metrics Monitor',
      icon: LayoutDashboard,
      badge: null,
      badgeVariant: 'blue' as const,
    },
  ];

  return (
    <aside
      className={`relative flex flex-col h-screen bg-white border-r border-slate-200 transition-all duration-300 z-30 shadow-sm ${
        collapsed ? 'w-[60px]' : 'w-[220px]'
      }`}
    >
      {/* Brand Header */}
      <div className="flex items-center justify-between h-14 px-3 border-b border-slate-200 shrink-0">
        <div className="flex items-center gap-2.5 overflow-hidden min-w-0">
          <div className="w-7 h-7 rounded-lg bg-brand-600 flex items-center justify-center shrink-0">
            <Database className="w-3.5 h-3.5 text-white" />
          </div>
          {!collapsed && (
            <div className="flex flex-col min-w-0">
              <span className="font-bold text-[13px] tracking-tight text-slate-900 truncate leading-tight">
                Peekachu RCA
              </span>
              <span className="text-[10px] text-slate-400 leading-tight truncate">InMobi · Click-a-thon 2026</span>
            </div>
          )}
        </div>

        <button
          onClick={() => setCollapsed(!collapsed)}
          className="shrink-0 p-1 rounded-md text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors"
          title={collapsed ? 'Expand Sidebar' : 'Collapse Sidebar'}
        >
          {collapsed ? <ChevronRight className="w-3.5 h-3.5" /> : <ChevronLeft className="w-3.5 h-3.5" />}
        </button>
      </div>

      {/* Navigation */}
      <nav className="flex-1 py-3 px-2 space-y-0.5 overflow-y-auto">
        {!collapsed && (
          <p className="px-2 pb-2 text-[10px] font-semibold tracking-wider text-slate-400 uppercase">
            Modules
          </p>
        )}

        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = activeModule === item.id;
          return (
            <button
              key={item.id}
              onClick={() => setActiveModule(item.id)}
              title={collapsed ? item.label : undefined}
              className={`w-full flex items-center gap-2.5 px-2 py-2 rounded-lg text-sm transition-all duration-150 ${
                isActive
                  ? 'bg-brand-50 text-brand-700 border border-brand-200'
                  : 'text-slate-500 hover:text-slate-800 hover:bg-slate-50 border border-transparent'
              }`}
            >
              <Icon className={`w-4 h-4 shrink-0 ${isActive ? 'text-brand-600' : 'text-slate-400'}`} />
              {!collapsed && (
                <div className="flex-1 text-left min-w-0">
                  <div className={`text-[13px] font-semibold truncate leading-tight ${isActive ? 'text-brand-700' : 'text-slate-700'}`}>
                    {item.label}
                  </div>
                  <div className="text-[10px] text-slate-400 truncate leading-tight">{item.sublabel}</div>
                </div>
              )}
              {!collapsed && item.badge !== null && (
                <span className="shrink-0 min-w-[18px] h-[18px] flex items-center justify-center rounded-full text-[10px] font-bold bg-amber-100 text-amber-700 border border-amber-200">
                  {item.badge}
                </span>
              )}
            </button>
          );
        })}
      </nav>

      {/* Footer */}
      {!collapsed && (
        <div className="p-3 border-t border-slate-200 shrink-0">
          <div className="flex items-center gap-2 px-2 py-2 rounded-lg bg-slate-50">
            <span className="w-2 h-2 rounded-full bg-emerald-500 shrink-0" />
            <div className="min-w-0">
              <div className="text-[11px] font-semibold text-slate-700 truncate">System Online</div>
              <div className="text-[10px] text-slate-400 truncate">ClickHouse Cloud · Go Engine</div>
            </div>
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500 shrink-0 ml-auto" />
          </div>
        </div>
      )}
    </aside>
  );
};
