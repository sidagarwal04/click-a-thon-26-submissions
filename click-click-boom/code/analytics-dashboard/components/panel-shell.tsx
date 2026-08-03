'use client';
import { usePanelCtx } from '@/lib/panel-context';

interface Props {
  nav: React.ReactNode;
  panel: React.ReactNode;
  children: React.ReactNode;
}

export function PanelShell({ nav, panel, children }: Props) {
  const { isOpen } = usePanelCtx();
  return (
    <div className="flex h-screen overflow-hidden">
      {nav}
      <main className="flex-1 overflow-y-auto min-w-0">
        {children}
      </main>
      {/* Panel slides in from the right — only mounted when open */}
      {isOpen && panel}
    </div>
  );
}
