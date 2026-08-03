/**
 * The generative-UI half of an answer.
 *
 * One decision lives here: show what Thesys rendered, or render the governed
 * brief ourselves. Everything downstream of that is presentation. The rule is
 * simply whether `c1_response` exists — a pending render, a failed one, an
 * erased one, and an environment with no renderer configured at all are the
 * same situation from a reader's point of view, and the brief answers all four.
 */

import { lazy, Suspense, useState } from 'react';

import { useMutation, useQuery } from '@tanstack/react-query';

import { Button } from '@open-zentra/foundation-design-system';

import type { TokenSource } from '../../api';
import type { ResolvedCitation, VisualizationStatus } from '../../types';
import {
  executeVisualizationAction,
  getInvestigationVisualization,
  resolveCitation,
  retryVisualization,
} from './api';
import { BriefAnswer } from './brief-answer';
import { CitationDetail } from './citation-detail';

// Crayon and the Thesys renderer are a large dependency for a page that may
// never show one, so they are fetched only once an answer needs them.
const C1Answer = lazy(() => import('./c1-answer'));

/** Why the reader is looking at the brief instead of the rendered answer. */
const NOTICE: Partial<Record<VisualizationStatus, string>> = {
  pending: 'Preparing the rendered view — showing the verified brief.',
  generating: 'Preparing the rendered view — showing the verified brief.',
  failed: 'The rendered view could not be produced. This is the verified brief.',
  tombstoned: 'The rendered view was erased. This is the verified brief.',
};

export const VisualizationAnswer = ({
  getToken,
  investigationId,
  onFollowUp,
}: {
  readonly getToken: TokenSource;
  readonly investigationId: string;
  /** A `continue_conversation` action resolves to a message to send. */
  readonly onFollowUp: (message: string) => void;
}) => {
  const [citation, setCitation] = useState<ResolvedCitation | null>(null);

  const query = useQuery({
    queryKey: ['visualization', investigationId],
    queryFn: () => getInvestigationVisualization(getToken, investigationId),
    retry: false,
  });

  const visualization = query.data;

  const action = useMutation({
    mutationFn: (actionId: string) => {
      if (!visualization) throw new Error('This answer is no longer available.');
      return executeVisualizationAction(getToken, visualization.visualization_id, actionId);
    },
    onSuccess: async (result) => {
      // The server decided what the action meant. The button only named it.
      if (result.kind === 'open_citation' && result.citation_id) {
        setCitation(await resolveCitation(getToken, investigationId, result.citation_id));
        return;
      }
      if (result.kind === 'continue_conversation') {
        onFollowUp('Re-run this governed comparison with the latest data.');
      }
    },
  });

  const openCitation = useMutation({
    mutationFn: (citationId: string) => resolveCitation(getToken, investigationId, citationId),
    onSuccess: setCitation,
  });

  const retry = useMutation({
    mutationFn: () => {
      if (!visualization) throw new Error('This answer is no longer available.');
      return retryVisualization(getToken, visualization.visualization_id);
    },
    onSuccess: () => query.refetch(),
  });

  // An Investigation that produced no Finding has no visualization, and a 404
  // here is that — not a fault worth putting in front of a reader.
  if (query.isPending || query.error || !visualization) return null;

  const brief = visualization.fallback_brief;

  return (
    <div className="mt-4">
      {visualization.c1_response ? (
        <Suspense
          fallback={
            <p
              className="font-mono text-[10px] uppercase tracking-[0.14em] text-foreground-muted"
              aria-live="polite"
            >
              Loading the rendered view…
            </p>
          }
        >
          <C1Answer
            c1Response={visualization.c1_response}
            actions={brief?.actions ?? []}
            onAction={(actionId) => action.mutate(actionId)}
          />
        </Suspense>
      ) : brief ? (
        <BriefAnswer
          brief={brief}
          notice={NOTICE[visualization.status] ?? null}
          actionPending={action.isPending}
          onAction={(actionId) => action.mutate(actionId)}
          onOpenCitation={(citationId) => openCitation.mutate(citationId)}
        />
      ) : null}

      {visualization.status === 'failed' ? (
        <Button
          className="mt-3"
          intent="ghost"
          size="sm"
          disabled={retry.isPending}
          onClick={() => retry.mutate()}
        >
          Render again
        </Button>
      ) : null}

      {citation ? <CitationDetail citation={citation} onClose={() => setCitation(null)} /> : null}
    </div>
  );
};
