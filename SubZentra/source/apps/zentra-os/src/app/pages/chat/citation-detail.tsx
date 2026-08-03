/**
 * One piece of supporting evidence, opened in place.
 *
 * A citation can resolve to a tombstone, which is not an error — it is the
 * recorded fact that the evidence was deliberately erased. It is rendered as
 * plainly as the measurement would have been, because a reader who cannot tell
 * "erased" from "broken" cannot trust either answer.
 */

import { Card } from '@open-zentra/foundation-design-system';
import { Icon } from '@open-zentra/foundation-icons';

import { isTombstone, type ResolvedCitation } from '../../types';

export const CitationDetail = ({
  citation,
  onClose,
}: {
  readonly citation: ResolvedCitation;
  readonly onClose: () => void;
}) => (
  <Card component="aside" padding="md" className="mt-4">
    <div className="flex items-start justify-between gap-4">
      <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-primary">
        Evidence · {citation.citation_id.slice(0, 8)}
      </p>
      <button
        type="button"
        className="cursor-pointer border-0 bg-transparent p-0 text-foreground-muted"
        onClick={onClose}
        aria-label="Close this evidence"
      >
        <Icon name="x" size="sm" />
      </button>
    </div>

    {isTombstone(citation) ? (
      <p className="mt-4 text-sm leading-relaxed text-foreground-muted">
        This evidence was erased on {new Date(citation.erased_at).toLocaleDateString()} under{' '}
        <code>{citation.category}</code>. The measurement it supported was recorded before the
        erasure and is not restated here.
      </p>
    ) : (
      <dl className="mt-4 grid gap-3 sm:grid-cols-2">
        <div>
          <dt className="font-mono text-[10px] uppercase tracking-[0.14em] text-foreground-muted">
            Metric
          </dt>
          <dd className="m-0 font-mono text-sm">{citation.metric}</dd>
        </div>
        <div>
          <dt className="font-mono text-[10px] uppercase tracking-[0.14em] text-foreground-muted">
            Value
          </dt>
          <dd className="m-0 font-mono text-sm">{citation.aggregate_value}</dd>
        </div>
        {citation.period ? (
          <div>
            <dt className="font-mono text-[10px] uppercase tracking-[0.14em] text-foreground-muted">
              Period
            </dt>
            <dd className="m-0 font-mono text-sm">
              {citation.period}
              {citation.grain ? ` · ${citation.grain}` : ''}
            </dd>
          </div>
        ) : null}
        {citation.filters.length > 0 ? (
          <div>
            <dt className="font-mono text-[10px] uppercase tracking-[0.14em] text-foreground-muted">
              Scope
            </dt>
            <dd className="m-0 flex flex-col gap-1 font-mono text-sm">
              {citation.filters.map((filter) => (
                <span key={`${filter.member}-${filter.operator}`}>
                  {filter.member} {filter.operator} {filter.values.join(', ')}
                </span>
              ))}
            </dd>
          </div>
        ) : null}
      </dl>
    )}
  </Card>
);
