'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { cn } from '@/lib/utils';
import { FileText, Lightbulb, Database, BookOpen } from 'lucide-react';

// Traces used to be its own nav item, but a run's live trace (reasoning +
// every tool call, same widgets) now renders directly in the run panel on
// the right as it happens -- a separate historical-replay page is redundant
// with that and was never wired to real data anyway (mock events only).
const nav = [
  { name: 'Specs',    href: '/specs',    icon: FileText  },
  { name: 'Insights', href: '/insights', icon: Lightbulb },
  { name: 'Schemas',  href: '/schemas',  icon: Database  },
  { name: 'Context',  href: '/context',  icon: BookOpen  },
];

export function LeftNav() {
  const pathname = usePathname();

  return (
    <div className="flex h-screen w-44 flex-shrink-0 flex-col border-r"
      style={{ backgroundColor: '#ffffff', borderColor: '#e5dfd6' }}>

      {/* Logo */}
      <div className="flex h-14 flex-shrink-0 items-center gap-2.5 border-b px-4"
        style={{ borderColor: '#e5dfd6' }}>
        <div className="flex h-7 w-7 items-center justify-center rounded-md bg-gradient-to-br from-blue-500 to-violet-600">
          <Lightbulb className="h-4 w-4 text-white" />
        </div>
        <div>
          <p className="text-sm font-semibold leading-tight" style={{ color: '#1c1814' }}>Atlys</p>
          <p className="text-[10px] leading-tight" style={{ color: '#9c9088' }}>Agent Pipeline</p>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 space-y-0.5 px-2 py-3">
        {nav.map(({ name, href, icon: Icon }) => {
          const active = pathname === href || pathname.startsWith(href + '/');
          return (
            <Link key={href} href={href}
              className="flex items-center gap-2.5 rounded-md px-3 py-2 text-sm font-medium transition-colors"
              style={{
                backgroundColor: active ? '#ede8e0' : 'transparent',
                color: active ? '#1c1814' : '#7a7068',
              }}>
              <Icon className="h-4 w-4 flex-shrink-0" />
              {name}
            </Link>
          );
        })}
      </nav>

      {/* Status */}
      <div className="flex-shrink-0 border-t p-3 space-y-1.5" style={{ borderColor: '#e5dfd6' }}>
        {['ClickHouse', 'Langfuse'].map(svc => (
          <div key={svc} className="flex items-center justify-between text-xs">
            <span style={{ color: '#9c9088' }}>{svc}</span>
            <span className="flex items-center gap-1" style={{ color: '#22c55e' }}>
              <span className="h-1.5 w-1.5 rounded-full bg-green-500" />
              OK
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
