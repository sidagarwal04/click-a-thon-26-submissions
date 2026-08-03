import { useMemo, type ReactNode } from "react";
import type { EChartsOption } from "echarts";
import echarts, { EChartsReactCore } from "@/echarts-setup";
import type { Decomposition, DimensionVerdict, Factor } from "@/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const FACTOR_LABEL: Record<Factor, string> = {
  requests: "Requests",
  fill_rate: "Fill rate",
  render_rate: "Render rate",
  ecpm: "eCPM",
};
const FACTOR_ORDER: Factor[] = ["requests", "fill_rate", "render_rate", "ecpm"];

const FLAT_THRESHOLD = 0.01; // |pct_change| < 1% reads as flat

type Status = "flat" | "moved" | "primary";

function statusOf(pctChange: number, factor: Factor, primaryFactor: Factor): Status {
  if (factor === primaryFactor) return "primary";
  if (Math.abs(pctChange) < FLAT_THRESHOLD) return "flat";
  return "moved";
}

// dataviz skill status palette, dark-surface steps (#1a1a19 chart surface).
const STATUS_COLOR: Record<Status, string> = {
  flat: "#0ca30c", // good
  moved: "#fab219", // warning
  primary: "#d03b3b", // critical
};

function formatValue(factor: Factor, value: number): string {
  if (factor === "requests") return value.toLocaleString(undefined, { maximumFractionDigits: 0 });
  if (factor === "ecpm") return `$${value.toFixed(4)}`;
  return `${(value * 100).toFixed(2)}%`;
}

function pct(v: number): string {
  return `${v >= 0 ? "+" : ""}${(v * 100).toFixed(1)}%`;
}

// Same "what moved, why" the engine's headline sentence carries (engine/investigate.py
// _headline), rebuilt as labelled rows instead of one dense sentence — a segment name
// buried mid-clause reads slower than the same fact pulled onto its own line.
function WhatWhy({
  classification,
  revenuePctChange,
  primaryFactor,
  factors,
  responsible,
}: {
  classification: "localized" | "global" | "unattributed";
  revenuePctChange: number;
  primaryFactor: Factor;
  factors: Decomposition["factors"];
  responsible: DimensionVerdict[];
}) {
  const revenueUp = revenuePctChange >= 0;
  const primaryMove = factors.find((f) => f.factor === primaryFactor)?.pct_change ?? 0;
  const factorLabel = FACTOR_LABEL[primaryFactor];
  const verb = primaryMove >= 0 ? "rose" : "fell";

  let why: ReactNode;
  if (classification === "localized" && responsible[0]) {
    const top = responsible[0];
    const seg = top.segments[0];
    why = (
      <>
        <strong className="font-semibold">{factorLabel}</strong> {seg.pct_change >= 0 ? "rose" : "fell"}{" "}
        <strong className="font-semibold">{pct(seg.pct_change)}</strong> in{" "}
        <span className="rounded bg-foreground/10 px-1.5 py-0.5 font-mono text-[13px]">
          {top.dim_name} = {top.top_value}
        </span>
        , vs {pct(primaryMove)} platform-wide.
      </>
    );
  } else if (classification === "global") {
    why = (
      <>
        <strong className="font-semibold">{factorLabel}</strong> {verb}{" "}
        <strong className="font-semibold">{pct(primaryMove)}</strong> uniformly across every dimension — no
        single segment responsible.
      </>
    );
  } else {
    why = (
      <>
        <strong className="font-semibold">{factorLabel}</strong> {verb}{" "}
        <strong className="font-semibold">{pct(primaryMove)}</strong>, but no dimension met the attribution
        bar.
      </>
    );
  }

  return (
    <div
      className="rounded-lg border p-4"
      style={{ borderColor: "#d03b3b66", backgroundColor: "#d03b3b0d" }}
    >
      <div className="flex items-baseline gap-2">
        <span className="w-10 shrink-0 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
          What
        </span>
        <span className="text-xl font-bold" style={{ color: revenueUp ? "#0ca30c" : "#d03b3b" }}>
          Revenue {pct(revenuePctChange)}
        </span>
      </div>
      <div className="mt-2 flex items-start gap-2">
        <span className="mt-0.5 w-10 shrink-0 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
          Why
        </span>
        <p className="text-sm leading-relaxed text-foreground/90">{why}</p>
      </div>
    </div>
  );
}

