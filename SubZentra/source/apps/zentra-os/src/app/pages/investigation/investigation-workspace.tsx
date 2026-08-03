import { Card } from '@open-zentra/foundation-design-system';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { AnimatePresence, motion } from 'motion/react';
import { Link, useParams } from 'react-router-dom';

import { requestJson, type TokenSource } from '../../api';
import { DraftFindingPanel, LegacyFindingNotice } from '../../draft-finding-panel';
import type { Investigation, RejectionReason } from '../../types';
import { ApprovalInspector } from './approval-inspector';
import { EvidenceDeletion } from './evidence-deletion';
import { EvidenceSpine } from './evidence-spine';
import { MetricField } from './metric-field';
import { OutcomePanel } from './outcome-panel';

/**
 * One Investigation: what it asked, what the ledger recorded, what was found,
 * and the decision it is waiting on.
 */
export const InvestigationWorkspace = ({
  getToken,
}: {
  readonly getToken: TokenSource;
}) => {
  const { id } = useParams();
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: ['investigation', id],
    queryFn: () => requestJson<Investigation>(`/v1/investigations/${id}`, getToken),
    enabled: Boolean(id),
    refetchInterval: (result) => {
      const data = result.state.data;
      if (!data) return false;
      const settled =
        data.status === 'completed' ||
        data.status === 'rejected' ||
        data.status === 'failed' ||
        data.status === 'cancelled';
      // Keep polling while the agents are still working, and afterwards until
      // the ledger has caught up with what already happened.
      return !settled || data.audit_delivery === 'pending' ? 1500 : false;
    },
  });

  const deletion = useMutation({
    mutationFn: () => {
      if (!id) throw new Error('This investigation is no longer available.');
      return requestJson<Investigation>(
        `/v1/investigations/${id}/evidence-deletion`,
        getToken,
        {
          method: 'POST',
          // The API demands the Investigation be named as well as addressed.
          // Sending it from here keeps the client honest about which one it
          // means rather than trusting the URL it happens to be on.
          body: JSON.stringify({ confirm_investigation_id: id }),
        },
      );
    },
    onSuccess: (investigation) =>
      queryClient.setQueryData(['investigation', id], investigation),
  });

  const decision = useMutation({
    mutationFn: ({
      choice,
      reason,
    }: {
      choice: 'approve' | 'reject';
      reason: RejectionReason | null;
    }) => {
      const approval = query.data?.pending_approval;
      if (!approval || !id) {
        throw new Error('This approval is no longer available.');
      }
      return requestJson<Investigation>(
        `/v1/investigations/${id}/approvals/${approval.approval_id}/decision`,
        getToken,
        {
          method: 'POST',
          body: JSON.stringify({ decision: choice, reason }),
        },
      );
    },
    onSuccess: (investigation) =>
      queryClient.setQueryData(['investigation', id], investigation),
  });

  if (query.isPending) {
    return (
      <section className="flex flex-col items-start gap-4 px-8 py-10" aria-live="polite">
        <span className="h-px w-40 animate-pulse bg-primary" aria-hidden="true" />
        <p className="text-sm text-foreground-muted">Loading persisted evidence…</p>
      </section>
    );
  }

  if (query.error || !query.data) {
    return (
      <section className="flex flex-col items-start gap-4 px-8 py-10">
        <p className="text-sm text-danger" role="alert">
          {query.error?.message ?? 'Investigation was not found.'}
        </p>
        <Link className="text-sm text-primary" to="/">
          Return to the launcher
        </Link>
      </section>
    );
  }

  const investigation = query.data;

  return (
    <div className="px-8 py-10" data-resolution={investigation.status}>
      <header className="flex flex-wrap items-start justify-between gap-6 border-b border-border pb-8">
        <div className="min-w-0">
          <p className="font-mono text-[10px] font-bold uppercase tracking-[0.16em] text-primary">
            Investigation · {investigation.investigation_id.slice(0, 8)}
          </p>
          <motion.h1
            className="mt-3 max-w-3xl font-serif text-[clamp(1.9rem,3.6vw,3rem)] font-normal leading-[1.04] tracking-[-0.035em]"
            layoutId="investigation-question"
          >
            {investigation.canonical_question}
          </motion.h1>
        </div>
        <div className="flex items-center gap-3" aria-live="polite">
          <span className="h-2 w-2 rounded-full bg-primary" aria-hidden="true" />
          <div className="flex flex-col">
            <small className="font-mono text-[10px] uppercase tracking-[0.14em] text-foreground-muted">
              Current state
            </small>
            <strong className="font-mono text-sm uppercase tracking-[0.08em]">
              {investigation.status.replace(/_/g, ' ')}
            </strong>
          </div>
        </div>
      </header>

      <div className="mt-8 grid grid-cols-1 items-start gap-6 xl:grid-cols-[minmax(0,20rem)_minmax(0,1fr)_minmax(0,22rem)]">
        <EvidenceSpine investigation={investigation} />

        <Card component="article" padding="lg">
          <Card.Header
            end={
              <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-foreground-muted">
                Evaluation {investigation.evaluation_attempts} / 3
              </span>
            }
          >
            <Card.Title>Finding preview</Card.Title>
          </Card.Header>

          {investigation.finding ? (
            <>
              <h2 className="font-serif text-2xl font-normal leading-tight tracking-[-0.02em]">
                {investigation.finding.headline}
              </h2>
              <p className="mt-4 max-w-2xl text-sm leading-relaxed text-foreground-muted">
                {investigation.finding.summary}
              </p>

              <div className="mt-8 grid gap-6 sm:grid-cols-2">
                {investigation.finding.metrics.map((metric) => (
                  <MetricField key={metric.metric} metric={metric} />
                ))}
              </div>

              <div className="mt-8">
                {investigation.draft_finding ? (
                  <DraftFindingPanel
                    draft={investigation.draft_finding}
                    investigationId={investigation.investigation_id}
                  />
                ) : (
                  <LegacyFindingNotice />
                )}
              </div>

              <OutcomePanel investigation={investigation} />

              <footer className="mt-8 flex flex-wrap items-center gap-3 border-t border-border pt-5 font-mono text-[10px] uppercase tracking-[0.14em] text-foreground-muted">
                <span>Evidence reference</span>
                <code className="normal-case tracking-normal text-foreground">
                  {investigation.finding.evidence_references[0]}
                </code>
              </footer>
            </>
          ) : null}
        </Card>

        <AnimatePresence mode="wait">
          <ApprovalInspector
            key={investigation.pending_approval?.approval_id ?? investigation.status}
            investigation={investigation}
            pending={decision.isPending}
            onDecision={(choice, reason) => decision.mutate({ choice, reason })}
          />
        </AnimatePresence>
      </div>

      <EvidenceDeletion
        investigation={investigation}
        canDelete={investigation.can_delete_evidence}
        pending={deletion.isPending}
        onDelete={() => deletion.mutate()}
      />

      {decision.error ? (
        <p className="mt-6 text-sm text-danger" role="alert">
          {decision.error.message}
        </p>
      ) : null}
    </div>
  );
};
