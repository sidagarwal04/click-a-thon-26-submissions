/**
 * The comparison chart, drawn by hand.
 *
 * A governed series is two points — what the metric was, and what it became.
 * That is a bar pair, and a bar pair is a handful of rects. Pulling a charting
 * library in to draw it would add far more than it saved, and the design
 * system has no chart component to reach for instead.
 *
 * Bars are scaled against the largest value across *all* series so two metrics
 * shown side by side stay comparable. Values that are not numbers — a governed
 * aggregate can be a string — are shown as labels with no bar, rather than
 * silently coerced to zero.
 */

import type { BriefSeries } from '../../types';

const BAR_HEIGHT = 96;

const numeric = (value: string): number | null => {
  const parsed = Number.parseFloat(value);
  return Number.isFinite(parsed) ? parsed : null;
};

export const BriefChart = ({ series }: { readonly series: readonly BriefSeries[] }) => {
  const values = series
    .flatMap((entry) => entry.points.map((point) => numeric(point.exact_value)))
    .filter((value): value is number => value !== null);
  if (values.length === 0) return null;

  // A floor of zero keeps a bar's length proportional to its value rather than
  // to its distance from the smallest one, which would exaggerate a small move.
  const ceiling = Math.max(...values, 0);
  const scale = (value: number | null) =>
    value === null || ceiling <= 0 ? 0 : Math.max((value / ceiling) * BAR_HEIGHT, 2);

  return (
    <div className="mt-6 grid gap-6 sm:grid-cols-2">
      {series.map((entry) => (
        <figure key={entry.label} className="m-0">
          <figcaption className="font-mono text-[10px] uppercase tracking-[0.14em] text-foreground-muted">
            {entry.label}
            <span className="ml-2 normal-case tracking-normal">{entry.unit}</span>
          </figcaption>

          <div
            className="mt-3 flex items-end gap-4"
            style={{ height: `${BAR_HEIGHT}px` }}
            role="img"
            aria-label={entry.points
              .map((point) => `${point.label}: ${point.display_value}`)
              .join(', ')}
          >
            {entry.points.map((point, index) => (
              <div key={point.position} className="flex flex-1 flex-col justify-end">
                <span
                  className={
                    index === entry.points.length - 1
                      ? 'w-full rounded-t-sm bg-primary'
                      : 'w-full rounded-t-sm bg-border'
                  }
                  style={{ height: `${scale(numeric(point.exact_value))}px` }}
                  aria-hidden="true"
                />
              </div>
            ))}
          </div>

          <div className="mt-2 flex gap-4 border-t border-border pt-2">
            {entry.points.map((point) => (
              <div key={point.position} className="flex flex-1 flex-col">
                <small className="font-mono text-[10px] uppercase tracking-[0.14em] text-foreground-muted">
                  {point.label}
                </small>
                <strong className="font-mono text-sm">{point.display_value}</strong>
              </div>
            ))}
          </div>
        </figure>
      ))}
    </div>
  );
};
