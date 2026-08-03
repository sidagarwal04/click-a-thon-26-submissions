'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { cn } from '@/lib/utils';
import {
  LayoutDashboard,
  MessageSquare,
  Lightbulb,
  Database,
  Activity,
  GitBranch,
  Upload,
} from 'lucide-react';

const navigation = [
  { name: 'Dashboard', href: '/', icon: LayoutDashboard },
  { name: 'Ingest Spec', href: '/ingest', icon: Upload },
  { name: 'Analytics Chat', href: '/chat', icon: MessageSquare },
  { name: 'Insights', href: '/insights', icon: Lightbulb },
  { name: 'Schema Proposals', href: '/schemas', icon: Database },
  { name: 'Context History', href: '/context', icon: GitBranch },
  { name: 'Test Runs', href: '/tests', icon: Activity },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <div className="flex h-screen w-64 flex-col border-r border-zinc-800 bg-zinc-900">
      {/* Logo */}
      <div className="flex h-16 items-center border-b border-zinc-800 px-6">
        <div className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-blue-500 to-purple-600">
            <Lightbulb className="h-5 w-5 text-white" />
          </div>
          <div>
            <h1 className="text-lg font-semibold text-white">Atlys Agents</h1>
            <p className="text-xs text-zinc-400">Analytics Dashboard</p>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 space-y-1 px-3 py-4">
        {navigation.map((item) => {
          const isActive = pathname === item.href;
          return (
            <Link
              key={item.name}
              href={item.href}
              className={cn(
                'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                isActive
                  ? 'bg-zinc-800 text-white'
                  : 'text-zinc-400 hover:bg-zinc-800/50 hover:text-white'
              )}
            >
              <item.icon className="h-5 w-5" />
              {item.name}
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="border-t border-zinc-800 p-4">
        <div className="space-y-2 text-xs text-zinc-500">
          <div className="flex items-center justify-between">
            <span>LibreChat</span>
            <span className="inline-flex items-center gap-1">
              <span className="h-2 w-2 rounded-full bg-green-500"></span>
              Online
            </span>
          </div>
          <div className="flex items-center justify-between">
            <span>ClickHouse</span>
            <span className="inline-flex items-center gap-1">
              <span className="h-2 w-2 rounded-full bg-green-500"></span>
              Connected
            </span>
          </div>
          <div className="flex items-center justify-between">
            <span>Langfuse</span>
            <span className="inline-flex items-center gap-1">
              <span className="h-2 w-2 rounded-full bg-green-500"></span>
              Tracing
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
