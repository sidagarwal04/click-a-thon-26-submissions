import type { Classification, Event } from "@/types";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

const CHIP_STYLE: Record<Classification, string> = {
  localized: "bg-[#d03b3b26] text-[#e66767] border-[#d03b3b66]",
  global: "bg-[#fab21926] text-[#fab219] border-[#fab21966]",
  unattributed: "bg-[#89878126] text-[#c3c2b7] border-[#89878166]",
};

export function IncidentList({
  events,
  selected,
  onSelect,
  compoundCounts,
}: {
  events: Event[];
  selected: number;
  onSelect: (index: number) => void;
  // Compound findings are investigation-wide, not attached to an event. Without
  // this pointer the 06-28 card reads "no dimension met the attribution bar"
  // while the compound scan has, in that same window, the largest finding of
  // the whole run — a flat contradiction to anyone who doesn't scroll.
  compoundCounts?: number[];
}) {
  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-border px-4 py-3">
        <h2 className="text-sm font-semibold text-foreground">Incidents</h2>
        <p className="text-xs text-muted-foreground">{events.length} found, most severe first</p>
      </div>
      <ScrollArea className="flex-1">
        <div className="flex flex-col gap-1 p-2">
          {events.map((e, i) => (
            <button
              key={`${e.start}-${e.end}`}
              onClick={() => onSelect(i)}
              className={`rounded-md border p-3 text-left transition-colors ${
                i === selected
                  ? "border-ring bg-accent"
                  : "border-transparent hover:bg-accent/50"
              }`}
            >
              <div className="flex items-center justify-between gap-2">
                <span className={`rounded-full border px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide ${CHIP_STYLE[e.classification]}`}>
                  {e.classification}
                </span>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <span className="cursor-help text-xs tabular-nums text-muted-foreground underline decoration-dotted underline-offset-2">
                      sev {e.severity.toFixed(1)}
                    </span>
                  </TooltipTrigger>
                  <TooltipContent className="flex w-64 max-w-64 flex-col items-start gap-1 whitespace-normal text-left text-xs">
                    <p className="font-medium">Severity = |peak % deviation| × hours it lasted</p>
                    {e.triggers[0] && (
                      <p className="text-muted-foreground">
                        Here: {e.triggers[0].scope} {e.triggers[0].metric}{" "}
                        {(e.triggers[0].mean_pct_change * 100).toFixed(1)}% over {e.triggers[0].hours}h.
                      </p>
                    )}
                  </TooltipContent>
                </Tooltip>
              </div>
              <div className="mt-1.5 text-xs text-muted-foreground">
                {e.start} → {e.end} ({e.hours}h)
              </div>
              <div className="mt-1 text-sm leading-snug text-foreground">{e.headline}</div>
              {compoundCounts?.[i] ? (
                <div className="mt-2 rounded border border-[#d03b3b66] bg-[#d03b3b1a] px-2 py-1 text-[11px] leading-snug text-[#e66767]">
                  {compoundCounts[i]} compound{" "}
                  {compoundCounts[i] === 1 ? "finding" : "findings"} in this window —
                  see “Compound segments” below
                </div>
              ) : null}
            </button>
          ))}
        </div>
      </ScrollArea>
    </div>
  );
}