export function MetricTree({
  decomposition,
  classification,
  responsible,
}: {
  decomposition: Decomposition;
  classification?: "localized" | "global" | "unattributed";
  responsible?: DimensionVerdict[];
}) {
  const factors = decomposition.factors;
  const ordered = useMemo(
    () => [...factors].sort((a, b) => FACTOR_ORDER.indexOf(a.factor) - FACTOR_ORDER.indexOf(b.factor)),
    [factors],
  );

  const option: EChartsOption = useMemo(
    () => ({
      backgroundColor: "transparent",
      grid: { left: 90, right: 55, top: 10, bottom: 20 },
      tooltip: {
        trigger: "item",
        backgroundColor: "#232322",
        borderColor: "rgba(255,255,255,0.1)",
        textStyle: { color: "#ffffff" },
        formatter: (p: any) =>
          `${FACTOR_LABEL[ordered[p.dataIndex].factor]}: ${(ordered[p.dataIndex].pct_change * 100).toFixed(2)}%`,
      },
      xAxis: {
        type: "value",
        axisLabel: { formatter: (v: number) => `${v}%`, color: "#898781" },
        axisLine: { lineStyle: { color: "#383835" } },
        splitLine: { lineStyle: { color: "#2c2c2a" } },
      },
      yAxis: {
        type: "category",
        data: ordered.map((f) => FACTOR_LABEL[f.factor]),
        axisLabel: { color: "#c3c2b7" },
        axisLine: { lineStyle: { color: "#383835" } },
        axisTick: { show: false },
      },
      series: [
        {
          type: "bar",
          data: ordered.map((f) => ({
            value: Number((f.pct_change * 100).toFixed(3)),
            itemStyle: {
              color: STATUS_COLOR[statusOf(f.pct_change, f.factor, decomposition.primary_factor)],
              borderRadius: 3,
            },
          })),
          barWidth: 36,
          markLine: {
            symbol: "none",
            silent: true,
            lineStyle: { color: "#383835" },
            label: { show: false },
            data: [{ xAxis: 0 }],
          },
        },
      ],
    }),
    [ordered, decomposition.primary_factor],
  );

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Metric tree — which factor moved</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {classification && responsible && (
          <WhatWhy
            classification={classification}
            revenuePctChange={decomposition.revenue_pct_change}
            primaryFactor={decomposition.primary_factor}
            factors={decomposition.factors}
            responsible={responsible}
          />
        )}
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {factors.map((f) => {
            const status = statusOf(f.pct_change, f.factor, decomposition.primary_factor);
            const color = STATUS_COLOR[status];
            return (
              <div
                key={f.factor}
                className="rounded-lg border p-3 text-left"
                style={{ borderColor: `${color}66`, backgroundColor: `${color}14` }}
              >
                <div className="flex items-center gap-1.5">
                  <span className="h-2 w-2 rounded-full" style={{ backgroundColor: color }} />
                  <span className="text-xs font-medium text-muted-foreground">{FACTOR_LABEL[f.factor]}</span>
                </div>
                <div className="mt-1 text-lg font-semibold text-foreground">
                  {f.pct_change >= 0 ? "+" : ""}
                  {(f.pct_change * 100).toFixed(2)}%
                </div>
                <div className="mt-1 text-xs text-muted-foreground">
                  {formatValue(f.factor, f.actual)} vs {formatValue(f.factor, f.baseline)}
                </div>
              </div>
            );
          })}
        </div>
        <EChartsReactCore echarts={echarts} option={option} style={{ height: 320 }} notMerge />
      </CardContent>
    </Card>
  );
}
