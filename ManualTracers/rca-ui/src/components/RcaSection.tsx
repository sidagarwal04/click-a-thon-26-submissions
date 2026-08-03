import type { ReactNode } from "react";

interface Props {
  title: string;
  icon?: ReactNode;
  children: ReactNode;
}

export function RcaSection({ title, icon, children }: Props) {
  return (
    <article className="border border-border bg-card/20">
      <header className="flex items-center gap-2 border-b border-border px-4 py-3">
        {icon}
        <h2>{title}</h2>
      </header>
      <div className="px-4 py-3 text-sm leading-relaxed text-foreground">{children}</div>
    </article>
  );
}
