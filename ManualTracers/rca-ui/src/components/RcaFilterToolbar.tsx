import { useState } from "react";
import { CalendarRange, Loader2, Play } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import type { Granularity, RcaFilters } from "@/lib/types";

const OS_VERSIONS = ["Android 15", "Android 14", "iOS 18.1", "iOS 17.5"] as const;

interface Props {
  filters: RcaFilters;
  onChange: (next: RcaFilters) => void;
  onApply: () => void;
  loading: boolean;
  defaultOs?: string;
}

function toLocalInput(iso: string) {
  return iso.slice(0, 16);
}

function fromLocalInput(val: string) {
  return val.length === 16 ? `${val}:00` : val;
}

const filterFieldClass =
  "h-9 bg-background text-foreground text-xs placeholder:text-muted-foreground";

export function RcaFilterToolbar({ filters, onChange, onApply, loading, defaultOs }: Props) {
  const patch = (partial: Partial<RcaFilters>) => onChange({ ...filters, ...partial });

  return (
    <section
      aria-label="RCA chart filters"
      className="border-b border-border bg-card/40 px-4 py-3 backdrop-blur-sm"
    >
      <div className="mx-auto flex max-w-[1400px] flex-wrap items-end gap-x-4 gap-y-3">
        <div className="flex min-w-[9rem] flex-col gap-1">
          <Label htmlFor="from" className="text-xs text-muted-foreground">
            From
          </Label>
          <Input
            id="from"
            type="datetime-local"
            value={toLocalInput(filters.from)}
            onChange={(e) => patch({ from: fromLocalInput(e.target.value) })}
            className={`${filterFieldClass} font-mono`}
          />
        </div>
        <div className="flex min-w-[9rem] flex-col gap-1">
          <Label htmlFor="to" className="text-xs text-muted-foreground">
            To
          </Label>
          <Input
            id="to"
            type="datetime-local"
            value={toLocalInput(filters.to)}
            onChange={(e) => patch({ to: fromLocalInput(e.target.value) })}
            className={`${filterFieldClass} font-mono`}
          />
        </div>
        <div className="flex min-w-[8rem] flex-col gap-1">
          <Label className="text-xs text-muted-foreground">Granularity</Label>
          <Select
            value={filters.granularity}
            onValueChange={(v) => patch({ granularity: v as Granularity })}
          >
            <SelectTrigger className={`${filterFieldClass} w-[8.5rem] text-foreground`}>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="hour">Hour</SelectItem>
              <SelectItem value="day">Day</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="flex min-w-[10rem] flex-col gap-1">
          <Label className="text-xs text-muted-foreground">OS filter (charts)</Label>
          <Select
            value={filters.os_versions[0] ?? "__all__"}
            onValueChange={(v) =>
              patch({ os_versions: v === "__all__" ? [] : [v] })
            }
          >
            <SelectTrigger className={`${filterFieldClass} text-foreground`}>
              <SelectValue placeholder="All OS" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="__all__">All OS</SelectItem>
              {OS_VERSIONS.map((os) => (
                <SelectItem key={os} value={os}>
                  {os}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <Button onClick={onApply} disabled={loading} className="h-9 gap-2 px-5">
          {loading ? (
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
          ) : (
            <Play className="h-4 w-4" aria-hidden />
          )}
          Apply
        </Button>
      </div>
      <div className="mx-auto mt-2 flex max-w-[1400px] flex-wrap items-center gap-1.5">
        {defaultOs && (
          <span className="rounded-sm border border-primary/40 bg-primary/10 px-2 py-0.5 text-[11px] text-primary">
            Culprit: {defaultOs}
          </span>
        )}
        <Separator orientation="vertical" className="mx-1 h-5" />
        <CalendarRange className="h-3.5 w-3.5 text-muted-foreground" aria-hidden />
        <span className="text-[11px] text-muted-foreground">
          Shared filter state drives all charts below
        </span>
      </div>
    </section>
  );
}
