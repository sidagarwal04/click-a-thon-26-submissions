'use client';
import { BookOpen } from 'lucide-react';
import { BaseWidget } from '../BaseWidget';
import type { SkillFileOutput } from '../types';

// ── Read Skill File ────────────────────────────────────────────────────────────

interface FileProps { step: string; input?: unknown; output?: unknown; defaultOpen?: boolean }

export function SkillFileWidget({ step, input, output, defaultOpen }: FileProps) {
  const path: string  = (input as any)?.file_path ?? (input as any)?.path ?? '';
  const skillName     = path.split('/')[0] ?? 'skill';
  const fileName      = path.split('/').slice(1).join('/') || path;
  const out           = output as SkillFileOutput | null;
  const content       = out?.content ?? (typeof output === 'string' ? output : '');
  const sizeKB        = content ? `${(content.length / 1024).toFixed(1)}KB` : '';

  return (
    <BaseWidget
      family="skill_file"
      title={fileName || skillName}
      meta={sizeKB}
      defaultOpen={defaultOpen}
      collapsedPreview={<span className="font-mono">{path}</span>}
    >
      <div className="p-3.5 space-y-2">
        {path && (
          <div className="flex items-center gap-2 text-[11px] font-mono px-2 py-1.5 rounded-lg"
            style={{ backgroundColor: '#faf5ff', color: '#7c3aed' }}>
            <BookOpen className="h-3.5 w-3.5" />
            <span>{path}</span>
            {sizeKB && <span className="ml-auto" style={{ color: '#a78bfa' }}>{sizeKB}</span>}
          </div>
        )}
        {content && (
          <div className="rounded-lg border overflow-hidden" style={{ borderColor: '#ddd6fe' }}>
            <pre className="p-3 text-[11.5px] leading-relaxed overflow-x-auto overflow-y-auto max-h-80 font-sans whitespace-pre-wrap"
              style={{ backgroundColor: '#faf5ff', color: '#3b0764' }}>
              {content}
            </pre>
          </div>
        )}
      </div>
    </BaseWidget>
  );
}

// ── List Skill Files ──────────────────────────────────────────────────────────

interface ListProps { step: string; input?: unknown; output?: unknown; defaultOpen?: boolean }

export function SkillListWidget({ step, input, output, defaultOpen }: ListProps) {
  const skillName: string = (input as any)?.skill_name ?? '';
  const files: { path: string; size_bytes?: number }[] = Array.isArray(output) ? output : [];

  return (
    <BaseWidget
      family="skill_list"
      title={skillName}
      meta={`${files.length} files`}
      defaultOpen={defaultOpen}
    >
      <div className="p-3.5">
        <div className="rounded-lg border overflow-hidden" style={{ borderColor: '#ddd6fe' }}>
          {files.map((f, i) => (
            <div key={i} className="flex items-center justify-between px-3 py-1.5 text-xs border-b last:border-0"
              style={{ backgroundColor: i % 2 === 0 ? '#faf5ff' : '#ffffff', borderColor: '#ede9fe' }}>
              <span className="font-mono" style={{ color: '#6d28d9' }}>{f.path}</span>
              {f.size_bytes && (
                <span className="text-[10px]" style={{ color: '#a78bfa' }}>
                  {(f.size_bytes / 1024).toFixed(1)}KB
                </span>
              )}
            </div>
          ))}
        </div>
      </div>
    </BaseWidget>
  );
}
