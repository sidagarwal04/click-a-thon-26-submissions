import { Link } from 'react-router-dom';

import { Badge } from '@open-zentra/foundation-design-system';
import { Icon } from '@open-zentra/foundation-icons';

import type { TokenSource } from '../../api';
import type { ThreadInvestigation } from '../../types';
import { VisualizationAnswer } from './visualization-answer';

/**
 * What the agents produced, rendered as the assistant's turn.
 *
 * There is no message behind this. A published Finding lives on the
 * Investigation, so the headline and summary are read from there and the
 * generated view is rendered beneath them. Until the Investigation is terminal
 * the row still exists — saying which state it is in is more useful than
 * showing nothing while four agents work.
 */
const WORKING: Record<string, string> = {
  pending: 'Queued.',
  running: 'Reading governed metrics…',
  evaluating: 'Rechecking the result independently…',
  awaiting_approval: 'Waiting for a decision before this can be published.',
};

const STOPPED: Record<string, string> = {
  failed: 'This investigation could not be completed.',
  cancelled: 'This investigation was stopped.',
  rejected: 'This draft was rejected, so no Finding was published.',
};

export const AnswerRow = ({
  investigation,
  getToken,
  onFollowUp,
}: {
  readonly investigation: ThreadInvestigation;
  readonly getToken: TokenSource;
  readonly onFollowUp: (message: string) => void;
}) => {
  const finding = investigation.finding;
  const working = WORKING[investigation.status];
  const stopped = STOPPED[investigation.status];

  return (
    <div className="flex gap-4">
      <span
        className="mt-1 flex h-7 w-7 shrink-0 items-center justify-center rounded-sm bg-accent text-accent-foreground"
        aria-hidden="true"
      >
        <Icon name="sparkles" size="sm" />
      </span>

      <div className="min-w-0 flex-1">
        {finding ? (
          <>
            <h2 className="font-serif text-xl font-normal leading-tight tracking-[-0.02em]">
              {finding.headline}
            </h2>
            <p className="mt-3 text-sm leading-relaxed text-foreground-muted">{finding.summary}</p>
          </>
        ) : null}

        {working ? (
          <p
            className="font-mono text-[10px] uppercase tracking-[0.14em] text-foreground-muted"
            aria-live="polite"
          >
            {working}
          </p>
        ) : null}

        {stopped ? (
          <Badge intent="warning" size="sm">
            {stopped}
          </Badge>
        ) : null}

        {/* The generated view, and the native brief whenever it is absent. */}
        <VisualizationAnswer
          getToken={getToken}
          investigationId={investigation.investigation_id}
          onFollowUp={onFollowUp}
        />

        <Link
          className="mt-4 inline-flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.14em] text-primary no-underline hover:underline"
          to={`/investigations/${investigation.investigation_id}`}
        >
          <Icon name="search" size="sm" />
          Open the evidence trace
        </Link>
      </div>
    </div>
  );
};
