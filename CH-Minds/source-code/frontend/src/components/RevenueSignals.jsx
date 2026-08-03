import { useCallback, useEffect, useState } from "react"
import { TrendingDown, Layers, ZapOff } from "lucide-react"

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { getRevenueSignals } from "@/api/client"

const DETECTORS = [
  {
    key: "sustained_drift",
    label: "Sustained drift",
    icon: TrendingDown,
    blurb: "Segment bleeding for several consecutive days, faster than the business overall. No single day clears the spike threshold.",
  },
  {
    key: "collapsed_segment",
    label: "Collapsed segment",
    icon: ZapOff,
    blurb: "Earning segment that stopped. Invisible to a percent-deviation test once the segment produces no rows at all.",
  },
  {
    key: "share_shift",
    label: "Revenue mix shift",
    icon: Layers,
    blurb: "Segment's share of total revenue moved sharply while its absolute deviation stayed under threshold.",
  },
]

export default function RevenueSignals({ day, onInvestigate }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [scoped, setScoped] = useState(false)

  const load = useCallback(
    async (scopeToDay) => {
      setLoading(true)
      setError(null)
      try {
        setData(await getRevenueSignals(scopeToDay ? { day } : {}))
        setScoped(scopeToDay)
      } catch (e) {
        setError(e.message)
      } finally {
        setLoading(false)
      }
    },
    [day],
  )

  useEffect(() => {
    load(false)
  }, [load])

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div className="flex flex-col gap-1">
            <CardTitle>Revenue signals {data && `(${data.total})`}</CardTitle>

            <CardDescription>
              Revenue incident shapes the day-grain threshold scan cannot express
            </CardDescription>
          </div>
          <div className="flex gap-1.5">
            <Button variant={scoped ? "outline" : "default"} size="sm" className="h-7 text-xs" onClick={() => load(false)}>
              All days
            </Button>
            <Button variant={scoped ? "default" : "outline"} size="sm" className="h-7 text-xs" onClick={() => load(true)}>
              {day}
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {loading && <p className="text-sm text-muted-foreground">Running revenue detectors…</p>}
        {error && <p className="text-sm text-destructive">{error}</p>}
        {!loading && !error && data && (
          <div className="scroll-thin max-h-[28rem] space-y-4 overflow-y-auto pr-1">
            {DETECTORS.map(({ key, label, icon: Icon, blurb }) => {
              const items = data[key] || []
              return (
                <div key={key} className="w-[98%]">
                  <div className="flex items-center gap-1.5 text-xs font-semibold">
                    <Icon className="h-3.5 w-3.5" />
                    {label}
                    <span className="font-normal text-muted-foreground">({items.length})</span>
                  </div>
                  <p className="mt-0.5 text-[11px] leading-snug text-muted-foreground">{blurb}</p>
                  {items.length === 0 ? (
                    <p className="mt-1 text-[11px] italic text-muted-foreground">
                      None found in the loaded range.
                    </p>
                  ) : (
                    <ul className="mt-1.5 space-y-1">
                      {items.map((s, i) => (
                        <li key={`${s.dimension}-${s.value}-${s.day}-${i}`}>
                          <button
                            type="button"
                            onClick={() => onInvestigate?.({ metric: "revenue", day: s.day })}
                            className="w-full rounded-md border border-transparent px-2 py-1.5 text-left text-[11px] leading-snug hover:border-border hover:bg-muted/50"
                            title="Investigate this day"
                          >
                            <span className="font-medium tabular-nums">{s.day}</span>
                            <span className="mx-1.5 text-muted-foreground">·</span>
                            <span className="font-medium">
                              {s.dimension} = {String(s.value)}
                            </span>
                            <span className="block text-muted-foreground">{s.description}</span>
                          </button>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
