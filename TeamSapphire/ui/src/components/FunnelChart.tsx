import { useMemo } from "react";
import type { EChartsOption } from "echarts";
import echarts, { EChartsReactCore } from "@/echarts-setup";
import type { FactorTotals } from "@/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

// Ordinal blue ramp (dataviz skill, palette.md) — steps stay <= 600 on the
// dark surface so the lightest stage still clears 2:1 contrast.
const STAGE_COLORS = ["#86b6ef", "#5598e7", "#2a78d6", "#184f95"];

const STAGES: { key: keyof FactorTotals; label: string }[] = [
  { key: "requests", label: "Requests" },
  { key: "fills", label: "Fills" },
  { key: "impressions", label: "Impressions" },
  { key: "clicks", label: "Clicks" },
];

function funnelSeries(name: string, totals: FactorTotals, left: string, width: string, max: number) {
  return {
    name,
    type: "funnel" as const,
    left,
    width,
    top: 40,
    bottom: 20,
    min: 0,
    max,
    minSize: "10%",
    maxSize: "100%",
    sort: "none" as const,
    gap: 4,
    label: { color: "#ffffff", fontSize: 13 },
    labelLine: { show: false },
    itemStyle: { borderColor: "#1a1a19", borderWidth: 1 },
    data: STAGES.map((s, i) => ({
      name: s.label,
      value: totals[s.key],
      itemStyle: { color: STAGE_COLORS[i] },
    })),
  };
}

export function FunnelChart({ actual, baseline }: { actual: FactorTotals; baseline: FactorTotals }) {
  const option: EChartsOption = useMemo(() => {
    const max = Math.max(actual.requests, baseline.requests);
    return {
      backgroundColor: "transparent",
      tooltip: {
        trigger: "item",
        backgroundColor: "#232322",
        borderColor: "rgba(255,255,255,0.1)",
        textStyle: { color: "#ffffff" },
        formatter: (p: any) => `${p.seriesName} — ${p.name}: ${Number(p.value).toLocaleString(undefined, { maximumFractionDigits: 0 })}`,
      },
      series: [
        funnelSeries("Actual", actual, "3%", "44%", max),
        funnelSeries("Baseline", baseline, "53%", "44%", max),
      ],
      graphic: [
        { type: "text", left: "20%", top: 8, style: { text: "Actual", fill: "#c3c2b7", fontSize: 13, fontWeight: 600 } },
        { type: "text", left: "70%", top: 8, style: { text: "Baseline", fill: "#c3c2b7", fontSize: 13, fontWeight: 600 } },
      ],
    };
  }, [actual, baseline]);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Funnel — requests → fills → impressions → clicks</CardTitle>
      </CardHeader>
      <CardContent>
        <EChartsReactCore echarts={echarts} option={option} style={{ height: 460 }} notMerge />
      </CardContent>
    </Card>
  );
}
