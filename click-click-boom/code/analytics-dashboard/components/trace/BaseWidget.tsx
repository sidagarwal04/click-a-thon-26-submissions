'use client';
import { useState } from 'react';
import {
  ChevronRight, ChevronDown, Database, FolderTree, BookOpen, Terminal,
  FileCode, Sparkles, GitBranch, Circle, Wrench, ShieldCheck, LineChart,
  Rocket, BookMarked, BadgeCheck,
} from 'lucide-react';

export const TOOL_META: Record<string, { icon: React.ComponentType<{ className?: string; style?: React.CSSProperties }>; label: string; accent: string; bg: string }> = {
  sql_query:      { icon: Database,    label: 'ClickHouse Query', accent: '#d97706', bg: '#fffbeb' },
  schema:         { icon: Database,    label: 'Schema',           accent: '#d97706', bg: '#fffbeb' },
  tables:         { icon: Database,    label: 'Tables',           accent: '#d97706', bg: '#fffbeb' },
  context_lookup: { icon: FolderTree,  label: 'Context',          accent: '#0d9488', bg: '#f0fdfa' },
  context_index:  { icon: FolderTree,  label: 'Context Index',    accent: '#0d9488', bg: '#f0fdfa' },
  skill_file:     { icon: BookOpen,    label: 'Skill',            accent: '#7c3aed', bg: '#faf5ff' },
  skill_list:     { icon: BookOpen,    label: 'Skill Files',      accent: '#7c3aed', bg: '#faf5ff' },
  python:         { icon: Terminal,    label: 'Python',           accent: '#16a34a', bg: '#f0fdf4' },
  scratch:        { icon: FileCode,    label: 'Scratch File',     accent: '#64748b', bg: '#f8fafc' },
  generation:     { icon: Sparkles,    label: 'Generation',       accent: '#4f46e5', bg: '#eef2ff' },
  proposal:       { icon: Wrench,      label: 'Proposal',         accent: '#d97706', bg: '#fffbeb' },
  review:         { icon: ShieldCheck, label: 'Review',           accent: '#2563eb', bg: '#eff6ff' },
  approved:       { icon: BadgeCheck,  label: 'Approved',         accent: '#0d9488', bg: '#f0fdfa' },
  insight:        { icon: LineChart,   label: 'Insight',          accent: '#16a34a', bg: '#f0fdf4' },
  execution:      { icon: Rocket,      label: 'Execution',        accent: '#0891b2', bg: '#ecfeff' },
  context_update: { icon: BookMarked,  label: 'Context Update',   accent: '#7c3aed', bg: '#faf5ff' },
  span:           { icon: GitBranch,   label: 'Span',             accent: '#6b7280', bg: '#f9fafb' },
  other:          { icon: Circle,      label: '',                 accent: '#9ca3af', bg: '#f9fafb' },
};

interface BaseWidgetProps {
  family: string;
  title: string;
  meta?: string;       // e.g. "14 rows · 12.4ms"
  error?: boolean;
  defaultOpen?: boolean;
  children: React.ReactNode;
  collapsedPreview?: React.ReactNode; // shown inline when collapsed
}

export function BaseWidget({
  family, title, meta, error, defaultOpen = false, children, collapsedPreview
}: BaseWidgetProps) {
  const [open, setOpen] = useState(defaultOpen);
  const tm = TOOL_META[family] ?? TOOL_META.other;
  const Icon = tm.icon;
  const borderColor = error ? '#fca5a5' : (open ? tm.accent + '50' : '#e5dfd6');

  return (
    <div
      className="rounded-lg border overflow-hidden mb-1"
      style={{ borderColor, backgroundColor: open ? tm.bg : '#ffffff' }}
    >
      {/* Header row — always visible */}
      <button
        onClick={() => setOpen(v => !v)}
        className="w-full flex items-center gap-2 px-3 py-2 text-left hover:bg-stone-50 transition-colors"
        style={{ backgroundColor: open ? tm.bg : undefined }}
      >
        <Icon className="h-3.5 w-3.5 flex-shrink-0" style={{ color: error ? '#dc2626' : tm.accent }} />

        <span className="flex-shrink-0 text-[9.5px] font-bold uppercase tracking-wider"
          style={{ color: error ? '#dc2626' : tm.accent }}>
          {error ? 'Error' : tm.label || family}
        </span>

        <span className="text-[12.5px] font-medium truncate flex-1" style={{ color: '#1c1814' }}>
          {title}
        </span>

        {!open && collapsedPreview && (
          <span className="text-[11px] truncate max-w-[40%] hidden sm:block" style={{ color: '#9c9088' }}>
            {collapsedPreview}
          </span>
        )}

        {meta && (
          <span className="text-[10.5px] flex-shrink-0 font-mono tabular-nums" style={{ color: '#9c9088' }}>
            {meta}
          </span>
        )}

        <span className="flex-shrink-0" style={{ color: '#c0b8b0' }}>
          {open ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
        </span>
      </button>

      {/* Body — only when expanded */}
      {open && (
        <div className="border-t" style={{ borderColor }}>
          {children}
        </div>
      )}
    </div>
  );
}
