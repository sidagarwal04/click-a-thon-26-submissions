/**
 * The answer, rendered from the governed brief rather than from Thesys.
 *
 * This is not a degraded placeholder. `fallback_brief` carries the whole
 * answer — every metric, every claim, every citation, and the same safe
 * actions — so when the renderer is pending, failed, tombstoned, or simply not
 * configured, the reader still gets the finding and the evidence under it. A
 * governed product that shows nothing when a third-party renderer is down has
 * made the renderer part of the guarantee, and it is not.
 */

import { Badge, Button, Card } from '@open-zentra/foundation-design-system';
import { Icon, type IconName } from '@open-zentra/foundation-icons';

import type { BriefMetric, VisualizationBrief } from '../../types';
import { BriefChart } from './brief-chart';

const DIRECTION: Record<BriefMetric['direction'], IconName | null> = {
  up: 'arrow_up',
  down: 'arrow_down',
  flat: 'minus',
  not_applicable: null,
};

const CitationLinks = ({
  citationIds,
  onOpenCitation,
}: {
  readonly citationIds: readonly string[];
  readonly onOpenCitation: (citationId: string) => void;
}) => (
  <span className="ml-2 inline-flex flex-wrap gap-1 align-middle">
    {citationIds.map((citationId, index) => (
      <button
        key={citationId}
        type="button"
        className="cursor-pointer border-0 bg-transparent p-0 font-mono text-[10px] text-primary underline"
        onClick={() => onOpenCitation(citationId)}
        // The figure is what matters; the index is only a handle for it.
        aria-label={`Open supporting evidence ${index + 1}`}
      >
        [{index + 1}]
      </button>
    ))}
  </span>
);

export const BriefAnswer = ({
  brief,
  notice,
  onAction,
  onOpenCitation,
  actionPending,
}: {
  readonly brief: VisualizationBrief;
  /** Why the rendered version is not being shown, when a reader should know. */
  readonly notice: string | null;
  readonly onAction: (actionId: string) => void;
  readonly onOpenCitation: (citationId: string) => void;
  readonly actionPending: boolean;
}) => {
  const observed = brief.claims.filter((claim) => claim.kind === 'observed');
  const interpretation = brief.claims.filter((claim) => claim.kind === 'interpretation');

  return (
    <Card component="article" padding="lg" className="mt-4">
      {notice ? (
        <p className="mb-5 font-mono text-[10px] uppercase tracking-[0.14em] text-foreground-muted">
          {notice}
        </p>
      ) : null}

      <h3 className="font-serif text-xl font-normal leading-tight tracking-[-0.02em]">
        {brief.headline}
      </h3>
      <p className="mt-3 text-sm leading-relaxed text-foreground-muted">{brief.summary}</p>

      {brief.time_range ? (
        <p className="mt-3 font-mono text-[10px] uppercase tracking-[0.14em] text-foreground-muted">
          {brief.time_range.start_label} → {brief.time_range.end_label}
        </p>
      ) : null}

      {brief.metrics.length > 0 ? (
        <div className="mt-6 grid gap-4 sm:grid-cols-2">
          {brief.metrics.map((metric) => {
            const icon = DIRECTION[metric.direction];
            return (
              <div key={metric.label} className="border-t border-border pt-3">
                <small className="font-mono text-[10px] uppercase tracking-[0.14em] text-foreground-muted">
                  {metric.label}
                </small>
                <p className="mt-1 flex items-baseline gap-2 font-mono text-lg">
                  {metric.display_value}
                  {icon ? <Icon name={icon} size="sm" aria-label={metric.direction} /> : null}
                </p>
                <CitationLinks citationIds={metric.citation_ids} onOpenCitation={onOpenCitation} />
              </div>
            );
          })}
        </div>
      ) : null}

      <BriefChart series={brief.series} />

      {observed.length > 0 ? (
        <section className="mt-8">
          <h4 className="font-mono text-[10px] uppercase tracking-[0.14em] text-foreground-muted">
            Observed
          </h4>
          <ul className="mt-3 flex list-none flex-col gap-2 p-0">
            {observed.map((claim) => (
              <li key={claim.text} className="text-sm leading-relaxed">
                {claim.text}
                <CitationLinks citationIds={claim.citation_ids} onOpenCitation={onOpenCitation} />
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {interpretation.length > 0 ? (
        <section className="mt-6">
          <h4 className="font-mono text-[10px] uppercase tracking-[0.14em] text-foreground-muted">
            Interpretation
          </h4>
          <ul className="mt-3 flex list-none flex-col gap-2 p-0">
            {interpretation.map((claim) => (
              <li key={claim.text} className="text-sm leading-relaxed text-foreground-muted">
                {claim.text}
                <CitationLinks citationIds={claim.citation_ids} onOpenCitation={onOpenCitation} />
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {brief.caveats.length > 0 ? (
        <ul className="mt-6 flex list-none flex-col gap-2 p-0">
          {brief.caveats.map((caveat) => (
            <li key={caveat}>
              <Badge intent="warning" size="sm">
                {caveat}
              </Badge>
            </li>
          ))}
        </ul>
      ) : null}

      <footer className="mt-8 flex flex-wrap items-center gap-3 border-t border-border pt-5">
        {brief.outcome_kind === 'confidence' && brief.confidence !== null ? (
          <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-foreground-muted">
            Confidence {Math.round(brief.confidence * 100)}%
          </span>
        ) : null}
        {brief.actions.map((action) => (
          <Button
            key={action.action_id}
            intent="secondary"
            size="sm"
            disabled={actionPending}
            onClick={() => onAction(action.action_id)}
          >
            {action.label}
          </Button>
        ))}
      </footer>
    </Card>
  );
};
