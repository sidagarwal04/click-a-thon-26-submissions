import type { DimensionVerdict } from "@/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export function ResponsibleSegment({ responsible }: { responsible: DimensionVerdict[] }) {
  const [top, ...also] = responsible;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">
          Responsible segment{responsible.length > 1 ? "s" : ""}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {top ? (
          <div className="flex flex-col gap-3">
            <div className="rounded-lg border p-3" style={{ borderColor: "#d03b3b66", backgroundColor: "#d03b3b14" }}>
              <div className="text-sm font-semibold text-foreground">
                {top.dim_name} = {top.top_value}
              </div>
              <div className="mt-1 text-xs text-muted-foreground">
                {(top.top_excess_of_total * 100).toFixed(0)}% of the whole incident ·{" "}
                {(top.top_excess_share * 100).toFixed(0)}% of the unexplained movement
              </div>
              <p className="mt-2 text-sm text-foreground/90">{top.reason}</p>
            </div>

            {/* Rendering only responsible[0] silently dropped every other
                flagged dimension, so the two panels together accounted for 8
                of 9 dimensions and the missing one was invisible rather than
                explained. Secondary hits are shown, de-emphasised, with the
                caveat that a dimension correlated with the primary will move
                with it — region tracks os_version when one OS skews to one
                region, and that is a correlation, not a second cause. */}
            {also.map((v) => (
              <div
                key={v.dim_name}
                className="rounded-lg border border-border p-3"
                style={{ backgroundColor: "#89878110" }}
              >
                <div className="text-sm font-medium text-foreground/90">
                  {v.dim_name} = {v.top_value}
                  <span className="ml-2 text-xs font-normal text-muted-foreground">also flagged</span>
                </div>
                <div className="mt-1 text-xs text-muted-foreground">
                  {(v.top_excess_of_total * 100).toFixed(0)}% of the whole incident ·{" "}
                  {(v.top_excess_share * 100).toFixed(0)}% of the unexplained movement
                </div>
                <p className="mt-2 text-sm text-muted-foreground">{v.reason}</p>
              </div>
            ))}

            {also.length > 0 && (
              <p className="text-xs leading-snug text-muted-foreground">
                Ranked by share of the incident. A dimension correlated with the primary will move
                with it — check whether the secondary is an independent cause or a reflection of the
                first before acting on it.
              </p>
            )}
          </div>
        ) : (
          <div className="rounded-lg border p-3" style={{ borderColor: "#89878166", backgroundColor: "#89878114" }}>
            <p className="text-sm text-foreground/90">
              No single segment responsible — the movement was uniform across every dimension checked.
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
